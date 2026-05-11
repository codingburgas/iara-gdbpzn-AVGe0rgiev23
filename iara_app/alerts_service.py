# iara_app/alerts_service.py
# ---------------------------------------------------------
# Central alert-generation service.
# All scheduler jobs import from here so that alert logic
# stays in one place and is easy to unit-test.
# ---------------------------------------------------------

from datetime import date, datetime, timedelta

from . import db


# ── Helpers ────────────────────────────────────────────────────────────────

def create_alert(user_id, alert_type, title, message, severity="info", link_url=None):
    """
    Persist one Alert row.  Deduplicates within the same calendar day so that
    repeated scheduler runs do not spam the inbox.
    """
    from .models import Alert

    today_start = datetime.combine(date.today(), datetime.min.time())

    duplicate = Alert.query.filter_by(
        user_id=user_id,
        type=alert_type,
        title=title,
    ).filter(Alert.created_at >= today_start).first()

    if duplicate:
        return None  # already fired today

    alert = Alert(
        user_id=user_id,
        type=alert_type,
        title=title,
        message=message,
        severity=severity,
        link_url=link_url,
    )
    db.session.add(alert)
    db.session.commit()
    return alert


def _admin_user_ids():
    """Return the list of user IDs whose role is 'administrator'."""
    from .models import User
    return [u.id for u in User.query.filter_by(role="administrator").all()]


# ── Permit Expiry Alerts ────────────────────────────────────────────────────

def run_permit_expiry_alerts():
    """
    Scheduler job — fires daily.
    Creates alerts for permits expiring in exactly 30, 15, 7, or 1 day(s).
    Alert recipients: all administrator accounts.
    """
    from .models import Permit

    thresholds = [30, 15, 7, 1]
    today = date.today()
    admin_ids = _admin_user_ids()

    if not admin_ids:
        return

    permits = Permit.query.filter(Permit.status != "Expired").all()

    for permit in permits:
        days_left = (permit.expiry_date - today).days
        if days_left not in thresholds:
            continue

        if days_left == 1:
            severity = "critical"
            day_label = "TOMORROW"
        elif days_left <= 7:
            severity = "high"
            day_label = f"in {days_left} days"
        elif days_left <= 15:
            severity = "warning"
            day_label = f"in {days_left} days"
        else:
            severity = "info"
            day_label = f"in {days_left} days"

        title = f"Permit {permit.permit_number} expires {day_label}"
        message = (
            f"Permit #{permit.permit_number} (vessel ID {permit.vessel_id}) "
            f"of type '{permit.permit_type}' will expire on {permit.expiry_date}. "
            f"Please take action to renew before the deadline."
        )
        link = f"/permits/{permit.id}"

        for uid in admin_ids:
            create_alert(uid, "permit_expiry", title, message, severity, link)

    print(f"[Scheduler] Permit expiry alerts checked ({today}).")


# ── High-Risk Vessel Detection ──────────────────────────────────────────────

def _vessel_risk_score(vessel_id):
    """
    Compute a 0–100 risk score for a vessel based on violations
    recorded in the past 30 days.

    Scoring:
      • +15 per violation (base, capped at 60)
      • +20 for any CRITICAL violation
      • +10 for any HIGH violation
      • +5  for any MEDIUM violation
    Score is capped at 100.
    """
    from .models import Violation, Inspection

    cutoff = datetime.utcnow() - timedelta(days=30)

    violations = (
        db.session.query(Violation)
        .join(Inspection, Violation.inspection_id == Inspection.id)
        .filter(Inspection.vessel_id == vessel_id)
        .filter(Violation.created_at >= cutoff)
        .all()
    )

    if not violations:
        return 0, violations

    base = min(len(violations) * 15, 60)
    bonus = 0
    for v in violations:
        sev = (v.severity or "").lower()
        if sev == "critical":
            bonus += 20
        elif sev == "high":
            bonus += 10
        elif sev == "medium":
            bonus += 5

    score = min(base + bonus, 100)
    return score, violations


def run_high_risk_vessel_detection():
    """
    Scheduler job — fires daily.
    Vessels with ≥ 3 violations in the last 30 days get a HIGH/CRITICAL alert
    sent to all administrators.
    """
    from .models import Vessel, Violation, Inspection

    cutoff = datetime.utcnow() - timedelta(days=30)
    admin_ids = _admin_user_ids()

    if not admin_ids:
        return

    # Find vessel IDs with ≥ 3 recent violations
    from sqlalchemy import func

    risky_vessel_ids = (
        db.session.query(Inspection.vessel_id)
        .join(Violation, Violation.inspection_id == Inspection.id)
        .filter(Violation.created_at >= cutoff)
        .group_by(Inspection.vessel_id)
        .having(func.count(Violation.id) >= 3)
        .all()
    )

    for (vid,) in risky_vessel_ids:
        vessel = Vessel.query.get(vid)
        if not vessel:
            continue

        score, violations = _vessel_risk_score(vid)
        severity = "critical" if score >= 75 else "high"

        title = f"High-risk vessel: {vessel.call_sign} (score {score}/100)"
        message = (
            f"Vessel '{vessel.call_sign}' (ID {vessel.id}) has accumulated "
            f"{len(violations)} violation(s) in the past 30 days with a risk score of {score}/100. "
            f"Immediate review is recommended."
        )
        link = f"/admin/vessels/{vessel.id}"

        for uid in admin_ids:
            create_alert(uid, "high_risk", title, message, severity, link)

    print(f"[Scheduler] High-risk vessel check complete ({date.today()}).")


# ── Unusual Activity Detection ──────────────────────────────────────────────

def run_unusual_activity_detection():
    """
    Scheduler job — fires daily.
    Flags:
      1. Vessels inspected ≥ 3 times in the last 7 days.
      2. Vessels with the same violation code appearing ≥ 2 times in 30 days.
    """
    from .models import Vessel, Inspection, Violation
    from sqlalchemy import func

    admin_ids = _admin_user_ids()
    if not admin_ids:
        return

    today = date.today()

    # ── 1. Frequent inspections (≥ 3 in last 7 days) ──────────────────────
    week_ago = datetime.utcnow() - timedelta(days=7)

    frequent = (
        db.session.query(Inspection.vessel_id, func.count(Inspection.id).label("cnt"))
        .filter(Inspection.date >= week_ago.date())
        .group_by(Inspection.vessel_id)
        .having(func.count(Inspection.id) >= 3)
        .all()
    )

    for vessel_id, cnt in frequent:
        vessel = Vessel.query.get(vessel_id)
        if not vessel:
            continue
        title = f"Unusual activity: {vessel.call_sign} inspected {cnt}× this week"
        message = (
            f"Vessel '{vessel.call_sign}' has been inspected {cnt} time(s) in the past 7 days. "
            f"This may indicate targeted monitoring or escalating compliance issues."
        )
        for uid in admin_ids:
            create_alert(uid, "unusual_activity", title, message, "warning", f"/admin/vessels/{vessel_id}")

    # ── 2. Recurring violation code (same code ≥ 2 times / 30 days) ───────
    cutoff30 = datetime.utcnow() - timedelta(days=30)

    recurring = (
        db.session.query(
            Inspection.vessel_id,
            Violation.violation_code_id,
            func.count(Violation.id).label("cnt"),
        )
        .join(Inspection, Violation.inspection_id == Inspection.id)
        .filter(Violation.created_at >= cutoff30)
        .filter(Violation.violation_code_id.isnot(None))
        .group_by(Inspection.vessel_id, Violation.violation_code_id)
        .having(func.count(Violation.id) >= 2)
        .all()
    )

    for vessel_id, code_id, cnt in recurring:
        vessel = Vessel.query.get(vessel_id)
        if not vessel:
            continue

        from .models import ViolationCode
        code = ViolationCode.query.get(code_id)
        code_label = code.code if code else f"#{code_id}"

        title = f"Recurring violation {code_label} on {vessel.call_sign}"
        message = (
            f"Vessel '{vessel.call_sign}' has received violation code {code_label} "
            f"{cnt} time(s) in the past 30 days — recurring non-compliance detected."
        )
        for uid in admin_ids:
            create_alert(uid, "unusual_activity", title, message, "high", f"/admin/vessels/{vessel_id}")

    print(f"[Scheduler] Unusual activity check complete ({today}).")


# ── Daily Email Digest ──────────────────────────────────────────────────────

def send_daily_digest():
    """
    Scheduler job — fires every morning at 08:00.
    Sends (or prints) a summary of each user's unread alerts from the past 24 h.
    Actual email delivery requires SMTP configuration in config.py.
    """
    from .models import Alert, User, UserAlertPreference

    cutoff = datetime.utcnow() - timedelta(hours=24)

    users = User.query.filter_by(is_active=True).all()

    for user in users:
        # Honour per-user preferences
        pref = user.alert_preference
        if pref and not pref.digest_enabled:
            continue

        unread = Alert.query.filter_by(
            user_id=user.id, is_read=False
        ).filter(Alert.created_at >= cutoff).all()

        if not unread:
            continue

        lines = [f"  [{a.severity.upper()}] {a.title}: {a.message}" for a in unread]
        body = (
            f"Good morning {user.first_name},\n\n"
            f"You have {len(unread)} unread alert(s) in IARA:\n\n"
            + "\n".join(lines)
            + "\n\nLog in to the IARA system to review and act on these alerts."
        )

        # ── SMTP stub — replace with real smtplib calls when credentials are available ──
        print(f"[Digest] → {user.email}\n{body}\n{'─'*60}")

    print(f"[Scheduler] Daily digest sent ({date.today()}).")
