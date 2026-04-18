# routes/auth.py
# ---------------------------------------------------------
# Authentication & Profile routes:
#   /login, /logout, /register
#   /profile, /profile/edit, /profile/change-password
#   /forgot-password, /reset-password/<token>
# ---------------------------------------------------------

import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from .. import db
from ..models import User
from ..forms import (
    LoginForm, RegistrationForm, ProfileEditForm,
    ChangePasswordForm, ForgotPasswordForm, ResetPasswordForm
)
from ..utils import log_action

bp = Blueprint("auth", __name__)


# ── HOME ─────────────────────────────────────────────────────────────────────

@bp.route("/")
def home():
    """Redirect to the correct dashboard based on the user's role."""
    if current_user.is_authenticated:
        return _redirect_to_dashboard(current_user.role)
    return redirect(url_for("auth.login"))


def _redirect_to_dashboard(role):
    """Helper: return a redirect to the right dashboard."""
    destinations = {
        "administrator": "admin.admin_dashboard",
        "inspector":     "inspector.inspector_dashboard",
        "fisherman":     "fisherman.fisherman_dashboard",
        "amateur":       "fisherman.amateur_dashboard",
    }
    endpoint = destinations.get(role, "admin.admin_dashboard")
    return redirect(url_for(endpoint))


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@bp.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in → go to their dashboard
    if current_user.is_authenticated:
        return _redirect_to_dashboard(current_user.role)

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        # ── Account locked? ──────────────────────────────────────────────────
        if user and user.locked_until and user.locked_until > datetime.utcnow():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() // 60) + 1
            flash(f"Account temporarily locked. Try again in {remaining} minute(s).", "danger")
            return render_template("auth/login.html", form=form)

        # ── Correct password ─────────────────────────────────────────────────
        if user and user.check_password(form.password.data):
            # is_active check — deactivated users cannot log in
            if not user.is_active:
                flash("Your account has been deactivated. Contact an administrator.", "danger")
                return render_template("auth/login.html", form=form)

            # Reset failed-login counter on success
            user.failed_logins = 0
            user.locked_until = None
            db.session.commit()

            # Remember Me is handled by flask-login when remember=True
            login_user(user, remember=form.remember.data)
            log_action("login", "User", user.id)
            flash(f"Welcome back, {user.first_name}!", "success")

            # If user was trying to visit a protected page, go back there
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)

            return _redirect_to_dashboard(user.role)

        # ── Wrong password ───────────────────────────────────────────────────
        else:
            if user:
                user.failed_logins = (user.failed_logins or 0) + 1
                if user.failed_logins >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    flash("Too many failed attempts. Account locked for 15 minutes.", "danger")
                else:
                    remaining_attempts = 5 - user.failed_logins
                    flash(
                        f"Invalid email or password. "
                        f"{remaining_attempts} attempt(s) remaining.",
                        "danger"
                    )
                db.session.commit()
            else:
                # Don't reveal whether the email exists
                flash("Invalid email or password.", "danger")

    return render_template("auth/login.html", form=form)


# ── LOGOUT ────────────────────────────────────────────────────────────────────

@bp.route("/logout")
@login_required
def logout():
    log_action("logout", "User", current_user.id)
    logout_user()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))


# ── REGISTER ──────────────────────────────────────────────────────────────────

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))

    form = RegistrationForm()

    if form.validate_on_submit():
        # Prevent duplicate emails
        if User.query.filter_by(email=form.email.data).first():
            flash("That email is already registered. Please log in.", "danger")
            return redirect(url_for("auth.login"))

        user = User(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            id_number=form.id_number.data,
            age_category=form.age_category.data,
            role=form.role.data,   # only fisherman / amateur from the public form
            is_active=True,
            failed_logins=0,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        log_action("register", "User", user.id, f"New {user.role} account")
        flash("Account created successfully! You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


# ── PROFILE ───────────────────────────────────────────────────────────────────

@bp.route("/profile")
@login_required
def profile():
    """View your own profile page."""
    return render_template("auth/profile.html", user=current_user)


@bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    """Edit your own name, phone, vessel registration, etc."""
    form = ProfileEditForm(obj=current_user)

    if form.validate_on_submit():
        current_user.first_name            = form.first_name.data
        current_user.last_name             = form.last_name.data
        current_user.phone                 = form.phone.data
        current_user.vessel_registration   = form.vessel_registration.data
        current_user.fishing_permit_number = form.fishing_permit_number.data
        db.session.commit()
        log_action("profile_edit", "User", current_user.id)
        flash("Profile updated successfully.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/profile_edit.html", form=form)


@bp.route("/profile/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Let the logged-in user change their own password."""
    form = ChangePasswordForm()

    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return render_template("auth/change_password.html", form=form)

        current_user.set_password(form.new_password.data)
        db.session.commit()
        log_action("password_change", "User", current_user.id)
        flash("Password changed successfully.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("auth/change_password.html", form=form)


# ── PASSWORD RESET ────────────────────────────────────────────────────────────

@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Request a password-reset link by email."""
    if current_user.is_authenticated:
        return redirect(url_for("auth.home"))

    form = ForgotPasswordForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        # Always show the same message so we don't reveal which emails exist
        flash(
            "If that email is registered, a reset link has been sent. "
            "Check your inbox.",
            "info"
        )

        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token        = token
            user.reset_token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()

            # In production you would send an email here.
            # For now, show the link in a flash message (DEV MODE only).
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            flash(f"[DEV MODE] Reset link: {reset_url}", "warning")

        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    """Allow a user to set a new password using a valid reset token."""
    user = User.query.filter_by(reset_token=token).first()

    if not user or not user.reset_token_expiry or user.reset_token_expiry < datetime.utcnow():
        flash("This reset link is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        user.reset_token        = None
        user.reset_token_expiry = None
        user.failed_logins      = 0
        user.locked_until       = None
        db.session.commit()
        log_action("password_reset", "User", user.id)
        flash("Password reset successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)
