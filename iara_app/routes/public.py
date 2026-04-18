# routes/public.py
# ---------------------------------------------------------
# Public-facing routes (no login required) and the REST API:
#   /public/vessel/<number>  — QR-scanned vessel card
#   /vessel/<id>/qr          — generate QR PNG
#   /api/v1/*                — simple token-based API
# ---------------------------------------------------------

import hmac
import hashlib
import base64
import json as _json
from datetime import date
from functools import wraps

from flask import Blueprint, render_template, request, send_file
from flask_login import login_required, current_user

from .. import db
from ..models import Vessel, Permit, Inspection, Violation

bp = Blueprint("public", __name__)

# ── PUBLIC VESSEL CARD ────────────────────────────────────────────────────────

@bp.route("/public/vessel/<string:international_number>")
def public_vessel_card(international_number):
    """
    No login required.
    Shown when someone scans the QR code on a vessel.
    """
    vessel         = Vessel.query.filter_by(international_number=international_number).first_or_404()
    active_permit  = Permit.query.filter_by(vessel_id=vessel.id, status="Active").first()
    last_inspection = Inspection.query.filter_by(vessel_id=vessel.id)\
        .order_by(Inspection.date.desc()).first()

    open_violations = []
    if last_inspection:
        open_violations = [v for v in last_inspection.violations if v.status == "open"]

    return render_template(
        "public/vessel_card.html",
        vessel=vessel,
        active_permit=active_permit,
        last_inspection=last_inspection,
        open_violations=open_violations
    )


@bp.route("/vessel/<int:vessel_id>/qr")
@login_required
def vessel_qr(vessel_id):
    """Generate and return a QR code PNG for the vessel's public card URL."""
    import qrcode
    import io

    vessel     = db.get_or_404(Vessel, vessel_id)
    public_url = request.host_url.rstrip("/") + f"/public/vessel/{vessel.international_number}"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(public_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     download_name=f"vessel_{vessel.call_sign}_qr.png")


# ── SIMPLE REST API (v1) ──────────────────────────────────────────────────────
# Uses a lightweight HMAC token — NOT full JWT, but beginner-friendly.

API_SECRET = "iara-api-secret-change-in-production"


def _make_token(user_id, role):
    """Create a signed token string from user_id and role."""
    payload = _json.dumps({"uid": user_id, "role": role}).encode()
    sig     = hmac.new(API_SECRET.encode(), payload, hashlib.sha256).digest()
    return (
        base64.urlsafe_b64encode(payload).decode()
        + "."
        + base64.urlsafe_b64encode(sig).decode()
    )


def _verify_token(token):
    """Verify the token signature and return the payload dict, or None on failure."""
    try:
        payload_b64, sig_b64 = token.split(".")
        payload  = base64.urlsafe_b64decode(payload_b64)
        sig      = base64.urlsafe_b64decode(sig_b64)
        expected = hmac.new(API_SECRET.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        return _json.loads(payload)
    except Exception:
        return None


def _api_login_required(f):
    """Decorator: require a valid Bearer token in the Authorization header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return {"error": "Missing or invalid Authorization header"}, 401
        claims = _verify_token(auth[7:])
        if not claims:
            return {"error": "Invalid or expired token"}, 401
        request.api_user = claims
        return f(*args, **kwargs)
    return decorated


def _api_role_required(*roles):
    """Decorator: require a specific role in the Bearer token."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return {"error": "Unauthorized"}, 401
            claims = _verify_token(auth[7:])
            if not claims or claims.get("role") not in roles:
                return {"error": "Forbidden"}, 403
            request.api_user = claims
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─── API Endpoints ────────────────────────────────────────────────────────────

@bp.route("/api/v1/auth/token", methods=["POST"])
def api_get_token():
    """POST { email, password } → { token, role, name }"""
    from ..models import User
    data     = request.get_json(silent=True) or {}
    user     = User.query.filter_by(email=data.get("email", "")).first()
    if not user or not user.check_password(data.get("password", "")):
        return {"error": "Invalid credentials"}, 401
    token = _make_token(user.id, user.role)
    return {"token": token, "role": user.role, "name": f"{user.first_name} {user.last_name}"}


@bp.route("/api/v1/vessels", methods=["GET"])
@_api_login_required
def api_vessels():
    vessels = Vessel.query.all()
    return {"vessels": [
        {
            "id": v.id,
            "call_sign": v.call_sign,
            "international_number": v.international_number,
            "owner": v.owner_name,
            "captain": v.captain_name,
            "length": v.length,
            "engine_power": v.engine_power
        }
        for v in vessels
    ]}


@bp.route("/api/v1/vessels/<int:vessel_id>", methods=["GET"])
@_api_login_required
def api_vessel_detail(vessel_id):
    v            = db.get_or_404(Vessel, vessel_id)
    active_permit = Permit.query.filter_by(vessel_id=v.id, status="Active").first()
    last_insp    = Inspection.query.filter_by(vessel_id=v.id)\
        .order_by(Inspection.date.desc()).first()
    return {
        "id": v.id,
        "call_sign": v.call_sign,
        "international_number": v.international_number,
        "marking": v.marking,
        "owner": v.owner_name,
        "captain": v.captain_name,
        "length": v.length,
        "width": v.width,
        "engine_power": v.engine_power,
        "active_permit": {
            "number": active_permit.permit_number,
            "type":   active_permit.permit_type,
            "expiry": str(active_permit.expiry_date),
            "status": active_permit.status
        } if active_permit else None,
        "last_inspection": {
            "id":     last_insp.id,
            "date":   str(last_insp.date),
            "score":  last_insp.final_score or last_insp.score,
            "status": last_insp.status
        } if last_insp else None
    }


@bp.route("/api/v1/permits/<int:vessel_id>", methods=["GET"])
@_api_login_required
def api_vessel_permits(vessel_id):
    vessel = db.get_or_404(Vessel, vessel_id)
    return {"vessel": vessel.call_sign, "permits": [
        {
            "id": p.id, "number": p.permit_number, "type": p.permit_type,
            "status": p.status, "issue_date": str(p.issue_date),
            "expiry_date": str(p.expiry_date)
        }
        for p in vessel.permits
    ]}


@bp.route("/api/v1/inspections", methods=["GET"])
@_api_login_required
def api_inspections():
    claims = request.api_user
    if claims["role"] == "inspector":
        inspections = Inspection.query.filter_by(inspector_id=claims["uid"])\
            .order_by(Inspection.date.desc()).limit(50).all()
    else:
        inspections = Inspection.query.order_by(Inspection.date.desc()).limit(50).all()
    return {"inspections": [
        {
            "id": i.id,
            "vessel": i.vessel.call_sign,
            "date": str(i.date),
            "status": i.status,
            "score": i.final_score or i.score,
            "violations": len(i.violations)
        }
        for i in inspections
    ]}


@bp.route("/api/v1/inspections/create", methods=["POST"])
@_api_role_required("inspector", "administrator")
def api_create_inspection():
    data      = request.get_json(silent=True) or {}
    vessel_id = data.get("vessel_id")
    location  = data.get("location")
    notes     = data.get("notes", "")

    if not vessel_id:
        return {"error": "vessel_id required"}, 400

    vessel = Vessel.query.get(vessel_id)
    if not vessel:
        return {"error": "Vessel not found"}, 404

    permit = Permit.query.filter_by(vessel_id=vessel_id)\
        .order_by(Permit.expiry_date.desc()).first()

    insp = Inspection(
        vessel_id=vessel_id,
        inspector_id=request.api_user["uid"],
        location=location,
        notes=notes,
        permit_status_snapshot=permit.status if permit else "No Permit",
        date=date.today()
    )
    db.session.add(insp)
    db.session.commit()
    return {"id": insp.id, "status": "draft", "vessel": vessel.call_sign}, 201


@bp.route("/api/v1/inspections/<int:inspection_id>", methods=["GET"])
@_api_login_required
def api_inspection_detail(inspection_id):
    i = db.get_or_404(Inspection, inspection_id)
    return {
        "id": i.id,
        "vessel": {"id": i.vessel.id, "call_sign": i.vessel.call_sign},
        "date": str(i.date),
        "location": i.location,
        "status": i.status,
        "score": i.final_score or i.score,
        "permit_status": i.permit_status_snapshot,
        "violations": [
            {
                "id": v.id,
                "code": v.violation_code.code if v.violation_code else None,
                "severity": v.severity,
                "description": v.description,
                "status": v.status
            }
            for v in i.violations
        ]
    }


@bp.route("/api/v1/stats", methods=["GET"])
@_api_role_required("administrator")
def api_stats():
    from sqlalchemy import func
    total_vessels     = Vessel.query.count()
    total_permits     = Permit.query.count()
    active_permits    = Permit.query.filter_by(status="Active").count()
    total_inspections = Inspection.query.count()
    total_violations  = Violation.query.count()
    open_violations   = Violation.query.filter_by(status="open").count()
    avg_score = db.session.query(func.avg(Inspection.final_score))\
        .filter(Inspection.final_score.isnot(None)).scalar()
    return {
        "vessels": total_vessels,
        "permits": {"total": total_permits, "active": active_permits},
        "inspections": total_inspections,
        "violations": {"total": total_violations, "open": open_violations},
        "average_score": round(float(avg_score), 1) if avg_score else None
    }
