from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from datetime import date
from wtforms import SubmitField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm
from wtforms.fields import DateField

from .models import User, Vessel, Permit
from .forms import LoginForm, RegistrationForm, VesselForm, PermitForm
from . import db

bp = Blueprint("main", __name__)


# -------------------------
# AUTH
# -------------------------

@bp.route("/")
def home():
    return redirect(url_for("main.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
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


# -------------------------
# DASHBOARDS
# -------------------------

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


# -------------------------
# VESSELS
# -------------------------

@bp.route("/admin/vessels/add", methods=["GET", "POST"])
@login_required
def add_vessel():
    form = VesselForm()

    if form.validate_on_submit():
        vessel = Vessel(
            international_number=form.international_number.data,
            call_sign=form.call_sign.data,
            marking=form.marking.data,
            length=form.length.data,
            width=form.width.data,
            engine_power=form.engine_power.data,
            owner_name=form.owner_name.data,
            captain_name=form.captain_name.data
        )

        db.session.add(vessel)
        db.session.commit()

        return redirect(url_for("main.vessels"))

    return render_template("add_vessel.html", form=form, title="Add Vessel")


@bp.route("/admin/vessels")
@login_required
def vessels():
    all_vessels = Vessel.query.all()
    return render_template("vessels.html", vessels=all_vessels, title="Vessel Registry")


@bp.route("/admin/vessels/<int:vessel_id>")
@login_required
def vessel_details(vessel_id):
    vessel = Vessel.query.get_or_404(vessel_id)
    return render_template("vessel_details.html", vessel=vessel, title="Vessel Details")


# -------------------------
# PERMITS
# -------------------------

@bp.route("/admin/permits")
@login_required
def permits():
    query = Permit.query

    # Filters
    status = request.args.get("status")
    vessel_id = request.args.get("vessel_id")
    permit_type = request.args.get("permit_type")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if status and status != "all":
        query = query.filter_by(status=status)

    if vessel_id and vessel_id != "all":
        query = query.filter_by(vessel_id=int(vessel_id))

    if permit_type and permit_type != "all":
        query = query.filter_by(permit_type=permit_type)

    if date_from:
        query = query.filter(Permit.issue_date >= date_from)

    if date_to:
        query = query.filter(Permit.issue_date <= date_to)

    permits = query.order_by(Permit.issue_date.desc()).all()

    # Auto-expire logic
    today = date.today()
    changed = False

    for permit in permits:
        if permit.expiry_date < today and permit.status != "Expired":
            permit.status = "Expired"
            changed = True

    if changed:
        db.session.commit()

    vessels = Vessel.query.all()

    return render_template(
        "permits.html",
        permits=permits,
        vessels=vessels,
        title="Fishing Permits"
    )


@bp.route("/admin/permits/<int:permit_id>")
@login_required
def permit_details(permit_id):
    permit = Permit.query.get_or_404(permit_id)

    # Auto-expire logic
    if permit.expiry_date < date.today() and permit.status != "Expired":
        permit.status = "Expired"
        db.session.commit()

    return render_template("permit_details.html", permit=permit, title="Permit Details")


@bp.route("/admin/permits/add", methods=["GET", "POST"])
@login_required
def add_permit():
    form = PermitForm()
    form.set_vessel_choices()

    if form.validate_on_submit():
        permit = Permit(
            permit_number=form.permit_number.data,
            permit_type=form.permit_type.data,
            vessel_id=form.vessel_id.data,
            issue_date=form.issue_date.data,
            expiry_date=form.expiry_date.data,
            status=form.status.data
        )

        db.session.add(permit)
        db.session.commit()

        flash("Permit created successfully!", "success")
        return redirect(url_for("main.permits"))

    return render_template("add_permit.html", form=form, title="Add Permit")


@bp.route("/admin/permits/<int:permit_id>/edit", methods=["GET", "POST"])
@login_required
def edit_permit(permit_id):
    permit = Permit.query.get_or_404(permit_id)
    form = PermitForm(obj=permit)
    form.set_vessel_choices()

    if form.validate_on_submit():
        permit.permit_number = form.permit_number.data
        permit.permit_type = form.permit_type.data
        permit.vessel_id = form.vessel_id.data
        permit.issue_date = form.issue_date.data
        permit.expiry_date = form.expiry_date.data
        permit.status = form.status.data

        db.session.commit()
        flash("Permit updated successfully!", "success")
        return redirect(url_for("main.permit_details", permit_id=permit.id))

    return render_template("edit_permit.html", form=form, permit=permit, title="Edit Permit")


@bp.route("/admin/permits/<int:permit_id>/delete", methods=["POST"])
@login_required
def delete_permit(permit_id):
    permit = Permit.query.get_or_404(permit_id)

    db.session.delete(permit)
    db.session.commit()

    flash("Permit deleted successfully.", "info")
    return redirect(url_for("main.permits"))


# -------------------------
# PERMIT STATUS ACTIONS
# -------------------------

@bp.route("/admin/permits/<int:permit_id>/activate", methods=["POST"])
@login_required
def activate_permit(permit_id):
    permit = Permit.query.get_or_404(permit_id)
    permit.status = "Active"
    db.session.commit()
    flash("Permit activated.", "success")
    return redirect(url_for("main.permit_details", permit_id=permit.id))


@bp.route("/admin/permits/<int:permit_id>/suspend", methods=["POST"])
@login_required
def suspend_permit(permit_id):
    permit = Permit.query.get_or_404(permit_id)
    permit.status = "Suspended"
    db.session.commit()
    flash("Permit suspended.", "warning")
    return redirect(url_for("main.permit_details", permit_id=permit.id))


@bp.route("/admin/permits/<int:permit_id>/expire", methods=["POST"])
@login_required
def expire_permit(permit_id):
    permit = Permit.query.get_or_404(permit_id)
    permit.status = "Expired"
    db.session.commit()
    flash("Permit marked as expired.", "info")
    return redirect(url_for("main.permit_details", permit_id=permit.id))


# -------------------------
# PERMIT RENEWAL
# -------------------------

@bp.route("/admin/permits/<int:permit_id>/renew", methods=["GET", "POST"])
@login_required
def renew_permit(permit_id):
    permit = Permit.query.get_or_404(permit_id)

    class RenewalForm(FlaskForm):
        new_expiry_date = DateField("New Expiry Date", validators=[DataRequired()])
        submit = SubmitField("Renew Permit")

    form = RenewalForm(new_expiry_date=permit.expiry_date)

    if form.validate_on_submit():
        permit.expiry_date = form.new_expiry_date.data
        permit.status = "Active"
        db.session.commit()

        flash("Permit renewed successfully.", "success")
        return redirect(url_for("main.permit_details", permit_id=permit.id))

    return render_template("renew_permit.html", form=form, permit=permit, title="Renew Permit")
