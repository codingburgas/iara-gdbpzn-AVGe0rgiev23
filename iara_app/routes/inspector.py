# routes/inspector.py
# ---------------------------------------------------------
# All inspector routes:
#   Dashboard, Inspections CRUD, Violations CRUD,
#   Evidence upload/delete, Finalize, PDF export,
#   Inspector Schedule
# ---------------------------------------------------------

import os
from datetime import date, datetime

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, send_file
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from .. import db
from ..models import (
    Inspection, Vessel, Permit, Violation,
    ViolationCode, ViolationSeverity, Evidence, ScheduledInspection
)
from ..decorators import inspector_required
from ..utils import log_action

bp = Blueprint("inspector", __name__)

# ── FILE UPLOAD HELPERS ───────────────────────────────────────────────────────

ALLOWED_EVIDENCE_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Absolute path to the evidence folder (outside the package, at project root)
BASE_DIR             = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EVIDENCE_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "evidence")
os.makedirs(EVIDENCE_UPLOAD_FOLDER, exist_ok=True)


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EVIDENCE_EXTENSIONS


def _inspection_is_locked(inspection):
    """Return True when the inspection can no longer be edited."""
    return inspection.status in ["submitted", "approved"]


# ── INSPECTOR DASHBOARD ───────────────────────────────────────────────────────

@bp.route("/inspector/dashboard")
@login_required
@inspector_required
def inspector_dashboard():
    # Administrators who visit this page need the inspector role check removed
    if current_user.role == "administrator":
        abort(403)

    today = date.today()

    todays_inspections = Inspection.query.filter_by(
        inspector_id=current_user.id,
        date=today
    ).order_by(Inspection.date.desc()).all()

    pending_resolution = Violation.query.join(Inspection).filter(
        Inspection.inspector_id == current_user.id,
        Violation.status == "open"
    ).all()

    corrected_waiting = Violation.query.join(Inspection).filter(
        Inspection.inspector_id == current_user.id,
        Violation.status == "corrected"
    ).all()

    all_violations = Violation.query.join(Inspection).filter(
        Inspection.inspector_id == current_user.id
    ).all()
    violations_missing_evidence = [v for v in all_violations if len(v.evidence) == 0]

    recent_inspections = Inspection.query.filter_by(
        inspector_id=current_user.id
    ).order_by(Inspection.date.desc()).limit(10).all()

    score_trend = [
        insp.final_score for insp in recent_inspections if insp.final_score is not None
    ]

    return render_template(
        "dashboard/inspector_dashboard.html",
        todays_inspections=todays_inspections,
        pending_resolution=pending_resolution,
        corrected_waiting=corrected_waiting,
        violations_missing_evidence=violations_missing_evidence,
        score_trend=score_trend,
        recent_inspections=recent_inspections
    )


# ── INSPECTIONS ───────────────────────────────────────────────────────────────

@bp.route("/inspections")
@login_required
@inspector_required
def inspections_list():
    if current_user.role == "administrator":
        abort(403)  # admin uses their own route
    inspections = Inspection.query.filter_by(
        inspector_id=current_user.id
    ).order_by(Inspection.date.desc()).all()
    return render_template("inspections/list.html", inspections=inspections)


@bp.route("/inspections/create", methods=["GET", "POST"])
@login_required
@inspector_required
def create_inspection():
    if current_user.role == "administrator":
        abort(403)

    vessels = Vessel.query.all()

    if request.method == "POST":
        vessel_id = request.form.get("vessel_id")
        location  = request.form.get("location")
        notes     = request.form.get("notes")

        permit = Permit.query.filter_by(vessel_id=vessel_id)\
            .order_by(Permit.expiry_date.desc()).first()
        permit_status = permit.status if permit else "No Permit"

        new_insp = Inspection(
            vessel_id=vessel_id,
            inspector_id=current_user.id,
            location=location,
            notes=notes,
            permit_status_snapshot=permit_status,
            date=date.today()
        )
        db.session.add(new_insp)
        db.session.commit()
        flash("Inspection created successfully!", "success")
        return redirect(url_for("inspector.inspections_list"))

    return render_template("inspections/create.html", vessels=vessels)


@bp.route("/inspections/<int:inspection_id>")
@login_required
def inspection_details(inspection_id):
    # Both inspectors (own) and admins (any) can view
    if current_user.role not in ["inspector", "administrator"]:
        abort(403)
    if not current_user.is_active:
        abort(403)

    inspection = db.get_or_404(Inspection, inspection_id)

    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        abort(403)

    return render_template("inspections/details.html", inspection=inspection)


@bp.route("/inspections/<int:inspection_id>/finalize", methods=["GET", "POST"])
@login_required
@inspector_required
def finalize_inspection(inspection_id):
    if current_user.role == "administrator":
        abort(403)

    inspection = db.get_or_404(Inspection, inspection_id)

    if inspection.inspector_id != current_user.id:
        abort(403)

    if inspection.status in ["submitted", "approved"]:
        flash("This inspection has already been submitted.", "info")
        return redirect(url_for("inspector.inspection_details", inspection_id=inspection.id))

    if request.method == "POST":
        signature = request.form.get("signature")
        if not signature:
            flash("Signature is required.", "danger")
            return redirect(request.url)

        inspection.status             = "submitted"
        inspection.inspector_signature = signature
        inspection.submitted_at       = datetime.utcnow()

        deduction_map = {"Low": 5, "Medium": 10, "High": 20, "Critical": 40}
        total_deduction = sum(
            deduction_map.get(v.severity, 10) for v in inspection.violations
        )
        inspection.final_score = max(0, 100 - total_deduction)
        db.session.commit()

        flash("Inspection submitted successfully!", "success")
        return redirect(url_for("inspector.inspection_details", inspection_id=inspection.id))

    return render_template("inspections/finalize.html", inspection=inspection)


@bp.route("/inspections/<int:inspection_id>/delete", methods=["POST"])
@login_required
@inspector_required
def delete_inspection(inspection_id):
    if current_user.role == "administrator":
        abort(403)

    inspection = db.get_or_404(Inspection, inspection_id)

    if inspection.inspector_id != current_user.id:
        abort(403)

    if inspection.status in ["submitted", "approved"]:
        flash("Cannot delete a submitted or approved inspection.", "danger")
        return redirect(url_for("inspector.inspection_details", inspection_id=inspection.id))

    # Delete evidence files from disk
    for violation in inspection.violations:
        for evidence in violation.evidence:
            file_path = os.path.join(BASE_DIR, "static", evidence.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)

    db.session.delete(inspection)
    db.session.commit()
    flash("Inspection deleted.", "info")
    return redirect(url_for("inspector.inspections_list"))


@bp.route("/inspections/<int:inspection_id>/pdf")
@login_required
def export_inspection_pdf(inspection_id):
    """Generate and download a PDF report of the inspection."""
    if current_user.role not in ["inspector", "administrator"]:
        abort(403)
    if not current_user.is_active:
        abort(403)

    inspection = db.get_or_404(Inspection, inspection_id)

    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        abort(403)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style    = ParagraphStyle("title",  parent=styles["Title"],   fontSize=18, spaceAfter=4,  textColor=colors.HexColor("#1e293b"))
    subtitle_style = ParagraphStyle("sub",    parent=styles["Normal"],  fontSize=10, textColor=colors.HexColor("#64748b"), spaceAfter=12)
    heading_style  = ParagraphStyle("h2",     parent=styles["Heading2"],fontSize=12, textColor=colors.HexColor("#1e293b"), spaceBefore=14, spaceAfter=6)
    body_style     = ParagraphStyle("body",   parent=styles["Normal"],  fontSize=10, leading=16)
    small_style    = ParagraphStyle("small",  parent=styles["Normal"],  fontSize=8,  textColor=colors.HexColor("#64748b"))

    NAVY  = colors.HexColor("#1e293b")
    LIGHT = colors.HexColor("#f1f5f9")
    RED   = colors.HexColor("#dc2626")
    GREEN = colors.HexColor("#16a34a")

    score       = inspection.final_score if inspection.final_score is not None else inspection.score
    score_color = GREEN if score >= 80 else (colors.HexColor("#d97706") if score >= 60 else RED)

    story = []

    story.append(Paragraph("IARA — Fisheries Inspection Authority", title_style))
    story.append(Paragraph(f"Official Inspection Report  |  Report #{inspection.id:05d}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=12))

    status_color = {
        "draft": "#94a3b8", "submitted": "#3b82f6",
        "approved": "#16a34a", "rejected": "#dc2626"
    }.get(inspection.status, "#94a3b8")

    story.append(Paragraph(
        f'Status: <font color="{status_color}"><b>{inspection.status.upper()}</b></font>'
        f'&nbsp;&nbsp;&nbsp;Score: <b>{score}/100</b>',
        body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Inspection Details", heading_style))
    info_data = [
        ["Vessel Call Sign", inspection.vessel.call_sign,
         "Int'l Number", inspection.vessel.international_number],
        ["Owner", inspection.vessel.owner_name,
         "Captain", inspection.vessel.captain_name],
        ["Date", str(inspection.date),
         "Location", inspection.location or "—"],
        ["Inspector",
         f"{inspection.inspector.first_name} {inspection.inspector.last_name}",
         "Permit at Inspection", inspection.permit_status_snapshot or "—"],
        ["Submitted",
         inspection.submitted_at.strftime("%Y-%m-%d %H:%M") if inspection.submitted_at else "—",
         "Signature", inspection.inspector_signature or "—"],
    ]
    info_table = Table(info_data, colWidths=[3.5*cm, 6*cm, 3.5*cm, 4*cm])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#e2e8f0")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#e2e8f0")),
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",   (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("PADDING",    (0, 0), (-1, -1), 6),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph(f"Violations ({len(inspection.violations)})", heading_style))
    deduction_map = {"Low": 5, "Medium": 10, "High": 20, "Critical": 40}

    if inspection.violations:
        viol_data = [["#", "Code", "Severity", "Description", "Status", "Deduction"]]
        for i, v in enumerate(inspection.violations, 1):
            viol_data.append([
                str(i),
                v.violation_code.code if v.violation_code else "—",
                v.severity or "—",
                (v.description or "—")[:60] + ("…" if v.description and len(v.description) > 60 else ""),
                v.status.upper(),
                f"-{deduction_map.get(v.severity, 10)}"
            ])
        viol_table = Table(viol_data, colWidths=[0.6*cm, 2*cm, 2.2*cm, 7.5*cm, 2.2*cm, 2*cm])
        viol_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("PADDING",       (0, 0), (-1, -1), 5),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("ALIGN",         (0, 0), (0, -1), "CENTER"),
            ("ALIGN",         (-1, 0), (-1, -1), "CENTER"),
        ]))
        story.append(viol_table)
    else:
        story.append(Paragraph("No violations recorded.", body_style))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=8))

    if inspection.notes:
        story.append(Paragraph("Inspector Notes", heading_style))
        story.append(Paragraph(inspection.notes, body_style))
        story.append(Spacer(1, 8))

    story.append(Paragraph("Score Summary", heading_style))
    total_ded  = sum(deduction_map.get(v.severity, 10) for v in inspection.violations)
    score_data = [
        ["Base Score", "Total Deduction", "Final Score"],
        ["100", f"-{total_ded}", str(score)],
    ]
    score_table = Table(score_data, colWidths=[5.5*cm, 5.5*cm, 5.5*cm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 11),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(score_table)

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=6))
    story.append(Paragraph(
        f"Generated by IARA System on {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC  |  "
        f"This is an official document. Unauthorized alteration is prohibited.",
        small_style
    ))

    doc.build(story)
    buf.seek(0)

    log_action("export_pdf", "Inspection", inspection.id)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"inspection_{inspection.id:05d}_report.pdf")


# ── VIOLATIONS ────────────────────────────────────────────────────────────────

@bp.route("/inspections/<int:inspection_id>/violations")
@login_required
@inspector_required
def violations_list(inspection_id):
    if current_user.role == "administrator":
        abort(403)

    inspection = db.get_or_404(Inspection, inspection_id)
    if inspection.inspector_id != current_user.id:
        abort(403)

    return render_template(
        "violations/list.html",
        inspection=inspection,
        violations=inspection.violations
    )


@bp.route("/inspections/<int:inspection_id>/violations/add", methods=["GET", "POST"])
@login_required
@inspector_required
def add_violation(inspection_id):
    if current_user.role == "administrator":
        abort(403)

    inspection = db.get_or_404(Inspection, inspection_id)
    if inspection.inspector_id != current_user.id:
        abort(403)
    if _inspection_is_locked(inspection):
        flash("This inspection is locked and cannot be modified.", "danger")
        return redirect(url_for("inspector.inspection_details", inspection_id=inspection.id))

    violation_codes = ViolationCode.query.all()

    if request.method == "POST":
        code_id     = request.form.get("violation_code_id")
        severity    = request.form.get("severity") or ViolationSeverity.MEDIUM.value
        description = request.form.get("description")

        violation = Violation(
            inspection_id=inspection.id,
            violation_code_id=code_id if code_id != "none" else None,
            severity=severity,
            description=description
        )
        db.session.add(violation)

        deduction_map = {"Low": 5, "Medium": 10, "High": 20, "Critical": 40}
        inspection.score = max(0, inspection.score - deduction_map.get(severity, 10))
        db.session.commit()

        flash("Violation added successfully!", "success")
        return redirect(url_for("inspector.violations_list", inspection_id=inspection.id))

    return render_template(
        "violations/add.html",
        inspection=inspection,
        violation_codes=violation_codes,
        severities=[s.value for s in ViolationSeverity]
    )


@bp.route("/violations/<int:violation_id>/details")
@login_required
@inspector_required
def violation_details(violation_id):
    if current_user.role == "administrator":
        abort(403)

    violation  = db.get_or_404(Violation, violation_id)
    inspection = violation.inspection
    if inspection.inspector_id != current_user.id:
        abort(403)

    return render_template(
        "violations/details.html",
        violation=violation,
        inspection=inspection,
        evidence_items=violation.evidence
    )


@bp.route("/violations/<int:violation_id>/resolve", methods=["POST"])
@login_required
@inspector_required
def resolve_violation(violation_id):
    if current_user.role == "administrator":
        abort(403)

    violation  = db.get_or_404(Violation, violation_id)
    inspection = violation.inspection
    if inspection.inspector_id != current_user.id:
        abort(403)
    if _inspection_is_locked(inspection):
        flash("This inspection is locked and cannot be modified.", "danger")
        return redirect(url_for("inspector.inspection_details", inspection_id=inspection.id))

    notes = request.form.get("resolution_notes")
    files = request.files.getlist("correction_files")

    violation.status           = "corrected"
    violation.resolution_notes = notes
    violation.resolved_at      = datetime.utcnow()

    for file in files:
        if not file.filename:
            continue
        filename = secure_filename(file.filename)
        correction_folder = os.path.join(
            EVIDENCE_UPLOAD_FOLDER, str(inspection.id), str(violation.id), "correction"
        )
        os.makedirs(correction_folder, exist_ok=True)
        file.save(os.path.join(correction_folder, filename))
        evidence = Evidence(
            violation_id=violation.id,
            file_path=f"uploads/evidence/{inspection.id}/{violation.id}/correction/{filename}",
            note="Correction evidence"
        )
        db.session.add(evidence)

    db.session.commit()
    flash("Violation marked as corrected.", "success")
    return redirect(url_for("inspector.violation_details", violation_id=violation.id))


# ── EVIDENCE ──────────────────────────────────────────────────────────────────

@bp.route("/violations/<int:violation_id>/evidence")
@login_required
@inspector_required
def evidence_list(violation_id):
    if current_user.role == "administrator":
        abort(403)

    violation  = db.get_or_404(Violation, violation_id)
    inspection = violation.inspection
    if inspection.inspector_id != current_user.id:
        abort(403)

    return render_template(
        "evidence/list.html",
        violation=violation,
        evidence_items=violation.evidence
    )


@bp.route("/violations/<int:violation_id>/evidence/upload", methods=["GET", "POST"])
@login_required
@inspector_required
def upload_evidence(violation_id):
    if current_user.role == "administrator":
        abort(403)

    violation  = db.get_or_404(Violation, violation_id)
    inspection = violation.inspection
    if inspection.inspector_id != current_user.id:
        abort(403)
    if _inspection_is_locked(inspection):
        flash("This inspection is locked and cannot be modified.", "danger")
        return redirect(url_for("inspector.inspection_details", inspection_id=inspection.id))

    if request.method == "POST":
        files = request.files.getlist("files")
        note  = request.form.get("note")

        if not files or all(f.filename == "" for f in files):
            flash("Please select at least one file.", "danger")
            return redirect(request.url)

        violation_folder = os.path.join(
            EVIDENCE_UPLOAD_FOLDER, str(inspection.id), str(violation.id)
        )
        os.makedirs(violation_folder, exist_ok=True)

        uploaded = 0
        for file in files:
            if not file.filename:
                continue
            if not _allowed_file(file.filename):
                flash(f"Skipped {file.filename}: invalid type. Allowed: png, jpg, jpeg, gif", "warning")
                continue
            filename  = secure_filename(file.filename)
            file.save(os.path.join(violation_folder, filename))
            evidence = Evidence(
                violation_id=violation.id,
                file_path=f"uploads/evidence/{inspection.id}/{violation.id}/{filename}",
                note=note
            )
            db.session.add(evidence)
            uploaded += 1

        if uploaded > 0:
            db.session.commit()
            flash(f"{uploaded} file(s) uploaded successfully!", "success")
        else:
            flash("No valid files were uploaded.", "danger")

        return redirect(url_for("inspector.evidence_list", violation_id=violation.id))

    return render_template("evidence/upload.html", violation=violation)


@bp.route("/evidence/<int:evidence_id>/delete", methods=["POST"])
@login_required
@inspector_required
def delete_evidence(evidence_id):
    if current_user.role == "administrator":
        abort(403)

    evidence   = db.get_or_404(Evidence, evidence_id)
    violation  = evidence.violation
    inspection = violation.inspection
    if inspection.inspector_id != current_user.id:
        abort(403)
    if _inspection_is_locked(inspection):
        flash("This inspection is locked and cannot be modified.", "danger")
        return redirect(url_for("inspector.inspection_details", inspection_id=inspection.id))

    file_path = os.path.join(BASE_DIR, "static", evidence.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(evidence)
    db.session.commit()
    flash("Evidence deleted successfully.", "info")
    return redirect(url_for("inspector.evidence_list", violation_id=violation.id))


# ── INSPECTOR SCHEDULE ────────────────────────────────────────────────────────

@bp.route("/inspector/schedule")
@login_required
@inspector_required
def inspector_schedule():
    if current_user.role == "administrator":
        abort(403)

    schedules = ScheduledInspection.query.filter_by(
        inspector_id=current_user.id
    ).filter(
        ScheduledInspection.status.in_(["pending", "accepted"])
    ).order_by(ScheduledInspection.scheduled_date.asc()).all()

    return render_template("inspections/schedule.html", schedules=schedules, today=date.today())


@bp.route("/inspector/schedule/<int:si_id>/accept", methods=["POST"])
@login_required
@inspector_required
def schedule_accept(si_id):
    if current_user.role == "administrator":
        abort(403)

    si = db.get_or_404(ScheduledInspection, si_id)
    if si.inspector_id != current_user.id:
        abort(403)
    si.status = "accepted"
    db.session.commit()
    flash("Inspection accepted and added to your queue.", "success")
    return redirect(url_for("inspector.inspector_schedule"))


@bp.route("/inspector/schedule/<int:si_id>/start", methods=["POST"])
@login_required
@inspector_required
def schedule_start(si_id):
    """Convert a scheduled inspection slot into a real Inspection (draft status)."""
    if current_user.role == "administrator":
        abort(403)

    si = db.get_or_404(ScheduledInspection, si_id)
    if si.inspector_id != current_user.id:
        abort(403)

    permit = Permit.query.filter_by(vessel_id=si.vessel_id)\
        .order_by(Permit.expiry_date.desc()).first()
    permit_status = permit.status if permit else "No Permit"

    insp = Inspection(
        vessel_id=si.vessel_id,
        inspector_id=current_user.id,
        location=si.location,
        notes=si.notes,
        permit_status_snapshot=permit_status,
        date=date.today()
    )
    db.session.add(insp)
    db.session.flush()  # get insp.id before committing

    si.status        = "completed"
    si.inspection_id = insp.id
    db.session.commit()

    flash("Inspection started from schedule!", "success")
    return redirect(url_for("inspector.inspection_details", inspection_id=insp.id))
