from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import InputRequired, Length, EqualTo, Optional


class SignupForm(FlaskForm):
    email = StringField(
        "Addresse e-mail",
        render_kw={"placeholder": "Adresse e-mail"},
        validators=[InputRequired(), Length(min=6, max=100)],
    )

    password = PasswordField(
        "Mot de passe",
        render_kw={"placeholder": "Mot de passe (12 à 40 caractères)"},
        validators=[InputRequired(), Length(min=12, max=40)],
    )

    confirm = PasswordField(
        "Confirmation du mot de passe",
        render_kw={"placeholder": "Confirmation du mot de passe"},
        validators=[
            InputRequired(),
            Length(min=12, max=40),
            EqualTo(
                "password",
                message="Mot de passe incorrect.",
            ),
        ],
    )

    submit = SubmitField("Inscription")


class LoginForm(FlaskForm):
    email = StringField(
        "Addresse e-mail",
        render_kw={"placeholder": "Adresse e-mail"},
        validators=[InputRequired(), Length(min=6, max=100)],
    )

    password = PasswordField(
        "Mot de passe",
        render_kw={"placeholder": "Mot de passe (12 à 40 caractères)"},
        validators=[InputRequired(), Length(min=12, max=40)],
    )

    remember = BooleanField(
        "Se rappeler de moi",
        default=True,
        validators=[Optional()],
    )

    submit = SubmitField("Inscription")
