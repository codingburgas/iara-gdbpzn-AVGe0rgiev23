# routes/fisherman.py
# ---------------------------------------------------------
# Dashboards for fisherman and amateur roles.
# ---------------------------------------------------------

from datetime import date

from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user

from ..models import Vessel, Permit, Inspection
from ..decorators import fisherman_required

bp = Blueprint("fisherman", __name__)


@bp.route("/fisherman/dashboard")
@login_required
@fisherman_required
def fisherman_dashboard():
    # Only the 'fisherman' role sees this page
    if current_user.role not in ["fisherman"]:
        abort(403)

    # Try to find a vessel linked to this user's registration number
    vessel = None
    if current_user.vessel_registration:
        vessel = Vessel.query.filter_by(
            international_number=current_user.vessel_registration
        ).first()

    active_permit   = None
    last_inspection = None
    open_violations = []
    expiring_soon   = False

    if vessel:
        active_permit = Permit.query.filter_by(
            vessel_id=vessel.id, status="Active"
        ).first()

        if active_permit:
            expiring_soon = active_permit.days_until_expiry() <= 30

        last_inspection = Inspection.query.filter_by(vessel_id=vessel.id)\
            .order_by(Inspection.date.desc()).first()

        if last_inspection:
            open_violations = [v for v in last_inspection.violations if v.status == "open"]

    return render_template(
        "dashboard/fisherman_dashboard.html",
        vessel=vessel,
        active_permit=active_permit,
        last_inspection=last_inspection,
        open_violations=open_violations,
        expiring_soon=expiring_soon
    )


@bp.route("/amateur/dashboard")
@login_required
@fisherman_required
def amateur_dashboard():
    # Only the 'amateur' role sees this page
    if current_user.role not in ["amateur"]:
        abort(403)
    return render_template("dashboard/amateur_dashboard.html")
