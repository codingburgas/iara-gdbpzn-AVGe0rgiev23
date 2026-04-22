from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (
    StringField, PasswordField, SubmitField,
    SelectField, IntegerField, FloatField, DateField,
    BooleanField, TextAreaField, TelField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo,
    Optional, ValidationError, Regexp
)
from .models import PermitStatus, VesselStatus, Vessel


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
# ADMIN USER MANAGEMENT FORMS
# ============================================================

ROLE_CHOICES = [
    ("administrator", "Administrator"),
    ("inspector",     "Inspector"),
    ("fisherman",     "Fisherman"),
    ("amateur",       "Amateur Fisher"),
]


class CreateUserForm(FlaskForm):
    """Admin creates a new user account with any role."""
    first_name = StringField("First Name",  validators=[DataRequired(), Length(max=50)])
    last_name  = StringField("Last Name",   validators=[DataRequired(), Length(max=50)])
    email      = StringField("Email",       validators=[DataRequired(), Email(), Length(max=120)])
    phone      = StringField("Phone",       validators=[DataRequired(), Length(max=20)])
    role       = SelectField("Role",        choices=ROLE_CHOICES, validators=[DataRequired()])
    password   = PasswordField("Password",  validators=[DataRequired(), Length(min=8, message="Minimum 8 characters")])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match")]
    )
    is_active  = BooleanField("Active account", default=True)
    submit     = SubmitField("Create User")


class EditUserForm(FlaskForm):
    """Admin edits an existing user's profile, role, and active status."""
    first_name = StringField("First Name",  validators=[DataRequired(), Length(max=50)])
    last_name  = StringField("Last Name",   validators=[DataRequired(), Length(max=50)])
    email      = StringField("Email",       validators=[DataRequired(), Email(), Length(max=120)])
    phone      = StringField("Phone",       validators=[DataRequired(), Length(max=20)])
    role       = SelectField("Role",        choices=ROLE_CHOICES, validators=[DataRequired()])
    is_active  = BooleanField("Account Active")
    submit     = SubmitField("Save Changes")


# ============================================================
# VESSEL FORM
# ============================================================

class VesselForm(FlaskForm):
    # ── Identity ───────────────────────────────────────────
    international_number = StringField("International Number *", validators=[DataRequired(), Length(max=50)])
    call_sign            = StringField("Call Sign *",            validators=[DataRequired(), Length(max=50)])
    marking              = StringField("External Marking *",     validators=[DataRequired(), Length(max=50)])
    name_bg              = StringField("Name (Bulgarian)",       validators=[Optional(), Length(max=150)])
    name_en              = StringField("Name (English)",         validators=[Optional(), Length(max=150)])

    # ── Registration ───────────────────────────────────────
    port_registration = StringField("Port of Registration",   validators=[Optional(), Length(max=100)])
    registration_date = DateField("Registration Date",        validators=[Optional()])
    status            = SelectField("Status *",
                            choices=[(s.value, s.value) for s in VesselStatus],
                            validators=[DataRequired()])

    # ── Dimensions ─────────────────────────────────────────
    length        = FloatField("Length (m) *",      validators=[DataRequired()])
    width         = FloatField("Width (m) *",       validators=[DataRequired()])
    gross_tonnage = FloatField("Gross Tonnage (GT)", validators=[Optional()])
    engine_power  = IntegerField("Engine Power (HP) *", validators=[DataRequired()])

    # ── Ownership ──────────────────────────────────────────
    owner_name   = StringField("Owner Name *",   validators=[DataRequired(), Length(max=100)])
    owner_egn    = StringField("Owner EGN",      validators=[Optional(), Length(max=20)])
    captain_name = StringField("Captain Name *", validators=[DataRequired(), Length(max=100)])

    submit = SubmitField("Save Vessel")


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


# ============================================================
# VESSEL DOCUMENT UPLOAD FORM
# ============================================================

class VesselDocumentUploadForm(FlaskForm):
    doc_type = SelectField("Document Type", choices=[
        ("Certificate",       "Certificate"),
        ("Insurance",         "Insurance"),
        ("Registration",      "Registration"),
        ("Inspection Report", "Inspection Report"),
        ("Other",             "Other"),
    ], validators=[DataRequired()])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])
    file  = FileField("File *", validators=[
        FileRequired(),
        FileAllowed(["pdf", "doc", "docx", "jpg", "jpeg", "png"],
                    "Allowed: PDF, DOC, DOCX, JPG, PNG")
    ])
    submit = SubmitField("Upload Document")


# ============================================================
# VESSEL PHOTO UPLOAD FORM
# ============================================================

class VesselPhotoUploadForm(FlaskForm):
    caption    = StringField("Caption", validators=[Optional(), Length(max=255)])
    is_primary = BooleanField("Set as primary photo")
    file       = FileField("Photo *", validators=[
        FileRequired(),
        FileAllowed(["jpg", "jpeg", "png", "webp"], "Allowed: JPG, PNG, WEBP")
    ])
    submit = SubmitField("Upload Photo")


# ============================================================
# VESSEL OWNERSHIP HISTORY FORM
# ============================================================

class VesselOwnershipForm(FlaskForm):
    owner_name = StringField("Owner Name *", validators=[DataRequired(), Length(max=100)])
    owner_egn  = StringField("Owner EGN",    validators=[Optional(), Length(max=20)])
    from_date  = DateField("From Date *",    validators=[DataRequired()])
    to_date    = DateField("To Date",        validators=[Optional()])
    notes      = TextAreaField("Notes",      validators=[Optional(), Length(max=500)])
    submit     = SubmitField("Record Transfer")

