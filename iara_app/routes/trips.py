# routes/trips.py
# ---------------------------------------------------------
# Fishing Trips & Catch Logbook
# Accessible to: fisherman, amateur (own trips), inspector & admin (all trips)
# ---------------------------------------------------------

from datetime import datetime, date, timedelta

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, abort, jsonify
)
from flask_login import login_required, current_user
from sqlalchemy import func

from .. import db
from ..models import (
    FishingTrip, CatchRecord, TripStatus,
    Species, GearType, Vessel
)
from ..forms import StartTripForm, EndTripForm, CatchRecordForm

bp = Blueprint("trips", __name__, url_prefix="/trips")

# ── Helpers ─────────────────────────────────────────────────────────────────

FISHER_ROLES  = {"fisherman", "amateur"}
STAFF_ROLES   = {"inspector", "administrator"}
ALL_ROLES     = FISHER_ROLES | STAFF_ROLES


def _require_roles(*roles):
    if current_user.role not in roles:
        abort(403)


def _get_trip_or_404(trip_id):
    return FishingTrip.query.get_or_404(trip_id)


def _assert_trip_owner(trip):
    """Fisher may only access their own trips; staff may access any."""
    if current_user.role in STAFF_ROLES:
        return
    if trip.fisherman_id != current_user.id:
        abort(403)


# ── Route 1: Trip list ───────────────────────────────────────────────────────

@bp.route("/")
@login_required
def trips_list():
    _require_roles(*ALL_ROLES)

    # Build base query
    if current_user.role in FISHER_ROLES:
        # Fishers see only their own trips
        q = FishingTrip.query.filter_by(fisherman_id=current_user.id)
    else:
        # Staff see all trips (with optional fisherman filter)
        q = FishingTrip.query

    # Date-range filter (optional GET params)
    date_from_str = request.args.get("date_from", "")
    date_to_str   = request.args.get("date_to",   "")
    status_filter = request.args.get("status",     "")

    if date_from_str:
        try:
            df = datetime.strptime(date_from_str, "%Y-%m-%d")
            q  = q.filter(FishingTrip.start_datetime >= df)
        except ValueError:
            pass

    if date_to_str:
        try:
            dt = datetime.strptime(date_to_str, "%Y-%m-%d")
            dt = dt.replace(hour=23, minute=59, second=59)
            q  = q.filter(FishingTrip.start_datetime <= dt)
        except ValueError:
            pass

    if status_filter in ("active", "completed"):
        q = q.filter(FishingTrip.status == status_filter)

    trips = q.order_by(FishingTrip.start_datetime.desc()).all()

    return render_template(
        "trips/trips_list.html",
        title="Fishing Logbook",
        trips=trips,
        date_from=date_from_str,
        date_to=date_to_str,
        status_filter=status_filter,
    )


# ── Route 2: Start trip ──────────────────────────────────────────────────────

@bp.route("/start", methods=["GET", "POST"])
@login_required
def start_trip():
    _require_roles(*FISHER_ROLES)

    # Block if there is already an active trip
    active = FishingTrip.query.filter_by(
        fisherman_id=current_user.id, status=TripStatus.ACTIVE.value
    ).first()
    if active:
        flash("You already have an active trip. Please end it before starting a new one.", "warning")
        return redirect(url_for("trips.trip_detail", trip_id=active.id))

    form = StartTripForm()
    form.set_vessel_choices(current_user)

    if form.validate_on_submit():
        trip = FishingTrip(
            fisherman_id   = current_user.id,
            vessel_id      = form.vessel_id.data if form.vessel_id.data else None,
            start_datetime = form.start_datetime.data,
            location       = form.location.data,
            weather        = form.weather.data,
            fuel_liters    = form.fuel_liters.data,
            notes          = form.notes.data,
            status         = TripStatus.ACTIVE.value,
        )
        # vessel_id == 0 means "no vessel"
        if trip.vessel_id == 0:
            trip.vessel_id = None

        db.session.add(trip)
        db.session.commit()
        flash("Trip started successfully. Log your catch below!", "success")
        return redirect(url_for("trips.trip_detail", trip_id=trip.id))

    # Default start_datetime to now (rounded to minute) for convenience
    if request.method == "GET":
        form.start_datetime.data = datetime.now().replace(second=0, microsecond=0)

    return render_template("trips/start_trip.html", title="Start New Trip", form=form)


# ── Route 3: End trip ────────────────────────────────────────────────────────

@bp.route("/<int:trip_id>/end", methods=["GET", "POST"])
@login_required
def end_trip(trip_id):
    trip = _get_trip_or_404(trip_id)
    _assert_trip_owner(trip)
    _require_roles(*FISHER_ROLES)

    if trip.status == TripStatus.COMPLETED.value:
        flash("This trip is already completed.", "info")
        return redirect(url_for("trips.trip_detail", trip_id=trip_id))

    form = EndTripForm()

    if form.validate_on_submit():
        if form.end_datetime.data <= trip.start_datetime:
            flash("Return time must be after departure time.", "danger")
        else:
            trip.end_datetime = form.end_datetime.data
            trip.status       = TripStatus.COMPLETED.value
            if form.notes.data:
                trip.notes = (trip.notes or "") + "\n\n[End notes]: " + form.notes.data
            db.session.commit()
            flash("Trip completed successfully.", "success")
            return redirect(url_for("trips.trip_detail", trip_id=trip_id))

    if request.method == "GET":
        form.end_datetime.data = datetime.now().replace(second=0, microsecond=0)

    return render_template(
        "trips/end_trip.html",
        title="End Trip",
        form=form,
        trip=trip,
    )


# ── Route 4: Trip detail ─────────────────────────────────────────────────────

@bp.route("/<int:trip_id>")
@login_required
def trip_detail(trip_id):
    _require_roles(*ALL_ROLES)
    trip = _get_trip_or_404(trip_id)
    _assert_trip_owner(trip)

    # Aggregate totals
    total_weight = db.session.query(
        func.coalesce(func.sum(CatchRecord.weight_kg), 0)
    ).filter_by(trip_id=trip_id).scalar()

    total_qty = db.session.query(
        func.coalesce(func.sum(CatchRecord.quantity), 0)
    ).filter_by(trip_id=trip_id).scalar()

    return render_template(
        "trips/trip_detail.html",
        title=f"Trip #{trip_id}",
        trip=trip,
        total_weight=round(total_weight, 2),
        total_qty=total_qty,
        TripStatus=TripStatus,
    )


# ── Route 5: Add catch record ────────────────────────────────────────────────

@bp.route("/<int:trip_id>/catch/add", methods=["GET", "POST"])
@login_required
def add_catch(trip_id):
    _require_roles(*FISHER_ROLES)
    trip = _get_trip_or_404(trip_id)
    _assert_trip_owner(trip)

    if trip.status == TripStatus.COMPLETED.value:
        flash("Cannot add catch to a completed trip.", "warning")
        return redirect(url_for("trips.trip_detail", trip_id=trip_id))

    form = CatchRecordForm()
    form.set_gear_choices()

    if form.validate_on_submit():
        species = None
        species_id = None
        if form.species_id.data:
            try:
                sid = int(form.species_id.data)
                if sid > 0:
                    species = Species.query.get(sid)
                    species_id = sid if species else None
            except (ValueError, TypeError):
                pass

        gear_id = form.gear_type_id.data if form.gear_type_id.data and form.gear_type_id.data != 0 else None

        record = CatchRecord(
            trip_id           = trip_id,
            species_id        = species_id,
            species_name_free = form.species_name_free.data if not species else None,
            quantity          = form.quantity.data,
            weight_kg         = form.weight_kg.data,
            size_cm           = form.size_cm.data,
            gear_type_id      = gear_id,
            notes             = form.notes.data,
        )
        db.session.add(record)
        db.session.flush()  # get record.id before commit

        alerts = []

        # ── Protected species alert ──────────────────────────────────────
        if species and species.is_protected:
            alerts.append(
                f"⚠️ PROTECTED SPECIES: {species.name_bg} is fully protected. "
                f"This catch has been logged but may be subject to regulatory review."
            )

        # ── Daily catch limit validation ─────────────────────────────────
        if species and species.daily_limit_kg:
            today_start = datetime.combine(date.today(), datetime.min.time())
            today_end   = datetime.combine(date.today(), datetime.max.time())

            # Sum weight already logged today for this species by this fisherman
            daily_total = db.session.query(
                func.coalesce(func.sum(CatchRecord.weight_kg), 0)
            ).join(FishingTrip).filter(
                FishingTrip.fisherman_id == current_user.id,
                CatchRecord.species_id   == species_id,
                FishingTrip.start_datetime.between(today_start, today_end)
            ).scalar() or 0

            if daily_total > species.daily_limit_kg:
                alerts.append(
                    f"⚠️ DAILY LIMIT EXCEEDED: You have logged {daily_total:.2f} kg of "
                    f"{species.name_bg} today (limit: {species.daily_limit_kg} kg)."
                )
            elif daily_total > species.daily_limit_kg * 0.8:
                alerts.append(
                    f"ℹ️ Approaching daily limit: {daily_total:.2f} kg of "
                    f"{species.name_bg} logged today (limit: {species.daily_limit_kg} kg)."
                )

        # ── Size check ───────────────────────────────────────────────────
        if species and form.size_cm.data and species.min_size_cm:
            if form.size_cm.data < species.min_size_cm:
                alerts.append(
                    f"⚠️ SIZE BELOW MINIMUM: Recorded size {form.size_cm.data} cm is below "
                    f"the minimum legal size of {species.min_size_cm} cm for {species.name_bg}."
                )

        db.session.commit()

        for alert in alerts:
            category = "danger" if "PROTECTED" in alert or "EXCEEDED" in alert or "BELOW" in alert else "warning"
            flash(alert, category)

        if not alerts:
            flash("Catch record saved successfully.", "success")

        return redirect(url_for("trips.trip_detail", trip_id=trip_id))

    return render_template(
        "trips/add_catch.html",
        title="Add Catch Record",
        form=form,
        trip=trip,
    )


# ── Route 6: Delete catch record ─────────────────────────────────────────────

@bp.route("/<int:trip_id>/catch/<int:record_id>/delete", methods=["POST"])
@login_required
def delete_catch(trip_id, record_id):
    _require_roles(*FISHER_ROLES)
    trip   = _get_trip_or_404(trip_id)
    _assert_trip_owner(trip)

    record = CatchRecord.query.filter_by(id=record_id, trip_id=trip_id).first_or_404()
    db.session.delete(record)
    db.session.commit()
    flash("Catch record removed.", "success")
    return redirect(url_for("trips.trip_detail", trip_id=trip_id))


# ── Route 7: Printable summary ───────────────────────────────────────────────

@bp.route("/<int:trip_id>/print")
@login_required
def trip_print(trip_id):
    _require_roles(*ALL_ROLES)
    trip = _get_trip_or_404(trip_id)
    _assert_trip_owner(trip)

    total_weight = sum(r.weight_kg for r in trip.catch_records if r.weight_kg)
    total_qty    = sum(r.quantity  for r in trip.catch_records if r.quantity)

    return render_template(
        "trips/trip_print.html",
        trip=trip,
        total_weight=round(total_weight, 2),
        total_qty=total_qty,
        printed_at=datetime.now(),
    )


# ── Route 8: Species autocomplete API ────────────────────────────────────────

@bp.route("/api/species/search")
@login_required
def species_search():
    q    = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 15)), 50)

    if len(q) < 1:
        return jsonify([])

    results = Species.query.filter(
        db.or_(
            Species.name_bg.ilike(f"%{q}%"),
            Species.name_en.ilike(f"%{q}%"),
            Species.scientific_name.ilike(f"%{q}%"),
        )
    ).order_by(Species.name_bg).limit(limit).all()

    return jsonify([
        {
            "id":           s.id,
            "name_bg":      s.name_bg,
            "name_en":      s.name_en or "",
            "scientific":   s.scientific_name or "",
            "is_protected": s.is_protected,
            "daily_limit":  s.daily_limit_kg,
            "min_size_cm":  s.min_size_cm,
        }
        for s in results
    ])
