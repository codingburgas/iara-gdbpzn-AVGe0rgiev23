from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    SubmitField,
    SelectField,
    IntegerField,
    DateField
)
from wtforms.validators import DataRequired, Email, Length
from .models import PermitStatus, Vessel


# -------------------------
# Authentication Forms
# -------------------------

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class RegistrationForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[DataRequired()])
    role = SelectField(
        "Role",
        choices=[
            ("administrator", "Administrator"),
            ("inspector", "Inspector"),
            ("fisherman", "Fisherman"),
            ("amateur", "Amateur Fisher")
        ],
        validators=[DataRequired()]
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    submit = SubmitField("Register")


# -------------------------
# Vessel Form
# -------------------------

class VesselForm(FlaskForm):
    international_number = StringField(
        "International Number",
        validators=[DataRequired(), Length(max=50)]
    )

    call_sign = StringField(
        "Call Sign",
        validators=[DataRequired(), Length(max=50)]
    )

    marking = StringField(
        "Vessel Marking",
        validators=[DataRequired(), Length(max=50)]
    )

    length = IntegerField(
        "Length (meters)",
        validators=[DataRequired()]
    )

    width = IntegerField(
        "Width (meters)",
        validators=[DataRequired()]
    )

    engine_power = IntegerField(
        "Engine Power (HP)",
        validators=[DataRequired()]
    )

    owner_name = StringField(
        "Owner Name",
        validators=[DataRequired(), Length(max=100)]
    )

    captain_name = StringField(
        "Captain Name",
        validators=[DataRequired(), Length(max=100)]
    )

    submit = SubmitField("Save Vessel")


# -------------------------
# Permit Form (Commit 3)
# -------------------------

class PermitForm(FlaskForm):
    permit_number = StringField(
        "Permit Number",
        validators=[DataRequired(), Length(max=50)]
    )

    permit_type = SelectField(
        "Permit Type",
        choices=[
            ("Commercial", "Commercial"),
            ("Recreational", "Recreational"),
            ("Scientific", "Scientific"),
            ("Transport", "Transport")
        ],
        validators=[DataRequired()]
    )

    vessel_id = SelectField(
        "Vessel",
        coerce=int,
        validators=[DataRequired()]
    )

    issue_date = DateField(
        "Issue Date",
        validators=[DataRequired()]
    )

    expiry_date = DateField(
        "Expiry Date",
        validators=[DataRequired()]
    )

    status = SelectField(
        "Status",
        choices=[(s.value, s.value) for s in PermitStatus],
        validators=[DataRequired()]
    )

    submit = SubmitField("Create Permit")

    def set_vessel_choices(self):
        """Populate vessel dropdown dynamically."""
        self.vessel_id.choices = [
            (v.id, f"{v.international_number} — {v.call_sign}")
            for v in Vessel.query.all()
        ]
