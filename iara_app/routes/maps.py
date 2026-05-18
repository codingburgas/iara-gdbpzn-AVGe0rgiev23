# routes/maps.py
# ---------------------------------------------------------
# Module 11 — Interactive Maps
# All map pages + JSON API endpoints for Leaflet.js
# ---------------------------------------------------------

import json
import math
import random
from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for,
    request, jsonify, abort
)
from flask_login import login_required, current_user

from .. import db
from ..models import (
    Vessel, Inspection, PortLocation, InspectionLocation,
    FishingZone, ZONE_TYPES, ZONE_COLORS
)
from ..decorators import admin_required

bp = Blueprint("maps", __name__, url_prefix="/maps")


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _haversine(lat1, lon1, lat2, lon2):
    """Return distance in km between two WGS-84 points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _bearing(lat1, lon1, lat2, lon2):
    """Initial bearing (degrees) from point 1 → 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlam = math.radians(lon2 - lon1)
    x = math.sin(dlam) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _resolve_port_coords(port_name):
    """Try to find lat/lng for a free-text port_registration string."""
    if not port_name:
        return None, None
    port = PortLocation.query.filter(
        db.func.lower(PortLocation.name) == port_name.strip().lower()
    ).first()
    if port:
        return port.lat, port.lng
    # partial match fallback
    port = PortLocation.query.filter(
        PortLocation.name.ilike(f"%{port_name.strip()}%")
    ).first()
    if port:
        return port.lat, port.lng
    return None, None


# ── PAGE ROUTES ───────────────────────────────────────────────────────────────

@bp.route("/")
@login_required
def fleet_map():
    zone_count = FishingZone.query.filter_by(is_active=True).count()
    port_count = PortLocation.query.filter_by(is_active=True).count()
    vessel_count = Vessel.query.count()
    inspection_count = InspectionLocation.query.count()
    return render_template(
        "maps/fleet_map.html",
        title="Fleet Map",
        zone_count=zone_count,
        port_count=port_count,
        vessel_count=vessel_count,
        inspection_count=inspection_count,
    )


@bp.route("/ports")
@login_required
def ports_map():
    ports = PortLocation.query.filter_by(is_active=True).order_by(PortLocation.name).all()
    return render_template(
        "maps/ports_map.html",
        title="Port Directory",
        ports=ports,
    )


@bp.route("/zones")
@login_required
def zones_map():
    zones = FishingZone.query.filter_by(is_active=True).order_by(FishingZone.name).all()
    return render_template(
        "maps/zones_map.html",
        title="Fishing Zones",
        zones=zones,
    )


@bp.route("/zones/manage")
@login_required
@admin_required
def zone_manage():
    zones = FishingZone.query.order_by(FishingZone.name).all()
    zone_types = ZONE_TYPES
    zone_colors = ZONE_COLORS
    return render_template(
        "maps/zone_manage.html",
        title="Manage Fishing Zones",
        zones=zones,
        zone_types=zone_types,
        zone_colors=zone_colors,
    )


@bp.route("/distance")
@login_required
def distance_calc():
    return render_template(
        "maps/distance_calc.html",
        title="Distance Calculator",
    )


# ── JSON API ──────────────────────────────────────────────────────────────────

@bp.route("/api/vessels")
@login_required
def api_vessels():
    """Return all vessels with resolved port coordinates."""
    vessels = Vessel.query.all()
    features = []
    unplaced = []

    for v in vessels:
        lat, lng = _resolve_port_coords(v.port_registration)
        if lat is None:
            unplaced.append(v)
            continue

        # jitter so multiple vessels at same port don't stack
        jlat = lat + random.uniform(-0.008, 0.008)
        jlng = lng + random.uniform(-0.008, 0.008)

        active_permit = next(
            (p for p in v.permits if p.status == "Active"), None
        )
        permit_info = (
            f"{active_permit.permit_number} (expires {active_permit.expiry_date})"
            if active_permit else "No active permit"
        )

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [jlng, jlat]},
            "properties": {
                "id":           v.id,
                "name":         v.name_bg or v.name_en or v.call_sign,
                "call_sign":    v.call_sign,
                "int_number":   v.international_number,
                "port":         v.port_registration or "—",
                "status":       v.status,
                "owner":        v.owner_name,
                "permit":       permit_info,
                "detail_url":   url_for("admin.vessel_details", vessel_id=v.id),
            }
        })

    return jsonify({
        "type": "FeatureCollection",
        "features": features,
        "unplaced_count": len(unplaced),
    })


@bp.route("/api/inspections")
@login_required
def api_inspections():
    """Return inspection geo-points for Leaflet.heat (array of [lat, lng, intensity])."""
    locs = db.session.query(InspectionLocation).join(
        Inspection, InspectionLocation.inspection_id == Inspection.id
    ).all()

    heat = []
    geojson_features = []

    for loc in locs:
        insp = loc.inspection
        violation_count = len(insp.violations) if insp.violations else 0
        intensity = min(1.0, 0.3 + violation_count * 0.15)
        heat.append([loc.lat, loc.lng, intensity])

        geojson_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [loc.lng, loc.lat]},
            "properties": {
                "id":          insp.id,
                "date":        str(insp.date) if insp.date else "",
                "location":    insp.location or "—",
                "score":       insp.final_score,
                "violations":  violation_count,
                "status":      insp.status,
                "detail_url":  url_for("admin.admin_inspections") if current_user.role == "administrator"
                               else url_for("inspector.inspections_list"),
            }
        })

    return jsonify({
        "heat": heat,
        "features": geojson_features,
    })


@bp.route("/api/zones")
@login_required
def api_zones():
    """Return active fishing zones as a GeoJSON FeatureCollection."""
    zones = FishingZone.query.filter_by(is_active=True).all()
    return jsonify({
        "type": "FeatureCollection",
        "features": [z.to_feature() for z in zones],
    })


@bp.route("/api/ports")
@login_required
def api_ports():
    """Return all active ports as GeoJSON with vessel counts."""
    ports = PortLocation.query.filter_by(is_active=True).all()
    features = []
    for p in ports:
        vessel_count = Vessel.query.filter(
            db.func.lower(Vessel.port_registration) == p.name.lower()
        ).count()
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p.lng, p.lat]},
            "properties": {
                "id":           p.id,
                "name":         p.name,
                "name_en":      p.name_en,
                "region":       p.region or "—",
                "country":      p.country,
                "vessel_count": vessel_count,
            }
        })
    return jsonify({
        "type": "FeatureCollection",
        "features": features,
    })


@bp.route("/api/zones/save", methods=["POST"])
@login_required
@admin_required
def api_zone_save():
    """Create or update a FishingZone from JSON body."""
    data = request.get_json(force=True)

    zone_id   = data.get("id")
    name      = (data.get("name") or "").strip()
    zone_code = (data.get("zone_code") or "").strip()
    zone_type = data.get("zone_type", "commercial")
    color     = ZONE_COLORS.get(zone_type, "#3B82F6")
    geojson   = data.get("geojson")
    desc      = (data.get("description") or "").strip()

    if not name or not zone_code or not geojson:
        return jsonify({"ok": False, "error": "name, zone_code and geojson are required"}), 400

    # Validate GeoJSON is parseable
    try:
        json.loads(geojson) if isinstance(geojson, str) else geojson
        geojson_str = geojson if isinstance(geojson, str) else json.dumps(geojson)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid GeoJSON"}), 400

    if zone_id:
        zone = db.session.get(FishingZone, zone_id)
        if not zone:
            return jsonify({"ok": False, "error": "Zone not found"}), 404
    else:
        # Check uniqueness
        if FishingZone.query.filter_by(zone_code=zone_code).first():
            return jsonify({"ok": False, "error": f"Zone code '{zone_code}' already exists"}), 409
        zone = FishingZone(created_by_id=current_user.id)
        db.session.add(zone)

    zone.name        = name
    zone.zone_code   = zone_code
    zone.zone_type   = zone_type
    zone.color       = color
    zone.geojson     = geojson_str
    zone.description = desc
    zone.updated_at  = datetime.utcnow()
    db.session.commit()

    return jsonify({"ok": True, "id": zone.id, "color": zone.color})


@bp.route("/api/zones/<int:zone_id>/delete", methods=["POST"])
@login_required
@admin_required
def api_zone_delete(zone_id):
    zone = db.session.get(FishingZone, zone_id)
    if not zone:
        return jsonify({"ok": False, "error": "Not found"}), 404
    db.session.delete(zone)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/distance")
@login_required
def api_distance():
    """Haversine distance between two lat/lng pairs."""
    try:
        lat1 = float(request.args["lat1"])
        lon1 = float(request.args["lon1"])
        lat2 = float(request.args["lat2"])
        lon2 = float(request.args["lon2"])
    except (KeyError, ValueError):
        return jsonify({"error": "Provide lat1, lon1, lat2, lon2"}), 400

    km = _haversine(lat1, lon1, lat2, lon2)
    nm = km / 1.852
    bearing = _bearing(lat1, lon1, lat2, lon2)
    mid_lat = (lat1 + lat2) / 2
    mid_lng = (lon1 + lon2) / 2

    return jsonify({
        "km":       round(km, 3),
        "nm":       round(nm, 3),
        "bearing":  round(bearing, 1),
        "midpoint": {"lat": round(mid_lat, 6), "lng": round(mid_lng, 6)},
    })
