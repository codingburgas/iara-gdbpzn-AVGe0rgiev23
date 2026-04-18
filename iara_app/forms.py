from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField,
    SelectField, IntegerField, DateField,
    BooleanField, TextAreaField, TelField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo,
    Optional, ValidationError
)
from .models import PermitStatus, Vessel


# ============================================================
# AUTH FORMS
# ============================================================

class LoginForm(FlaskForm):
    email    = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit   = SubmitField("Sign In")


class RegistrationForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[DataRequired()])
    id_number = StringField("ID Number", validators=[DataRequired()])  # ADD THIS
    age_category = SelectField(  # ADD THIS
        "Age Category",
        choices=[
            ("Adult", "Adult"),
            ("Senior", "Senior"),
            ("Youth", "Youth")
        ],
        validators=[DataRequired()]
    )
    role = SelectField(
        "Register As",
        choices=[
            ("fisherman", "Fisherman"),
            ("amateur", "Amateur Fisher")
        ],
        validators=[DataRequired()]
    )
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField("Confirm Password", validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField("Register")


class ProfileEditForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=50)])
    last_name  = StringField("Last Name",  validators=[DataRequired(), Length(max=50)])
    phone      = StringField("Phone",      validators=[DataRequired(), Length(max=20)])
    vessel_registration    = StringField("Vessel Registration Number", validators=[Optional(), Length(max=50)])
    fishing_permit_number  = StringField("Fishing Permit Number",      validators=[Optional(), Length(max=50)])
    submit = SubmitField("Save Changes")


class ChangePasswordForm(FlaskForm):
    current_password  = PasswordField("Current Password", validators=[DataRequired()])
    new_password      = PasswordField("New Password",
                            validators=[DataRequired(), Length(min=8, message="Minimum 8 characters")])
    confirm_password  = PasswordField("Confirm New Password",
                            validators=[DataRequired(), EqualTo("new_password", message="Passwords must match")])
    submit = SubmitField("Change Password")


class ForgotPasswordForm(FlaskForm):
    email  = StringField("Email Address", validators=[DataRequired(), Email()])
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    new_password     = PasswordField("New Password",
                           validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm Password",
                           validators=[DataRequired(), EqualTo("new_password", message="Passwords must match")])
    submit = SubmitField("Reset Password")


# ============================================================
# VESSEL FORM
# ============================================================

class VesselForm(FlaskForm):
    international_number = StringField("International Number", validators=[DataRequired(), Length(max=50)])
    call_sign            = StringField("Call Sign",            validators=[DataRequired(), Length(max=50)])
    marking              = StringField("Vessel Marking",       validators=[DataRequired(), Length(max=50)])
    length               = IntegerField("Length (m)",          validators=[DataRequired()])
    width                = IntegerField("Width (m)",           validators=[DataRequired()])
    engine_power         = IntegerField("Engine Power (HP)",   validators=[DataRequired()])
    owner_name           = StringField("Owner Name",           validators=[DataRequired(), Length(max=100)])
    captain_name         = StringField("Captain Name",         validators=[DataRequired(), Length(max=100)])
    submit               = SubmitField("Save Vessel")


# ============================================================
# PERMIT FORM
# ============================================================

class PermitForm(FlaskForm):
    permit_number = StringField("Permit Number",  validators=[DataRequired(), Length(max=50)])
    permit_type   = SelectField("Permit Type",
                        choices=[
                            ("Commercial",    "Commercial"),
                            ("Recreational",  "Recreational"),
                            ("Scientific",    "Scientific"),
                            ("Transport",     "Transport"),
                        ],
                        validators=[DataRequired()])
    vessel_id     = SelectField("Vessel", coerce=int, validators=[DataRequired()])
    issue_date    = DateField("Issue Date",   validators=[DataRequired()])
    expiry_date   = DateField("Expiry Date",  validators=[DataRequired()])
    status        = SelectField("Status",
                        choices=[(s.value, s.value) for s in PermitStatus],
                        validators=[DataRequired()])
    submit        = SubmitField("Save Permit")

    def set_vessel_choices(self):
        self.vessel_id.choices = [
            (v.id, f"{v.international_number} — {v.call_sign}")
            for v in Vessel.query.all()
        ]
