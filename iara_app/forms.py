from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class RegistrationForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired()])
    last_name = StringField("Last Name", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[DataRequired()])
    role = SelectField("Role", choices=[
        ("administrator", "Administrator"),
        ("inspector", "Inspector"),
        ("fisherman", "Fisherman"),
        ("amateur", "Amateur Fisher")
    ])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    submit = SubmitField("Register")

from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Length

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
