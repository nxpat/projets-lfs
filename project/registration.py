from wtforms import Form, BooleanField, StringField, PasswordField, validators


class SignupForm(Form):
    email = StringField("Email Address", [validators.Length(min=6, max=35)])
    password = PasswordField(
        "New Password",
        validators=[validators.DataRequired(), validators.Length(min=6, max=12)],
    )
    confirm = StringField(
        label="Password confirm",
        validators=[
            validators.DataRequired(),
            validators.Length(min=6, max=12),
            validators.EqualTo("password", message="Passwords must match"),
        ],
    )
