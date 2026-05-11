# iara_app/routes/alerts.py
# ---------------------------------------------------------
# Module 13 — Smart Alerts & Notifications
# Blueprint: alerts  (url_prefix="/alerts")
# ---------------------------------------------------------

from flask import (Blueprint, render_template, redirect, url_for,
                   request, jsonify, flash, abort)
from flask_login import login_required, current_user

from .. import db
from ..models import Alert, AlertRule, UserAlertPreference

bp = Blueprint("alerts", __name__, url_prefix="/alerts")


# ── Helpers ────────────────────────────────────────────────────────────────

def _unread_count():
    return Alert.query.filter_by(user_id=current_user.id, is_read=False).count()


RULE_TYPE_CHOICES = [
    ("permit_expiry",    "Permit Expiry"),
    ("high_risk",        "High-Risk Vessel"),
    ("unusual_activity", "Unusual Activity"),
]


# ── Notification Centre ────────────────────────────────────────────────────

@bp.route("/")
@login_required
def notification_center():
    tab = request.args.get("tab", "unread")   # "unread" | "all"
    page = request.args.get("page", 1, type=int)

    base_q = Alert.query.filter_by(user_id=current_user.id).order_by(Alert.created_at.desc())

    if tab == "unread":
        base_q = base_q.filter_by(is_read=False)

    pagination = base_q.paginate(page=page, per_page=20, error_out=False)
    alerts = pagination.items

    return render_template(
        "alerts/notification_center.html",
        title="Notifications",
        alerts=alerts,
        pagination=pagination,
        tab=tab,
        unread_count=_unread_count(),
    )


# ── Mark single alert read & redirect ─────────────────────────────────────

@bp.route("/<int:alert_id>/read", methods=["POST"])
@login_required
def mark_read(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    if alert.user_id != current_user.id:
        abort(403)

    alert.is_read = True
    db.session.commit()

    if alert.link_url:
        return redirect(alert.link_url)
    return redirect(url_for("alerts.notification_center"))


# ── Mark all read ──────────────────────────────────────────────────────────

@bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    Alert.query.filter_by(user_id=current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("All notifications marked as read.", "success")
    return redirect(url_for("alerts.notification_center"))


# ── JSON unread count (navbar bell polling) ────────────────────────────────

@bp.route("/api/unread-count")
@login_required
def api_unread_count():
    return jsonify({"count": _unread_count()})


# ── Admin — Alert Rule Management ─────────────────────────────────────────

@bp.route("/rules", methods=["GET", "POST"])
@login_required
def alert_rules():
    if current_user.role != "administrator":
        abort(403)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            name      = request.form.get("name", "").strip()
            rule_type = request.form.get("rule_type", "")
            threshold = request.form.get("threshold", 0, type=int)

            if not name or not rule_type:
                flash("Name and rule type are required.", "danger")
            else:
                rule = AlertRule(
                    name=name,
                    rule_type=rule_type,
                    threshold=threshold,
                    created_by_id=current_user.id,
                )
                db.session.add(rule)
                db.session.commit()
                flash(f"Rule '{name}' created.", "success")

        elif action == "delete":
            rule_id = request.form.get("rule_id", type=int)
            rule = AlertRule.query.get_or_404(rule_id)
            db.session.delete(rule)
            db.session.commit()
            flash("Rule deleted.", "success")

        return redirect(url_for("alerts.alert_rules"))

    rules = AlertRule.query.order_by(AlertRule.created_at.desc()).all()
    return render_template(
        "alerts/alert_rules.html",
        title="Alert Rules",
        rules=rules,
        rule_type_choices=RULE_TYPE_CHOICES,
    )


@bp.route("/rules/<int:rule_id>/toggle", methods=["POST"])
@login_required
def toggle_rule(rule_id):
    if current_user.role != "administrator":
        abort(403)
    rule = AlertRule.query.get_or_404(rule_id)
    rule.is_enabled = not rule.is_enabled
    db.session.commit()
    state = "enabled" if rule.is_enabled else "disabled"
    flash(f"Rule '{rule.name}' {state}.", "success")
    return redirect(url_for("alerts.alert_rules"))


# ── Per-User Preferences ───────────────────────────────────────────────────

@bp.route("/preferences", methods=["GET", "POST"])
@login_required
def preferences():
    pref = UserAlertPreference.query.filter_by(user_id=current_user.id).first()
    if not pref:
        pref = UserAlertPreference(user_id=current_user.id)
        db.session.add(pref)
        db.session.commit()

    if request.method == "POST":
        pref.email_enabled  = "email_enabled"  in request.form
        pref.sms_enabled    = "sms_enabled"     in request.form
        pref.digest_enabled = "digest_enabled"  in request.form
        db.session.commit()
        flash("Notification preferences saved.", "success")
        return redirect(url_for("alerts.preferences"))

    return render_template(
        "alerts/preferences.html",
        title="Notification Preferences",
        pref=pref,
    )


# ── Admin test trigger (dev helper — protected) ────────────────────────────

@bp.route("/test-trigger")
@login_required
def test_trigger():
    """Manually fires all alert jobs — admin only, dev convenience."""
    if current_user.role != "administrator":
        abort(403)
    from ..alerts_service import (
        run_permit_expiry_alerts,
        run_high_risk_vessel_detection,
        run_unusual_activity_detection,
    )
    run_permit_expiry_alerts()
    run_high_risk_vessel_detection()
    run_unusual_activity_detection()
    flash("Alert jobs triggered manually.", "success")
    return redirect(url_for("alerts.notification_center"))
