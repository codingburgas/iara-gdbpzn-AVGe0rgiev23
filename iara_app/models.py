from datetime import datetime, date
from enum import Enum
import bcrypt

from flask_login import UserMixin
from . import db


# ============================================================
# ENUMS
# ============================================================

class PermitStatus(Enum):
    ACTIVE = "Active"
    EXPIRED = "Expired"
    SUSPENDED = "Suspended"


class ViolationSeverity(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class VesselStatus(Enum):
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    SCRAPPED = "Scrapped"


# ============================================================
# USER MODEL
# ============================================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)

    role = db.Column(db.String(50), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    vessel_registration = db.Column(db.String(50))
    fishing_permit_number = db.Column(db.String(50))

    inspector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    id_number = db.Column(db.String(50))
    age_category = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Password reset
    reset_token       = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

    # Rate limiting — track failed login attempts
    failed_logins   = db.Column(db.Integer, default=0)
    locked_until    = db.Column(db.DateTime, nullable=True)

    # Relationships
    inspections = db.relationship("Inspection", foreign_keys="Inspection.inspector_id", backref="inspector", lazy=True)
    scheduled_inspections = db.relationship("ScheduledInspection", foreign_keys="ScheduledInspection.inspector_id", backref="assigned_inspector", lazy=True)
    created_scheduled_inspections = db.relationship("ScheduledInspection", foreign_keys="ScheduledInspection.created_by_id", backref="created_by_user", lazy=True)
    audit_logs = db.relationship("AuditLog", foreign_keys="AuditLog.user_id", backref="user", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    def get_id(self) -> str:
        return str(self.id)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


# ============================================================
# VESSEL MODEL
# ============================================================

class Vessel(db.Model):
    __tablename__ = "vessel"

    id = db.Column(db.Integer, primary_key=True)

    # Identifiers
    international_number = db.Column(db.String(50), nullable=False, unique=True)
    call_sign            = db.Column(db.String(50), nullable=False)
    marking              = db.Column(db.String(50), nullable=False)

    # Names
    name_bg = db.Column(db.String(150))
    name_en = db.Column(db.String(150))

    # Registration
    port_registration = db.Column(db.String(100))
    registration_date = db.Column(db.Date)
    status = db.Column(db.String(20), nullable=False, default=VesselStatus.ACTIVE.value)

    # Dimensions
    length        = db.Column(db.Float, nullable=False)
    width         = db.Column(db.Float, nullable=False)
    gross_tonnage = db.Column(db.Float)
    engine_power  = db.Column(db.Integer, nullable=False)

    # Ownership
    owner_name   = db.Column(db.String(100), nullable=False)
    owner_egn    = db.Column(db.String(20))
    captain_name = db.Column(db.String(100), nullable=False)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    permits              = db.relationship("Permit", backref="vessel", lazy=True)
    inspections          = db.relationship("Inspection", backref="vessel", lazy=True)
    scheduled_inspections = db.relationship("ScheduledInspection", backref="vessel", lazy=True)
    documents            = db.relationship("VesselDocument", backref="vessel", lazy=True, cascade="all, delete-orphan")
    photos               = db.relationship("VesselPhoto", backref="vessel", lazy=True, cascade="all, delete-orphan")
    ownership_history    = db.relationship("VesselOwnershipHistory", backref="vessel", lazy=True, cascade="all, delete-orphan")
    fishing_trips        = db.relationship("FishingTrip", backref="vessel", lazy=True)

    def __repr__(self) -> str:
        return f"<Vessel {self.call_sign}>"


# ============================================================
# PERMIT MODEL
# ============================================================

class Permit(db.Model):
    __tablename__ = "permit"

    id = db.Column(db.Integer, primary_key=True)

    vessel_id = db.Column(db.Integer, db.ForeignKey("vessel.id"), nullable=False)

    permit_number = db.Column(db.String(50), nullable=False, unique=True)
    permit_type = db.Column(db.String(50), nullable=False)

    issue_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)

    status = db.Column(
        db.String(20),
        nullable=False,
        default=PermitStatus.ACTIVE.value
    )

    def is_expired(self) -> bool:
        return date.today() > self.expiry_date

    def days_until_expiry(self) -> int:
        return (self.expiry_date - date.today()).days

    def __repr__(self) -> str:
        return f"<Permit {self.permit_number} ({self.status})>"


# ============================================================
# VIOLATION CATEGORY
# ============================================================

class ViolationCategory(db.Model):
    __tablename__ = "violation_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    codes = db.relationship("ViolationCode", backref="category", lazy=True)

    def __repr__(self) -> str:
        return f"<ViolationCategory {self.name}>"


# ============================================================
# VIOLATION CODE
# ============================================================

class ViolationCode(db.Model):
    __tablename__ = "violation_codes"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("violation_categories.id"),
        nullable=False
    )

    default_severity = db.Column(
        db.String(20),
        nullable=False,
        default=ViolationSeverity.MEDIUM.value
    )

    # Legal reference & fine — added in Lookup Data module
    law_article     = db.Column(db.String(100), nullable=True)   # e.g. "Art. 34 ZRR"
    default_penalty = db.Column(db.Numeric(10, 2), nullable=True)  # EUR

    violations = db.relationship("Violation", backref="violation_code", lazy=True)

    def __repr__(self) -> str:
        return f"<ViolationCode {self.code}>"


# ============================================================
# SPECIES
# ============================================================

class Species(db.Model):
    """Reference table for fish & marine species subject to IARA regulation."""
    __tablename__ = "species"

    id              = db.Column(db.Integer, primary_key=True)

    # Names
    name_bg         = db.Column(db.String(150), nullable=False, unique=True)  # BG common name
    name_en         = db.Column(db.String(150), nullable=True)
    scientific_name = db.Column(db.String(200), nullable=True)

    # Size limits (cm)
    min_size_cm     = db.Column(db.Float, nullable=True)  # minimum legal catch size
    max_size_cm     = db.Column(db.Float, nullable=True)  # optional upper limit

    # Fishing season — stored as 'MM-DD' strings (e.g. '01-04')
    season_start    = db.Column(db.String(10), nullable=True)  # None = year-round
    season_end      = db.Column(db.String(10), nullable=True)

    # Quotas
    daily_limit_kg  = db.Column(db.Float, nullable=True)  # per fisher per day, None = unlimited

    # Protection flag
    is_protected    = db.Column(db.Boolean, nullable=False, default=False)

    notes           = db.Column(db.Text, nullable=True)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Species {self.name_bg}>"


# ============================================================
# GEAR TYPE
# ============================================================

class GearType(db.Model):
    """Reference table for fishing gear types used in inspections and violation records."""
    __tablename__ = "gear_type"

    id                  = db.Column(db.Integer, primary_key=True)

    code                = db.Column(db.String(20), nullable=False, unique=True)  # FAO/EU code e.g. 'TBB'
    name                = db.Column(db.String(150), nullable=False)  # human-readable name
    description         = db.Column(db.Text, nullable=True)

    mesh_size_required  = db.Column(db.Boolean, nullable=False, default=False)
    min_mesh_size_mm    = db.Column(db.Float, nullable=True)

    is_legal            = db.Column(db.Boolean, nullable=False, default=True)

    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<GearType {self.code}>"


# ============================================================
# SCHEDULED INSPECTION
# ============================================================

class ScheduledInspection(db.Model):
    __tablename__ = "scheduled_inspection"

    id = db.Column(db.Integer, primary_key=True)

    vessel_id = db.Column(db.Integer, db.ForeignKey("vessel.id"), nullable=False)
    inspector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    scheduled_date = db.Column(db.Date, nullable=False)
    scheduled_time = db.Column(db.String(10))
    location = db.Column(db.String(255))
    notes = db.Column(db.Text)

    status = db.Column(db.String(20), default="pending")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    inspection_id = db.Column(db.Integer, db.ForeignKey("inspection.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<ScheduledInspection {self.id} {self.scheduled_date}>"


# ============================================================
# INSPECTION
# ============================================================

class Inspection(db.Model):
    __tablename__ = "inspection"

    id = db.Column(db.Integer, primary_key=True)

    vessel_id = db.Column(db.Integer, db.ForeignKey("vessel.id"), nullable=False)
    inspector_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    date = db.Column(db.Date)
    location = db.Column(db.String(255))
    notes = db.Column(db.Text)

    permit_status_snapshot = db.Column(db.String(50))

    score = db.Column(db.Integer, default=100)
    final_score = db.Column(db.Integer)
    status = db.Column(db.String(20), default="draft")
    inspector_signature = db.Column(db.String(255))
    submitted_at = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)

    violations = db.relationship("Violation", backref="inspection", lazy=True,
                                  cascade="all, delete-orphan")


# ============================================================
# VIOLATION
# ============================================================

class Violation(db.Model):
    __tablename__ = "violation"

    id = db.Column(db.Integer, primary_key=True)

    inspection_id = db.Column(
        db.Integer,
        db.ForeignKey("inspection.id"),
        nullable=False
    )

    violation_code_id = db.Column(
        db.Integer,
        db.ForeignKey("violation_codes.id")
    )

    severity = db.Column(db.String(20))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    status = db.Column(db.String(20), default="open")
    resolution_notes = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime)

    evidence = db.relationship("Evidence", backref="violation", lazy=True,
                                cascade="all, delete-orphan")


# ============================================================
# EVIDENCE
# ============================================================

class Evidence(db.Model):
    __tablename__ = "evidence"

    id = db.Column(db.Integer, primary_key=True)

    violation_id = db.Column(
        db.Integer,
        db.ForeignKey("violation.id"),
        nullable=False
    )

    file_path = db.Column(db.String(255))
    note = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Evidence {self.id}>"


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    detail = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by user {self.user_id}>"


# ============================================================
# VESSEL DOCUMENT
# ============================================================

DOC_TYPE_CHOICES = [
    ("Certificate",      "Certificate"),
    ("Insurance",        "Insurance"),
    ("Registration",     "Registration"),
    ("Inspection Report","Inspection Report"),
    ("Other",            "Other"),
]

class VesselDocument(db.Model):
    __tablename__ = "vessel_document"

    id             = db.Column(db.Integer, primary_key=True)
    vessel_id      = db.Column(db.Integer, db.ForeignKey("vessel.id"), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    doc_type      = db.Column(db.String(50), nullable=False)
    filename      = db.Column(db.String(255), nullable=False)   # stored UUID filename
    original_name = db.Column(db.String(255), nullable=False)   # original upload name
    notes         = db.Column(db.Text)
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User", foreign_keys=[uploaded_by_id])

    def __repr__(self) -> str:
        return f"<VesselDocument {self.original_name}>"


# ============================================================
# VESSEL PHOTO
# ============================================================

class VesselPhoto(db.Model):
    __tablename__ = "vessel_photo"

    id             = db.Column(db.Integer, primary_key=True)
    vessel_id      = db.Column(db.Integer, db.ForeignKey("vessel.id"), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    filename    = db.Column(db.String(255), nullable=False)
    caption     = db.Column(db.String(255))
    is_primary  = db.Column(db.Boolean, default=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship("User", foreign_keys=[uploaded_by_id])

    def __repr__(self) -> str:
        return f"<VesselPhoto {self.filename}>"


# ============================================================
# VESSEL OWNERSHIP HISTORY
# ============================================================

class VesselOwnershipHistory(db.Model):
    __tablename__ = "vessel_ownership_history"

    id             = db.Column(db.Integer, primary_key=True)
    vessel_id      = db.Column(db.Integer, db.ForeignKey("vessel.id"), nullable=False)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    owner_name = db.Column(db.String(100), nullable=False)
    owner_egn  = db.Column(db.String(20))
    from_date  = db.Column(db.Date, nullable=False)
    to_date    = db.Column(db.Date, nullable=True)
    notes      = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recorder = db.relationship("User", foreign_keys=[recorded_by_id])

    def __repr__(self) -> str:
        return f"<VesselOwnershipHistory vessel={self.vessel_id} owner={self.owner_name}>"


# ============================================================
# FISHING TRIP
# ============================================================

class TripStatus(Enum):
    ACTIVE    = "active"
    COMPLETED = "completed"


class FishingTrip(db.Model):
    """One fishing trip entry in the catch logbook."""
    __tablename__ = "fishing_trip"

    id             = db.Column(db.Integer, primary_key=True)

    # Who & which vessel
    fisherman_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    vessel_id      = db.Column(db.Integer, db.ForeignKey("vessel.id"), nullable=True)

    # Time
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime   = db.Column(db.DateTime, nullable=True)   # set when trip ends

    # Location & conditions
    location       = db.Column(db.String(255), nullable=True)
    weather        = db.Column(db.String(100), nullable=True)  # e.g. "Calm / 3 Bft"
    fuel_liters    = db.Column(db.Float, nullable=True)

    notes          = db.Column(db.Text, nullable=True)
    status         = db.Column(db.String(20), nullable=False, default=TripStatus.ACTIVE.value)

    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    fisherman      = db.relationship("User", foreign_keys=[fisherman_id], backref="fishing_trips")
    catch_records  = db.relationship("CatchRecord", backref="trip", lazy=True,
                                      cascade="all, delete-orphan")

    @property
    def total_weight_kg(self):
        return sum(r.weight_kg for r in self.catch_records if r.weight_kg)

    @property
    def total_quantity(self):
        return sum(r.quantity for r in self.catch_records if r.quantity)

    @property
    def duration_hours(self):
        if self.end_datetime and self.start_datetime:
            delta = self.end_datetime - self.start_datetime
            return round(delta.total_seconds() / 3600, 1)
        return None

    def __repr__(self) -> str:
        return f"<FishingTrip {self.id} by user {self.fisherman_id}>"


# ============================================================
# CATCH RECORD
# ============================================================

class CatchRecord(db.Model):
    """One species catch entry within a fishing trip."""
    __tablename__ = "catch_record"

    id                = db.Column(db.Integer, primary_key=True)
    trip_id           = db.Column(db.Integer, db.ForeignKey("fishing_trip.id"), nullable=False)

    # Species — FK preferred, free-text fallback
    species_id        = db.Column(db.Integer, db.ForeignKey("species.id"), nullable=True)
    species_name_free = db.Column(db.String(150), nullable=True)  # if not in species table

    # Catch details
    quantity          = db.Column(db.Integer, nullable=False, default=1)
    weight_kg         = db.Column(db.Float, nullable=False)
    size_cm           = db.Column(db.Float, nullable=True)  # average/representative size

    # Gear
    gear_type_id      = db.Column(db.Integer, db.ForeignKey("gear_type.id"), nullable=True)

    notes             = db.Column(db.Text, nullable=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    species   = db.relationship("Species",  foreign_keys=[species_id],  backref="catch_records")
    gear_type = db.relationship("GearType", foreign_keys=[gear_type_id], backref="catch_records")

    @property
    def display_species(self):
        if self.species:
            return self.species.name_bg
        return self.species_name_free or "Unknown"

    def __repr__(self) -> str:
        return f"<CatchRecord trip={self.trip_id} species={self.display_species} {self.weight_kg}kg>"