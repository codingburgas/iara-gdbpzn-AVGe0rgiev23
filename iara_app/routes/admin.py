# routes/admin.py
# ---------------------------------------------------------
# All administrator-only routes:
#   Dashboard, User Management, Vessels, Permits,
#   Inspections review, Violations review, Schedule,
#   Audit Log, Inspector Performance, Dashboard data API
# ---------------------------------------------------------

import csv
import os
import uuid
import secrets
from datetime import date, timedelta, datetime
from io import StringIO

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, make_response, jsonify, send_from_directory
)
from flask_login import login_required, current_user

from .. import db
from ..models import (
    User, Vessel, Permit, Inspection, Violation, ScheduledInspection,
    VesselDocument, VesselPhoto, VesselOwnershipHistory
)
from ..forms import (
    VesselForm, PermitForm, CreateUserForm, EditUserForm,
    VesselDocumentUploadForm, VesselPhotoUploadForm, VesselOwnershipForm
)
from ..decorators import admin_required
from ..utils import log_action

# ── PERMISSION HELPERS ────────────────────────────────────────────────────────

def _can_change_role(actor: User, target: User, new_role: str) -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    Rules:
    - An admin cannot change their own role.
    - An admin can change any other user's role freely
      EXCEPT they cannot promote someone to 'administrator'
      through the change-role action (use Create User for that).
    - Deleting a user with existing inspections is blocked.
    """
    if target.id == actor.id:
        return False, "You cannot change your own role."
    if new_role == "administrator" and target.role != "administrator":
        # Allow promoting to admin only through this action — it's a deliberate choice
        pass
    return True, ""

bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@bp.route("/dashboard")
@login_required
@admin_required
def admin_dashboard():
    today = date.today()

    total_permits     = Permit.query.count()
    active_permits    = Permit.query.filter_by(status="Active").count()
    expired_permits   = Permit.query.filter_by(status="Expired").count()
    suspended_permits = Permit.query.filter_by(status="Suspended").count()

    expiring_soon = Permit.query.filter(
        Permit.expiry_date >= today,
        Permit.expiry_date <= today + timedelta(days=30)
    ).count()

    total_vessels = Vessel.query.count()

    return render_template(
        "dashboard/admin_dashboard.html",
        total_permits=total_permits,
        active_permits=active_permits,
        expired_permits=expired_permits,
        suspended_permits=suspended_permits,
        expiring_soon=expiring_soon,
        total_vessels=total_vessels,
        title="Admin Dashboard"
    )


@bp.route("/dashboard/data")
@login_required
@admin_required
def admin_dashboard_data():
    """JSON endpoint used by Chart.js on the admin dashboard."""
    from sqlalchemy import func, extract

    six_months_ago = date.today() - timedelta(days=180)
    monthly = db.session.query(
        extract("month", Inspection.date).label("month"),
        extract("year",  Inspection.date).label("year"),
        func.count(Inspection.id).label("count")
    ).filter(Inspection.date >= six_months_ago)\
     .group_by("year", "month")\
     .order_by("year", "month").all()

    sev_counts = db.session.query(
        Violation.severity, func.count(Violation.id)
    ).group_by(Violation.severity).all()

    permit_statuses = db.session.query(
        Permit.status, func.count(Permit.id)
    ).group_by(Permit.status).all()

    scores = db.session.query(Inspection.final_score, Inspection.date)\
        .filter(Inspection.final_score.isnot(None))\
        .order_by(Inspection.date.desc()).limit(10).all()
    scores = list(reversed(scores))

    return {
        "monthly_inspections": [
            {"label": f"{int(r.month):02d}/{int(r.year)}", "count": r.count}
            for r in monthly
        ],
        "violations_by_severity": [
            {"severity": r[0], "count": r[1]} for r in sev_counts
        ],
        "permit_status": [
            {"status": r[0], "count": r[1]} for r in permit_statuses
        ],
        "score_trend": [
            {"date": str(r[1]), "score": r[0]} for r in scores
        ]
    }


# ── USER MANAGEMENT ───────────────────────────────────────────────────────────

ROLE_LABELS = {
    "administrator": "Administrator",
    "inspector":     "Inspector",
    "fisherman":     "Fisherman",
    "amateur":       "Amateur Fisher",
}

@bp.route("/users")
@login_required
@admin_required
def admin_users():
    # Filters
    role_filter   = request.args.get("role", "")
    status_filter = request.args.get("status", "")
    search_q      = request.args.get("q", "").strip()

    query = User.query

    if role_filter:
        query = query.filter_by(role=role_filter)
    if status_filter == "active":
        query = query.filter_by(is_active=True)
    elif status_filter == "inactive":
        query = query.filter_by(is_active=False)
    if search_q:
        like = f"%{search_q}%"
        query = query.filter(
            db.or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
            )
        )

    users = query.order_by(User.created_at.desc()).all()
    now   = datetime.utcnow()

    # Stats
    stats = {
        "total":         User.query.count(),
        "administrators": User.query.filter_by(role="administrator").count(),
        "inspectors":    User.query.filter_by(role="inspector").count(),
        "fishermen":     User.query.filter_by(role="fisherman").count(),
        "amateurs":      User.query.filter_by(role="amateur").count(),
        "inactive":      User.query.filter_by(is_active=False).count(),
    }

    return render_template(
        "admin/users.html",
        users=users,
        now=now,
        stats=stats,
        role_filter=role_filter,
        status_filter=status_filter,
        search_q=search_q,
    )


@bp.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def admin_create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        # Check email uniqueness
        if User.query.filter_by(email=form.email.data.lower().strip()).first():
            form.email.errors.append("This email address is already registered.")
        else:
            user = User(
                first_name = form.first_name.data.strip(),
                last_name  = form.last_name.data.strip(),
                email      = form.email.data.lower().strip(),
                phone      = form.phone.data.strip(),
                role       = form.role.data,
                is_active  = form.is_active.data,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            log_action("user_created", "User", user.id,
                       f"Role: {user.role}, Created by admin {current_user.id}")
            flash(f"User {user.first_name} {user.last_name} ({user.email}) created successfully.", "success")
            return redirect(url_for("admin.admin_users"))

    return render_template("admin/create_user.html", form=form, title="Create User")


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = db.get_or_404(User, user_id)

    # Prevent self-role-change — self edit of name/phone/email is OK,
    # but role change is blocked for self.
    form = EditUserForm(obj=user)

    if form.validate_on_submit():
        # Block self role change
        if user.id == current_user.id and form.role.data != current_user.role:
            flash("You cannot change your own role.", "danger")
            return redirect(url_for("admin.admin_edit_user", user_id=user.id))

        # Block self deactivation
        if user.id == current_user.id and not form.is_active.data:
            flash("You cannot deactivate your own account.", "danger")
            return redirect(url_for("admin.admin_edit_user", user_id=user.id))

        # Check email uniqueness (allow same user to keep their email)
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing and existing.id != user.id:
            form.email.errors.append("This email address is already in use.")
        else:
            old_role   = user.role
            old_active = user.is_active

            user.first_name = form.first_name.data.strip()
            user.last_name  = form.last_name.data.strip()
            user.email      = form.email.data.lower().strip()
            user.phone      = form.phone.data.strip()
            user.role       = form.role.data
            user.is_active  = form.is_active.data

            db.session.commit()

            # Detailed audit log
            changes = []
            if old_role != user.role:
                changes.append(f"role: {old_role} → {user.role}")
            if old_active != user.is_active:
                changes.append(f"active: {old_active} → {user.is_active}")
            log_action("user_edited", "User", user.id,
                       f"Changes: {', '.join(changes) if changes else 'profile details'}")

            flash(f"User {user.email} updated successfully.", "success")
            return redirect(url_for("admin.admin_users"))

    # For self — disable role field in template via context flag
    is_self = (user.id == current_user.id)
    return render_template(
        "admin/edit_user.html",
        form=form, user=user, is_self=is_self, title="Edit User"
    )


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = db.get_or_404(User, user_id)

    # Self-delete guard
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("admin.admin_users"))

    # Referential integrity: block if user has inspections
    if user.inspections:
        flash(
            f"Cannot delete {user.email}: they have {len(user.inspections)} inspection record(s). "
            "Deactivate the account instead.",
            "danger"
        )
        return redirect(url_for("admin.admin_users"))

    # Block deletion of the last administrator
    if user.role == "administrator":
        admin_count = User.query.filter_by(role="administrator", is_active=True).count()
        if admin_count <= 1:
            flash("Cannot delete the last active administrator account.", "danger")
            return redirect(url_for("admin.admin_users"))

    log_action("user_deleted", "User", user.id,
               f"Deleted user {user.email} (role: {user.role})")
    db.session.delete(user)
    db.session.commit()
    flash(f"User {user.email} has been permanently deleted.", "info")
    return redirect(url_for("admin.admin_users"))


@bp.route("/users/<int:user_id>/change-role", methods=["POST"])
@login_required
@admin_required
def admin_change_role(user_id):
    user     = db.get_or_404(User, user_id)
    new_role = request.form.get("new_role", "").strip()

    valid_roles = ["administrator", "inspector", "fisherman", "amateur"]
    if new_role not in valid_roles:
        flash("Invalid role selected.", "danger")
        return redirect(url_for("admin.admin_users"))

    allowed, reason = _can_change_role(current_user, user, new_role)
    if not allowed:
        flash(reason, "danger")
        return redirect(url_for("admin.admin_users"))

    # Block removing last admin
    if user.role == "administrator" and new_role != "administrator":
        admin_count = User.query.filter_by(role="administrator", is_active=True).count()
        if admin_count <= 1:
            flash("Cannot change role: this is the last active administrator.", "danger")
            return redirect(url_for("admin.admin_users"))

    old_role   = user.role
    user.role  = new_role
    db.session.commit()
    log_action("user_role_changed", "User", user.id,
               f"Role: {old_role} → {new_role}")
    flash(
        f"{user.first_name} {user.last_name}'s role changed from "
        f"{ROLE_LABELS.get(old_role, old_role)} to {ROLE_LABELS.get(new_role, new_role)}.",
        "success"
    )
    return redirect(url_for("admin.admin_users"))


@bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def admin_toggle_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "danger")
        return redirect(url_for("admin.admin_users"))
    user.is_active = not user.is_active
    db.session.commit()
    state = "activated" if user.is_active else "deactivated"
    log_action(f"user_{state}", "User", user.id)
    flash(f"User {user.email} has been {state}.", "success")
    return redirect(url_for("admin.admin_users"))


@bp.route("/users/<int:user_id>/unlock", methods=["POST"])
@login_required
@admin_required
def admin_unlock_user(user_id):
    user = db.get_or_404(User, user_id)
    user.failed_logins = 0
    user.locked_until  = None
    db.session.commit()
    log_action("user_unlocked", "User", user.id)
    flash(f"Account for {user.email} has been unlocked.", "success")
    return redirect(url_for("admin.admin_users"))


@bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def admin_reset_user_password(user_id):
    user = db.get_or_404(User, user_id)
    temp_password = secrets.token_urlsafe(10)
    user.set_password(temp_password)
    user.failed_logins = 0
    user.locked_until  = None
    db.session.commit()
    log_action("admin_password_reset", "User", user.id)
    flash(f"Password for {user.email} reset to: {temp_password}  (share securely)", "warning")
    return redirect(url_for("admin.admin_users"))




# ─── Upload directory helpers ─────────────────────────────────────────────────

def _upload_dir():
    """Return the project-level uploads/ directory, creating subdirs as needed."""
    from flask import current_app
    base = os.path.join(current_app.root_path, "..", "uploads")
    for sub in ("vessel_docs", "vessel_photos"):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    return os.path.abspath(base)


def _save_upload(file_storage, subfolder, allowed_exts):
    """Save a FileStorage object to uploads/<subfolder>/ with a UUID name. Returns filename."""
    ext = file_storage.filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed_exts:
        raise ValueError(f"Extension .{ext} not allowed")
    filename = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(_upload_dir(), subfolder, filename)
    file_storage.save(dest)
    return filename


# ── VESSELS ───────────────────────────────────────────────────────────────────

@bp.route("/vessels")
@login_required
@admin_required
def vessels():
    q           = request.args.get("q", "").strip()
    status_f    = request.args.get("status", "")
    port_f      = request.args.get("port", "").strip()
    page        = request.args.get("page", 1, type=int)
    per_page    = 15

    query = Vessel.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Vessel.call_sign.ilike(like),
                Vessel.international_number.ilike(like),
                Vessel.name_bg.ilike(like),
                Vessel.name_en.ilike(like),
                Vessel.owner_name.ilike(like),
                Vessel.marking.ilike(like),
            )
        )
    if status_f:
        query = query.filter_by(status=status_f)
    if port_f:
        query = query.filter(Vessel.port_registration.ilike(f"%{port_f}%"))

    pagination  = query.order_by(Vessel.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    all_vessels = pagination.items

    # Unique ports for filter dropdown
    ports = [r[0] for r in db.session.query(Vessel.port_registration)
             .filter(Vessel.port_registration.isnot(None))
             .distinct().all()]

    return render_template(
        "vessels/vessels.html",
        vessels=all_vessels,
        pagination=pagination,
        q=q, status_f=status_f, port_f=port_f,
        ports=ports,
        title="Vessel Registry"
    )


@bp.route("/vessels/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_vessel():
    form = VesselForm()
    duplicate_warning = None

    if form.validate_on_submit():
        # Duplicate detection
        dup_number = Vessel.query.filter_by(
            international_number=form.international_number.data.strip()
        ).first()
        dup_sign = Vessel.query.filter(
            db.func.lower(Vessel.call_sign) == form.call_sign.data.strip().lower()
        ).first()

        if dup_number:
            flash(f"⚠ Vessel with International Number '{form.international_number.data}' already exists (#{dup_number.id}). Verify before saving.", "warning")
        elif dup_sign:
            flash(f"⚠ Vessel with Call Sign '{form.call_sign.data}' already exists (#{dup_sign.id}). Verify before saving.", "warning")
        else:
            vessel = Vessel(
                international_number=form.international_number.data.strip(),
                call_sign=form.call_sign.data.strip(),
                marking=form.marking.data.strip(),
                name_bg=form.name_bg.data.strip() if form.name_bg.data else None,
                name_en=form.name_en.data.strip() if form.name_en.data else None,
                port_registration=form.port_registration.data.strip() if form.port_registration.data else None,
                registration_date=form.registration_date.data,
                status=form.status.data,
                length=form.length.data,
                width=form.width.data,
                gross_tonnage=form.gross_tonnage.data,
                engine_power=form.engine_power.data,
                owner_name=form.owner_name.data.strip(),
                owner_egn=form.owner_egn.data.strip() if form.owner_egn.data else None,
                captain_name=form.captain_name.data.strip(),
            )
            db.session.add(vessel)
            db.session.flush()  # get vessel.id before commit

            # Record initial ownership
            if vessel.owner_name:
                history = VesselOwnershipHistory(
                    vessel_id=vessel.id,
                    owner_name=vessel.owner_name,
                    owner_egn=vessel.owner_egn,
                    from_date=vessel.registration_date or date.today(),
                    recorded_by_id=current_user.id,
                )
                db.session.add(history)

            db.session.commit()
            log_action("vessel_created", "Vessel", vessel.id,
                       f"Call sign: {vessel.call_sign}, Status: {vessel.status}")
            flash(f"Vessel '{vessel.call_sign}' registered successfully!", "success")
            return redirect(url_for("admin.vessel_details", vessel_id=vessel.id))

    return render_template("vessels/add_vessel.html", form=form, title="Register Vessel")


@bp.route("/vessels/<int:vessel_id>")
@login_required
@admin_required
def vessel_details(vessel_id):
    vessel   = db.get_or_404(Vessel, vessel_id)
    doc_form   = VesselDocumentUploadForm()
    photo_form = VesselPhotoUploadForm()
    own_form   = VesselOwnershipForm()
    active_tab = request.args.get("tab", "info")
    return render_template(
        "vessels/vessel_details.html",
        vessel=vessel,
        doc_form=doc_form,
        photo_form=photo_form,
        own_form=own_form,
        active_tab=active_tab,
        title=f"Vessel — {vessel.call_sign}"
    )


@bp.route("/vessels/<int:vessel_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_vessel(vessel_id):
    vessel = db.get_or_404(Vessel, vessel_id)
    form   = VesselForm(obj=vessel)

    if form.validate_on_submit():
        # Duplicate check (exclude self)
        dup = Vessel.query.filter(
            Vessel.international_number == form.international_number.data.strip(),
            Vessel.id != vessel.id
        ).first()
        if dup:
            flash(f"⚠ Another vessel already uses International Number '{form.international_number.data}' (#{dup.id}).", "warning")
        else:
            old_status = vessel.status
            vessel.international_number = form.international_number.data.strip()
            vessel.call_sign            = form.call_sign.data.strip()
            vessel.marking              = form.marking.data.strip()
            vessel.name_bg              = form.name_bg.data.strip() if form.name_bg.data else None
            vessel.name_en              = form.name_en.data.strip() if form.name_en.data else None
            vessel.port_registration    = form.port_registration.data.strip() if form.port_registration.data else None
            vessel.registration_date    = form.registration_date.data
            vessel.status               = form.status.data
            vessel.length               = form.length.data
            vessel.width                = form.width.data
            vessel.gross_tonnage        = form.gross_tonnage.data
            vessel.engine_power         = form.engine_power.data
            vessel.owner_name           = form.owner_name.data.strip()
            vessel.owner_egn            = form.owner_egn.data.strip() if form.owner_egn.data else None
            vessel.captain_name         = form.captain_name.data.strip()

            # Auto-expire permits when vessel is scrapped
            if old_status != "Scrapped" and vessel.status == "Scrapped":
                for permit in vessel.permits:
                    if permit.status == "Active":
                        permit.status = "Expired"
                flash("All active permits have been expired because the vessel was scrapped.", "warning")

            db.session.commit()
            log_action("vessel_edited", "Vessel", vessel.id,
                       f"Status: {old_status} → {vessel.status}")
            flash(f"Vessel '{vessel.call_sign}' updated successfully!", "success")
            return redirect(url_for("admin.vessel_details", vessel_id=vessel.id))

    return render_template("vessels/edit_vessel.html", form=form, vessel=vessel, title="Edit Vessel")


@bp.route("/vessels/<int:vessel_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_vessel(vessel_id):
    vessel = db.get_or_404(Vessel, vessel_id)

    if vessel.inspections:
        flash(
            f"Cannot delete '{vessel.call_sign}': it has {len(vessel.inspections)} inspection record(s). "
            "Change its status to Scrapped instead.",
            "danger"
        )
        return redirect(url_for("admin.vessel_details", vessel_id=vessel.id))

    if vessel.permits:
        flash(
            f"Cannot delete '{vessel.call_sign}': it has {len(vessel.permits)} permit record(s). "
            "Remove them first or mark the vessel as Scrapped.",
            "danger"
        )
        return redirect(url_for("admin.vessel_details", vessel_id=vessel.id))

    call_sign = vessel.call_sign
    log_action("vessel_deleted", "Vessel", vessel.id, f"Call sign: {call_sign}")
    db.session.delete(vessel)
    db.session.commit()
    flash(f"Vessel '{call_sign}' has been permanently deleted.", "info")
    return redirect(url_for("admin.vessels"))


@bp.route("/vessels/<int:vessel_id>/status", methods=["POST"])
@login_required
@admin_required
def vessel_change_status(vessel_id):
    vessel     = db.get_or_404(Vessel, vessel_id)
    new_status = request.form.get("status", "").strip()
    valid      = ["Active", "Suspended", "Scrapped"]
    if new_status not in valid:
        flash("Invalid status value.", "danger")
        return redirect(url_for("admin.vessel_details", vessel_id=vessel.id))

    old_status    = vessel.status
    vessel.status = new_status

    if old_status != "Scrapped" and new_status == "Scrapped":
        for permit in vessel.permits:
            if permit.status == "Active":
                permit.status = "Expired"
        flash("All active permits have been expired because the vessel was scrapped.", "warning")

    db.session.commit()
    log_action("vessel_status_changed", "Vessel", vessel.id,
               f"{old_status} → {new_status}")
    flash(f"Vessel status changed to '{new_status}'.", "success")
    return redirect(url_for("admin.vessel_details", vessel_id=vessel.id))


# ── VESSEL — INSPECTION HISTORY (keep for back-compat) ───────────────────────

@bp.route("/vessels/<int:vessel_id>/inspections")
@login_required
@admin_required
def vessel_inspection_history(vessel_id):
    vessel = db.get_or_404(Vessel, vessel_id)
    inspections = Inspection.query.filter_by(
        vessel_id=vessel.id
    ).order_by(Inspection.date.desc()).all()

    history = []
    for insp in inspections:
        severity_counts = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
        evidence_count  = 0
        for v in insp.violations:
            if v.severity in severity_counts:
                severity_counts[v.severity] += 1
            evidence_count += len(v.evidence)
        history.append({
            "inspection":       insp,
            "total_violations": len(insp.violations),
            "severity_counts":  severity_counts,
            "evidence_count":   evidence_count,
        })

    return render_template(
        "vessels/inspection_history.html",
        vessel=vessel,
        history=history
    )


@bp.route("/vessels/<int:vessel_id>/qr-print")
@login_required
@admin_required
def vessel_qr_print(vessel_id):
    vessel = db.get_or_404(Vessel, vessel_id)
    active_permit = Permit.query.filter_by(vessel_id=vessel.id, status="Active").first()
    return render_template(
        "admin/vessel_qr_print.html",
        vessel=vessel,
        active_permit=active_permit
    )


# ── VESSEL DOCUMENTS ──────────────────────────────────────────────────────────

@bp.route("/vessels/<int:vessel_id>/documents/upload", methods=["POST"])
@login_required
@admin_required
def vessel_upload_document(vessel_id):
    vessel = db.get_or_404(Vessel, vessel_id)
    form   = VesselDocumentUploadForm()
    if form.validate_on_submit():
        try:
            filename = _save_upload(
                form.file.data, "vessel_docs",
                {"pdf", "doc", "docx", "jpg", "jpeg", "png"}
            )
            doc = VesselDocument(
                vessel_id=vessel.id,
                uploaded_by_id=current_user.id,
                doc_type=form.doc_type.data,
                filename=filename,
                original_name=form.file.data.filename,
                notes=form.notes.data,
            )
            db.session.add(doc)
            db.session.commit()
            log_action("vessel_doc_uploaded", "VesselDocument", doc.id,
                       f"Vessel {vessel.id}: {doc.original_name}")
            flash("Document uploaded successfully.", "success")
        except Exception as e:
            flash(f"Upload failed: {e}", "danger")
    else:
        for field, errs in form.errors.items():
            flash(f"{field}: {', '.join(errs)}", "danger")
    return redirect(url_for("admin.vessel_details", vessel_id=vessel.id, tab="documents"))


@bp.route("/vessels/<int:vessel_id>/documents/<int:doc_id>/delete", methods=["POST"])
@login_required
@admin_required
def vessel_delete_document(vessel_id, doc_id):
    doc = db.get_or_404(VesselDocument, doc_id)
    if doc.vessel_id != vessel_id:
        abort(404)
    try:
        path = os.path.join(_upload_dir(), "vessel_docs", doc.filename)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
    db.session.delete(doc)
    db.session.commit()
    flash("Document deleted.", "info")
    return redirect(url_for("admin.vessel_details", vessel_id=vessel_id, tab="documents"))


@bp.route("/uploads/vessel_docs/<path:filename>")
@login_required
@admin_required
def serve_vessel_doc(filename):
    folder = os.path.join(_upload_dir(), "vessel_docs")
    return send_from_directory(folder, filename)


# ── VESSEL PHOTOS ─────────────────────────────────────────────────────────────

@bp.route("/vessels/<int:vessel_id>/photos/upload", methods=["POST"])
@login_required
@admin_required
def vessel_upload_photo(vessel_id):
    vessel = db.get_or_404(Vessel, vessel_id)
    form   = VesselPhotoUploadForm()
    if form.validate_on_submit():
        try:
            filename = _save_upload(
                form.file.data, "vessel_photos",
                {"jpg", "jpeg", "png", "webp"}
            )
            if form.is_primary.data:
                # Unset existing primary
                VesselPhoto.query.filter_by(vessel_id=vessel.id, is_primary=True)\
                    .update({"is_primary": False})
            photo = VesselPhoto(
                vessel_id=vessel.id,
                uploaded_by_id=current_user.id,
                filename=filename,
                caption=form.caption.data,
                is_primary=form.is_primary.data,
            )
            db.session.add(photo)
            db.session.commit()
            log_action("vessel_photo_uploaded", "VesselPhoto", photo.id,
                       f"Vessel {vessel.id}")
            flash("Photo uploaded successfully.", "success")
        except Exception as e:
            flash(f"Upload failed: {e}", "danger")
    else:
        for field, errs in form.errors.items():
            flash(f"{field}: {', '.join(errs)}", "danger")
    return redirect(url_for("admin.vessel_details", vessel_id=vessel.id, tab="photos"))


@bp.route("/vessels/<int:vessel_id>/photos/<int:photo_id>/delete", methods=["POST"])
@login_required
@admin_required
def vessel_delete_photo(vessel_id, photo_id):
    photo = db.get_or_404(VesselPhoto, photo_id)
    if photo.vessel_id != vessel_id:
        abort(404)
    try:
        path = os.path.join(_upload_dir(), "vessel_photos", photo.filename)
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
    db.session.delete(photo)
    db.session.commit()
    flash("Photo deleted.", "info")
    return redirect(url_for("admin.vessel_details", vessel_id=vessel_id, tab="photos"))


@bp.route("/vessels/<int:vessel_id>/photos/<int:photo_id>/set-primary", methods=["POST"])
@login_required
@admin_required
def vessel_set_primary_photo(vessel_id, photo_id):
    photo = db.get_or_404(VesselPhoto, photo_id)
    if photo.vessel_id != vessel_id:
        abort(404)
    VesselPhoto.query.filter_by(vessel_id=vessel_id, is_primary=True)\
        .update({"is_primary": False})
    photo.is_primary = True
    db.session.commit()
    flash("Primary photo updated.", "success")
    return redirect(url_for("admin.vessel_details", vessel_id=vessel_id, tab="photos"))


@bp.route("/uploads/vessel_photos/<path:filename>")
@login_required
@admin_required
def serve_vessel_photo(filename):
    folder = os.path.join(_upload_dir(), "vessel_photos")
    return send_from_directory(folder, filename)


# ── VESSEL OWNERSHIP HISTORY ──────────────────────────────────────────────────

@bp.route("/vessels/<int:vessel_id>/ownership/add", methods=["POST"])
@login_required
@admin_required
def vessel_add_ownership(vessel_id):
    vessel = db.get_or_404(Vessel, vessel_id)
    form   = VesselOwnershipForm()
    if form.validate_on_submit():
        entry = VesselOwnershipHistory(
            vessel_id=vessel.id,
            recorded_by_id=current_user.id,
            owner_name=form.owner_name.data.strip(),
            owner_egn=form.owner_egn.data.strip() if form.owner_egn.data else None,
            from_date=form.from_date.data,
            to_date=form.to_date.data,
            notes=form.notes.data,
        )
        # Close previous open entry
        prev = VesselOwnershipHistory.query.filter_by(
            vessel_id=vessel.id, to_date=None
        ).first()
        if prev and prev.id != entry.id:
            prev.to_date = form.from_date.data

        # Update vessel current owner
        vessel.owner_name = form.owner_name.data.strip()
        vessel.owner_egn  = form.owner_egn.data.strip() if form.owner_egn.data else None

        db.session.add(entry)
        db.session.commit()
        log_action("vessel_ownership_added", "VesselOwnershipHistory", entry.id,
                   f"Vessel {vessel.id}: new owner {entry.owner_name}")
        flash("Ownership transfer recorded.", "success")
    else:
        for field, errs in form.errors.items():
            flash(f"{field}: {', '.join(errs)}", "danger")
    return redirect(url_for("admin.vessel_details", vessel_id=vessel.id, tab="ownership"))


# ── PERMITS ───────────────────────────────────────────────────────────────────

@bp.route("/permits")
@login_required
@admin_required
def permits():
    page       = request.args.get("page", 1, type=int)
    per_page   = 10
    query      = Permit.query

    status      = request.args.get("status")
    vessel_id   = request.args.get("vessel_id")
    permit_type = request.args.get("permit_type")
    date_from   = request.args.get("date_from")
    date_to     = request.args.get("date_to")

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

    permits_page = query.order_by(Permit.issue_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Auto-expire overdue permits
    today   = date.today()
    changed = False
    for permit in permits_page.items:
        if permit.expiry_date < today and permit.status != "Expired":
            permit.status = "Expired"
            changed = True
    if changed:
        db.session.commit()

    return render_template(
        "permits/permits.html",
        permits=permits_page,
        vessels=Vessel.query.all(),
        title="Fishing Permits"
    )


@bp.route("/permits/<int:permit_id>")
@login_required
@admin_required
def permit_details(permit_id):
    permit = db.get_or_404(Permit, permit_id)
    if permit.expiry_date < date.today() and permit.status != "Expired":
        permit.status = "Expired"
        db.session.commit()
    return render_template("permits/permit_details.html", permit=permit, title="Permit Details")


@bp.route("/permits/add", methods=["GET", "POST"])
@login_required
@admin_required
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
        return redirect(url_for("admin.permits"))
    return render_template("permits/add_permit.html", form=form, title="Add Permit")


@bp.route("/permits/<int:permit_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_permit(permit_id):
    permit = db.get_or_404(Permit, permit_id)
    form   = PermitForm(obj=permit)
    form.set_vessel_choices()
    if form.validate_on_submit():
        permit.permit_number = form.permit_number.data
        permit.permit_type   = form.permit_type.data
        permit.vessel_id     = form.vessel_id.data
        permit.issue_date    = form.issue_date.data
        permit.expiry_date   = form.expiry_date.data
        permit.status        = form.status.data
        db.session.commit()
        flash("Permit updated successfully!", "success")
        return redirect(url_for("admin.permit_details", permit_id=permit.id))
    return render_template("permits/edit_permit.html", form=form, permit=permit, title="Edit Permit")


@bp.route("/permits/<int:permit_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_permit(permit_id):
    permit = db.get_or_404(Permit, permit_id)
    db.session.delete(permit)
    db.session.commit()
    flash("Permit deleted successfully.", "info")
    return redirect(url_for("admin.permits"))


@bp.route("/permits/<int:permit_id>/activate", methods=["POST"])
@login_required
@admin_required
def activate_permit(permit_id):
    permit = db.get_or_404(Permit, permit_id)
    permit.status = "Active"
    db.session.commit()
    flash("Permit activated successfully.", "success")
    return redirect(url_for("admin.permit_details", permit_id=permit.id))


@bp.route("/permits/<int:permit_id>/suspend", methods=["POST"])
@login_required
@admin_required
def suspend_permit(permit_id):
    permit = db.get_or_404(Permit, permit_id)
    permit.status = "Suspended"
    db.session.commit()
    flash("Permit suspended.", "warning")
    return redirect(url_for("admin.permit_details", permit_id=permit.id))


@bp.route("/permits/<int:permit_id>/expire", methods=["POST"])
@login_required
@admin_required
def expire_permit(permit_id):
    permit = db.get_or_404(Permit, permit_id)
    permit.status = "Expired"
    db.session.commit()
    flash("Permit marked as expired.", "info")
    return redirect(url_for("admin.permit_details", permit_id=permit.id))


@bp.route("/permits/<int:permit_id>/renew", methods=["GET", "POST"])
@login_required
@admin_required
def renew_permit(permit_id):
    permit = db.get_or_404(Permit, permit_id)
    if request.method == "POST":
        new_expiry_str = request.form.get("new_expiry_date")
        if not new_expiry_str:
            flash("Please provide a new expiry date.", "danger")
            return redirect(request.url)
        try:
            new_expiry = date.fromisoformat(new_expiry_str)
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(request.url)
        if new_expiry <= date.today():
            flash("New expiry date must be in the future.", "danger")
            return redirect(request.url)
        permit.expiry_date = new_expiry
        permit.status      = "Active"
        db.session.commit()
        flash(f"Permit renewed until {new_expiry}.", "success")
        return redirect(url_for("admin.permit_details", permit_id=permit.id))
    return render_template("permits/renew_permit.html", permit=permit, today=date.today().isoformat())


@bp.route("/permits/export")
@login_required
@admin_required
def export_permits():
    """Download a CSV of permits (with the same filters as the list view)."""
    query = Permit.query

    status      = request.args.get("status")
    vessel_id   = request.args.get("vessel_id")
    permit_type = request.args.get("permit_type")
    date_from   = request.args.get("date_from")
    date_to     = request.args.get("date_to")

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

    all_permits = query.order_by(Permit.issue_date.desc()).all()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Permit Number", "Permit Type", "Vessel Call Sign",
                     "Issue Date", "Expiry Date", "Status"])
    for p in all_permits:
        writer.writerow([
            p.permit_number, p.permit_type, p.vessel.call_sign,
            p.issue_date, p.expiry_date, p.status
        ])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=permits.csv"
    response.headers["Content-Type"] = "text/csv"
    return response


# ── INSPECTIONS (ADMIN VIEW) ──────────────────────────────────────────────────

@bp.route("/inspections")
@login_required
@admin_required
def admin_inspections():
    inspections = Inspection.query.order_by(Inspection.date.desc()).all()
    return render_template("admin/inspections_list.html", inspections=inspections)


@bp.route("/inspections/<int:inspection_id>/detail")
@login_required
@admin_required
def admin_inspection_detail(inspection_id):
    inspection = db.get_or_404(Inspection, inspection_id)
    return render_template("admin/inspection_detail.html", inspection=inspection)


@bp.route("/inspections/<int:inspection_id>/reject", methods=["POST"])
@login_required
@admin_required
def admin_reject_inspection(inspection_id):
    inspection = db.get_or_404(Inspection, inspection_id)
    inspection.status      = "rejected"
    inspection.rejected_at = datetime.utcnow()
    db.session.commit()
    flash("Inspection rejected.", "warning")
    return redirect(url_for("admin.admin_inspections"))


@bp.route("/inspections/<int:inspection_id>/override_score", methods=["POST"])
@login_required
@admin_required
def admin_override_score(inspection_id):
    inspection = db.get_or_404(Inspection, inspection_id)
    new_score  = int(request.form.get("new_score", 0))
    inspection.final_score = new_score
    inspection.status      = "approved"
    inspection.approved_at = datetime.utcnow()
    db.session.commit()
    flash("Inspection score overridden and approved.", "success")
    return redirect(url_for("admin.admin_inspections"))


# ── VIOLATIONS (ADMIN VIEW) ───────────────────────────────────────────────────

@bp.route("/violations")
@login_required
@admin_required
def admin_violations():
    violations = Violation.query.order_by(Violation.created_at.desc()).all()
    return render_template("admin/violations.html", violations=violations)


@bp.route("/violation/<int:violation_id>/evidence")
@login_required
@admin_required
def admin_view_evidence(violation_id):
    violation = db.get_or_404(Violation, violation_id)
    return render_template("admin/evidence_viewer.html", violation=violation)


@bp.route("/violation/<int:violation_id>/approve", methods=["POST"])
@login_required
@admin_required
def admin_approve_violation(violation_id):
    violation = db.get_or_404(Violation, violation_id)
    violation.status      = "approved"
    violation.resolved_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("admin.admin_violations"))


@bp.route("/violation/<int:violation_id>/reject", methods=["POST"])
@login_required
@admin_required
def admin_reject_violation(violation_id):
    violation = db.get_or_404(Violation, violation_id)
    violation.status = "rejected"
    db.session.commit()
    return redirect(url_for("admin.admin_violations"))


# ── INSPECTOR PERFORMANCE ─────────────────────────────────────────────────────

@bp.route("/inspectors/performance")
@login_required
@admin_required
def admin_inspector_performance():
    inspectors  = User.query.filter_by(role="inspector").all()
    performance = []
    for inspector in inspectors:
        inspections = Inspection.query.filter_by(inspector_id=inspector.id).all()
        total       = len(inspections)
        scores      = [i.final_score for i in inspections if i.final_score is not None]
        avg_score   = (sum(scores) / len(scores)) if scores else None
        performance.append({
            "inspector":         inspector,
            "total_inspections": total,
            "avg_score":         avg_score,
        })
    return render_template("admin/inspector_performance.html", performance=performance)


# ── SCHEDULE ──────────────────────────────────────────────────────────────────

@bp.route("/schedule")
@login_required
@admin_required
def schedule_list():
    schedules  = ScheduledInspection.query.order_by(
        ScheduledInspection.scheduled_date.asc()
    ).all()
    inspectors = User.query.filter_by(role="inspector").all()
    vessels    = Vessel.query.all()
    return render_template(
        "admin/schedule.html",
        schedules=schedules,
        inspectors=inspectors,
        vessels=vessels,
        today=date.today()
    )


@bp.route("/schedule/create", methods=["POST"])
@login_required
@admin_required
def schedule_create():
    vessel_id    = request.form.get("vessel_id")
    inspector_id = request.form.get("inspector_id")
    sched_date   = request.form.get("scheduled_date")
    sched_time   = request.form.get("scheduled_time", "09:00")
    location     = request.form.get("location")
    notes        = request.form.get("notes")

    if not all([vessel_id, inspector_id, sched_date]):
        flash("Vessel, Inspector and Date are required.", "danger")
        return redirect(url_for("admin.schedule_list"))

    si = ScheduledInspection(
        vessel_id=int(vessel_id),
        inspector_id=int(inspector_id),
        scheduled_date=date.fromisoformat(sched_date),
        scheduled_time=sched_time,
        location=location,
        notes=notes,
        created_by_id=current_user.id,
        status="pending"
    )
    db.session.add(si)
    db.session.commit()
    log_action(
        "schedule_inspection", "ScheduledInspection", si.id,
        f"Vessel {vessel_id} → Inspector {inspector_id} on {sched_date}"
    )
    flash("Inspection scheduled successfully!", "success")
    return redirect(url_for("admin.schedule_list"))


@bp.route("/schedule/<int:si_id>/cancel", methods=["POST"])
@login_required
@admin_required
def schedule_cancel(si_id):
    si = db.get_or_404(ScheduledInspection, si_id)
    si.status = "cancelled"
    db.session.commit()
    flash("Scheduled inspection cancelled.", "warning")
    return redirect(url_for("admin.schedule_list"))


# ── AUDIT LOG ─────────────────────────────────────────────────────────────────

@bp.route("/audit-log")
@login_required
@admin_required
def audit_log():
    from ..models import AuditLog
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_log.html", logs=logs)
