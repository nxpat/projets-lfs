from wtforms import Form, StringField, PasswordField
from wtforms.validators import InputRequired, Length, EqualTo


class SignupForm(Form):
    email = StringField("Email Address", [Length(min=6, max=100)])
    password = PasswordField(
        "New Password",
        validators=[InputRequired(), Length(min=12, max=21)],
    )
    confirm = StringField(
        label="Password confirm",
        validators=[
            InputRequired(),
            Length(min=12, max=21),
            EqualTo("password", message="Les mots de passe doivent être identiques"),
        ],
    )
