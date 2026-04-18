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
    international_number = db.Column(db.String(50), nullable=False)
    call_sign = db.Column(db.String(50), nullable=False)
    marking = db.Column(db.String(50), nullable=False)
    length = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=False)
    engine_power = db.Column(db.Integer, nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    captain_name = db.Column(db.String(100), nullable=False)

    permits = db.relationship("Permit", backref="vessel", lazy=True)
    inspections = db.relationship("Inspection", backref="vessel", lazy=True)
    scheduled_inspections = db.relationship("ScheduledInspection", backref="vessel", lazy=True)

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

    violations = db.relationship("Violation", backref="violation_code", lazy=True)

    def __repr__(self) -> str:
        return f"<ViolationCode {self.code}>"


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