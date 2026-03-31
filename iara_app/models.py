from datetime import datetime
from flask_login import UserMixin
from . import db
import bcrypt


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

    inspector_id = db.Column(db.String(50))

    id_number = db.Column(db.String(50))
    age_category = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode("utf-8"), self.password_hash.encode("utf-8")
        )

    def get_id(self):
        return str(self.id)


class Vessel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    international_number = db.Column(db.String(50), nullable=False)
    call_sign = db.Column(db.String(50), nullable=False)
    marking = db.Column(db.String(50), nullable=False)
    length = db.Column(db.Integer, nullable=False)
    width = db.Column(db.Integer, nullable=False)
    engine_power = db.Column(db.Integer, nullable=False)
    owner_name = db.Column(db.String(100), nullable=False)
    captain_name = db.Column(db.String(100), nullable=False)


from . import db
from datetime import date
from enum import Enum


class PermitStatus(Enum):
    ACTIVE = "Active"
    EXPIRED = "Expired"
    SUSPENDED = "Suspended"


class Permit(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Relationship to Vessel
    vessel_id = db.Column(db.Integer, db.ForeignKey('vessel.id'), nullable=False)
    vessel = db.relationship('Vessel', backref=db.backref('permits', lazy=True))

    permit_number = db.Column(db.String(50), nullable=False, unique=True)
    permit_type = db.Column(db.String(50), nullable=False)

    issue_date = db.Column(db.Date, nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)

    status = db.Column(db.String(20), nullable=False, default=PermitStatus.ACTIVE.value)

    def is_expired(self):
        return date.today() > self.expiry_date

