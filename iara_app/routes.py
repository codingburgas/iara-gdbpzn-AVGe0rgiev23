from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from .models import User
from . import db

bp = Blueprint("main", __name__)

@bp.route("/")
def home():
    return redirect(url_for("main.login"))

@bp.route("/login", methods=["GET", "POST"])
def login():
    from .forms import LoginForm
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and user.check_password(form.password.data):
            login_user(user)
            flash("Login successful!", "success")

            if user.role == "administrator":
                return redirect(url_for("main.admin_dashboard"))
            elif user.role == "inspector":
                return redirect(url_for("main.inspector_dashboard"))
            elif user.role == "fisherman":
                return redirect(url_for("main.fisherman_dashboard"))
            else:
                return redirect(url_for("main.amateur_dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html", form=form)

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.login"))

@bp.route("/register", methods=["GET", "POST"])
def register():
    from .forms import RegistrationForm
    form = RegistrationForm()

    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("main.register"))

        user = User(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            role=form.role.data
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", form=form)

@bp.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if current_user.role != "administrator":
        abort(403)
    return render_template("admin_dashboard.html")

@bp.route("/inspector/dashboard")
@login_required
def inspector_dashboard():
    if current_user.role != "inspector":
        abort(403)
    return render_template("inspector_dashboard.html")

@bp.route("/fisherman/dashboard")
@login_required
def fisherman_dashboard():
    if current_user.role != "fisherman":
        abort(403)
    return render_template("fisherman_dashboard.html")

@bp.route("/amateur/dashboard")
@login_required
def amateur_dashboard():
    if current_user.role != "amateur":
        abort(403)
    return render_template("amateur_dashboard.html")
