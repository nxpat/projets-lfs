import secrets
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    current_app,
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user

from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import MismatchingStateError

from .models import db, Dashboard, User, Personnel
from .decorators import require_unlocked_db
from .registration import SignupForm, LoginForm

logger = logging.getLogger(__name__)

auth = Blueprint("auth", __name__)

# Initialize OAuth WITHOUT current_app to avoid context errors
oauth = OAuth()
google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    base_url="https://www.google.com/accounts/",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params=None,
    access_token_url="https://accounts.google.com/o/oauth2/token",
    access_token_params=None,
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    userinfo_endpoint="https://openidconnect.googleapis.com/v1/userinfo",
    client_kwargs={"scope": "openid email profile"},
    jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
)


@auth.route("/google_login")
def google_login():
    redirect_uri = url_for("auth.authorize", _external=True)
    return google.authorize_redirect(redirect_uri)


@auth.route("/authorize")
def authorize():
    try:
        token = oauth.google.authorize_access_token()
    except MismatchingStateError:
        # Catch the phantom duplicate requests
        # If they are already logged in, just send them home safely.
        if current_user.is_authenticated:
            return redirect(url_for("core.index"))

        # If they aren't logged in, something actually went wrong. Send them to login.
        flash("La session a expiré. Veuillez vous reconnecter", "warning")
        return redirect(url_for("core.index"))

    user_info = token["userinfo"]

    if not user_info.email_verified:
        flash(
            "Votre adresse e-mail n'est pas vérifiée. Veuillez la valider auprès de Google et ré-essayer.",
            "warning",
        )
        return redirect(url_for("core.index"))

    # Only authorized users can register
    personnel = Personnel.query.filter_by(email=user_info.email).first()
    if not personnel:
        flash("Ce compte n'est pas autorisé.", "danger")
        return redirect(url_for("core.index"))

    # If this returns a User, then the user has already registered
    user = db.session.query(User).join(Personnel).filter(Personnel.email == user_info.email).first()

    if not user:
        dash = Dashboard.query.first()
        if dash and dash.lock >= 2:
            flash(
                "La création de nouveaux comptes est temporairement suspendue pour maintenance. Veuillez ré-essayer plus tard.",
                "warning",
            )
            return redirect(url_for("core.index"))

        new_user = User(
            password=generate_password_hash(secrets.token_hex(20), method="pbkdf2:sha1"),
            date_registered=datetime.now(tz=ZoneInfo("Asia/Seoul")),
        )

        # associate the User with the Personnel record
        personnel.user = new_user

        db.session.add(new_user)
        db.session.commit()

        user = (
            db.session.query(User)
            .join(Personnel)
            .filter(Personnel.email == user_info.email)
            .first()
        )
        logger.info(f"New user registered ({user_info.email})")

    login_user(user, remember=True)
    return redirect(url_for("projects.list_projects"))


@auth.route("/login", methods=["GET", "POST"])
def login():
    # UPDATED: Dynamically check the environment
    if current_app.config.get("FLASK_ENV") == "production":
        return redirect(url_for("auth.google_login"))

    form = LoginForm()

    if form.validate_on_submit():
        user = (
            db.session.query(User)
            .join(Personnel)
            .filter(Personnel.email == form.email.data)
            .first()
        )

        if not user or not check_password_hash(user.password, form.password.data):
            flash("Veuillez vérifier vos identifiants et ré-essayer.", "warning")
            return redirect(url_for("auth.login"))

        login_user(user, remember=form.remember.data)
        return redirect(url_for("projects.list_projects"))

    return render_template("login.html", form=form)


@auth.route("/signup", methods=["GET", "POST"])
@require_unlocked_db(level=2)
def signup():
    if current_app.config.get("FLASK_ENV") == "production":
        return redirect(url_for("auth.google_login"))

    form = SignupForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        personnel = Personnel.query.filter_by(email=email).first()
        if not personnel:
            flash("Cette adresse e-mail n'est pas reconnue.", "danger")
            return redirect(url_for("auth.signup"))

        # if this returns a user, then the email already exists in database
        user = db.session.query(User).join(Personnel).filter(Personnel.email == email).first()

        # if a user is found, we want to redirect back to signup page so user can try again
        if user:
            flash("Cette adresse e-mail est déjà utilisée.", "danger")
            return redirect(url_for("auth.signup"))

        # create a new user with the form data
        # hash the password so the plaintext version isn't saved
        new_user = User(
            password=generate_password_hash(password, method="pbkdf2:sha1"),
            date_registered=datetime.now(tz=ZoneInfo("Asia/Seoul")),
        )

        # associate the User with the Personnel record
        personnel.user = new_user

        db.session.add(new_user)
        db.session.commit()

        logger.info(f"New user registered ({email})")
        return redirect(url_for("auth.login"))

    return render_template("signup.html", form=form)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté avec succès.", "info")
    return redirect(url_for("core.index"))
