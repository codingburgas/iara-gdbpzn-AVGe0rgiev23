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
from .models import PermitStatus, VesselStatus, Vessel, ViolationCategory, ViolationSeverity


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
    id_number = StringField("ID Number", validators=[DataRequired()])
    age_category = SelectField(
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


# ============================================================
# LOOKUP DATA FORMS
# ============================================================

SEASON_MONTH_DAYS = [
    ("", "— select —"),
    ("01-01", "01 Jan"), ("01-02", "01 Feb"), ("01-03", "01 Mar"),
    ("01-04", "01 Apr"), ("01-05", "01 May"), ("01-06", "01 Jun"),
    ("01-07", "01 Jul"), ("01-08", "01 Aug"), ("01-09", "01 Sep"),
    ("01-10", "01 Oct"), ("01-11", "01 Nov"), ("01-12", "01 Dec"),
    ("15-01", "15 Jan"), ("15-02", "15 Feb"), ("15-03", "15 Mar"),
    ("15-04", "15 Apr"), ("15-05", "15 May"), ("15-06", "15 Jun"),
    ("15-07", "15 Jul"), ("15-08", "15 Aug"), ("15-09", "15 Sep"),
    ("15-10", "15 Oct"), ("15-11", "15 Nov"), ("15-12", "15 Dec"),
    ("31-01", "31 Jan"), ("28-02", "28 Feb"), ("31-03", "31 Mar"),
    ("30-04", "30 Apr"), ("31-05", "31 May"), ("30-06", "30 Jun"),
    ("31-07", "31 Jul"), ("31-08", "31 Aug"), ("30-09", "30 Sep"),
    ("31-10", "31 Oct"), ("30-11", "30 Nov"), ("31-12", "31 Dec"),
]


class SpeciesForm(FlaskForm):
    name_bg         = StringField("Bulgarian Name *",   validators=[DataRequired(), Length(max=150)])
    name_en         = StringField("English Name",       validators=[Optional(), Length(max=150)])
    scientific_name = StringField("Scientific Name",    validators=[Optional(), Length(max=200)])

    min_size_cm     = FloatField("Min Size (cm)",       validators=[Optional()])
    max_size_cm     = FloatField("Max Size (cm)",       validators=[Optional()])

    season_start    = SelectField("Season Start",       choices=SEASON_MONTH_DAYS, validators=[Optional()])
    season_end      = SelectField("Season End",         choices=SEASON_MONTH_DAYS, validators=[Optional()])

    daily_limit_kg  = FloatField("Daily Limit (kg)",    validators=[Optional()])
    is_protected    = BooleanField("Fully Protected Species")
    notes           = TextAreaField("Notes",            validators=[Optional(), Length(max=2000)])
    submit          = SubmitField("Save Species")


class GearTypeForm(FlaskForm):
    code               = StringField("Gear Code *",          validators=[DataRequired(), Length(max=20)])
    name               = StringField("Gear Name *",          validators=[DataRequired(), Length(max=150)])
    description        = TextAreaField("Description",         validators=[Optional(), Length(max=2000)])
    mesh_size_required = BooleanField("Mesh Size Declaration Required")
    min_mesh_size_mm   = FloatField("Min Mesh Size (mm)",     validators=[Optional()])
    is_legal           = BooleanField("Legal / Permitted Gear", default=True)
    submit             = SubmitField("Save Gear Type")


class ViolationCategoryForm(FlaskForm):
    name   = StringField("Category Name *", validators=[DataRequired(), Length(max=100)])
    submit = SubmitField("Save Category")


class ViolationCodeForm(FlaskForm):
    code            = StringField("Code *",              validators=[DataRequired(), Length(max=20)])
    title           = StringField("Title *",             validators=[DataRequired(), Length(max=255)])
    description     = TextAreaField("Description",       validators=[Optional()])
    category_id     = SelectField("Category *",          coerce=int, validators=[DataRequired()])
    default_severity = SelectField(
        "Default Severity *",
        choices=[(s.value, s.value) for s in ViolationSeverity],
        validators=[DataRequired()]
    )
    law_article     = StringField("Law Article",         validators=[Optional(), Length(max=100)])
    default_penalty = FloatField("Default Penalty (EUR)", validators=[Optional()])
    submit          = SubmitField("Save Violation Code")

    def set_category_choices(self):
        self.category_id.choices = [
            (c.id, c.name) for c in ViolationCategory.query.order_by(ViolationCategory.name).all()
        ]


class SpeciesCSVImportForm(FlaskForm):
    csv_file = FileField("CSV File *", validators=[
        FileRequired(),
        FileAllowed(["csv"], "Only .csv files are accepted.")
    ])
    submit = SubmitField("Import Species")