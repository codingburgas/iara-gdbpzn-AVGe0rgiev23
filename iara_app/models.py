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

    # Roles: administrator, inspector, fisherman, amateur
    role = db.Column(db.String(50), nullable=False)

    password_hash = db.Column(db.String(128), nullable=False)

    # Optional fields for fishermen / amateurs
    vessel_registration = db.Column(db.String(50))
    fishing_permit_number = db.Column(db.String(50))

    # Optional external inspector identifier (badge, internal ID, etc.)
    inspector_id = db.Column(db.String(50))

    id_number = db.Column(db.String(50))
    age_category = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationship: Inspector → Inspections
    inspections = db.relationship("Inspection", backref="inspector", lazy=True)

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
    international_number = db.Column(db.String(50), nullable=False)
    call_sign = db.Column(db.String(50), nullable=False)
    marking = db.Column(db.String(50), nullable=False)
    length = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=False)
    engine_power = db.Column(db.Integer, nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    captain_name = db.Column(db.String(100), nullable=False)

    # Vessel → Permits
    permits = db.relationship("Permit", backref="vessel", lazy=True)

    # Vessel → Inspections
    inspections = db.relationship("Inspection", backref="vessel", lazy=True)

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
    code = db.Column(db.String(20), unique=True, nullable=False)  # e.g. V-001
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

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

    violations = db.relationship("Violation", backref="violation_code", lazy=True)

    def __repr__(self) -> str:
        return f"<ViolationCode {self.code}>"


# ============================================================
# INSPECTION
# ============================================================

def generate_inspection_id() -> str:
    now = datetime.utcnow()
    return f"INSP-{now.year}-{int(now.timestamp())}"


class Inspection(db.Model):
    __tablename__ = "inspections"

    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(
        db.String(50),
        unique=True,
        nullable=False,
        default=generate_inspection_id
    )

    vessel_id = db.Column(
        db.Integer,
        db.ForeignKey("vessel.id"),
        nullable=False
    )
    inspector_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    date = db.Column(db.Date, nullable=False, default=date.today)
    location = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Snapshot of permit status at inspection time
    permit_status_snapshot = db.Column(db.String(50), nullable=True)

    # Overall inspection score (0–100)
    score = db.Column(db.Integer, nullable=False, default=100)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    violations = db.relationship(
        "Violation",
        backref="inspection",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Inspection {self.inspection_id}>"


# ============================================================
# VIOLATION
# ============================================================

class Violation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey("inspection.id"), nullable=False)
    violation_code_id = db.Column(db.Integer, db.ForeignKey("violation_code.id"))
    severity = db.Column(db.String(20))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # NEW FIELDS FOR RESOLUTION WORKFLOW
    status = db.Column(db.String(20), default="open")
    resolution_notes = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime)

    # Relationship
    evidence = db.relationship("Evidence", backref="violation", lazy=True)



# ============================================================
# EVIDENCE
# ============================================================

class Evidence(db.Model):
    __tablename__ = "evidence"

    id = db.Column(db.Integer, primary_key=True)

    violation_id = db.Column(
        db.Integer,
        db.ForeignKey("violations.id"),
        nullable=False
    )
    file_path = db.Column(db.String(255), nullable=True)
    note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Evidence {self.id}>"
