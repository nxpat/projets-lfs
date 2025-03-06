from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    current_app,
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user

from authlib.integrations.flask_client import OAuth

from .models import User, Personnel
from .registration import SignupForm
from . import db, production_env

from datetime import datetime
from zoneinfo import ZoneInfo

import os

import secrets

import logging

AUTHOR = os.getenv("AUTHOR")
REFERENT_NUMERIQUE_EMAIL = os.getenv("REFERENT_NUMERIQUE_EMAIL")
GITHUB_REPO = os.getenv("GITHUB_REPO")
LFS_LOGO = os.getenv("LFS_LOGO")
LFS_WEBSITE = os.getenv("LFS_WEBSITE")

logger = logging.getLogger(__name__)

auth = Blueprint("auth", __name__)

oauth = OAuth(current_app)
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


@auth.context_processor
def utility_processor():
    return dict(
        AUTHOR=AUTHOR,
        REFERENT_NUMERIQUE_EMAIL=REFERENT_NUMERIQUE_EMAIL,
        GITHUB_REPO=GITHUB_REPO,
        LFS_LOGO=LFS_LOGO,
        LFS_WEBSITE=LFS_WEBSITE,
    )


@auth.route("/google_login")
def google_login():
    redirect_uri = url_for("auth.authorize", _external=True)
    return google.authorize_redirect(redirect_uri)


@auth.route("/authorize")
def authorize():
    token = oauth.google.authorize_access_token()
    user_info = token["userinfo"]

    if not user_info.email_verified:
        flash("Vérifiez vos identifiants et ré-essayez.")
        return redirect(url_for("auth.google_login"))

    # only authorized users can register
    personnel = Personnel.query.filter_by(email=user_info.email).first()
    if not personnel:
        flash("Ce compte n'est pas autorisé.")
        return render_template("index.html")

    # if this returns a User, then the user has already registered
    user = (
        db.session.query(User)
        .join(Personnel)
        .filter(Personnel.email == user_info.email)
        .first()
    )

    # create a new user with the form data.
    # generate a hashed random password (useless logging with OAuth, but required by the database model)
    if not user:
        new_user = User(
            password=generate_password_hash(secrets.token_hex(20), method="pbkdf2:sha1"),
            date_registered=datetime.now(tz=ZoneInfo("Asia/Seoul")),
        )

        # associate the User with the Personnel record
        personnel.user = new_user

        # add the new user to the database
        db.session.add(new_user)
        db.session.commit()
        user = (
            db.session.query(User)
            .join(Personnel)
            .filter(Personnel.email == user_info.email)
            .first()
        )
        logger.info(f"New user registered ({user_info.email})")

    # if the above check passes, then we know the user has the right credentials
    login_user(user, remember=True)

    return redirect(url_for("main.projects"))


@auth.route("/login")
def login():
    if production_env:
        return redirect(url_for("auth.google_login"))

    return render_template("login.html")


@auth.route("/login", methods=["POST"])
def login_post():
    if production_env:
        return redirect(url_for("auth.google_login"))

    # login code goes here
    email = request.form.get("email")
    password = request.form.get("password")
    remember = True if request.form.get("remember") else False

    user = db.session.query(User).join(Personnel).filter(Personnel.email == email).first()

    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or not check_password_hash(user.password, password):
        flash("Veuiller vérifier vos identifiants et ré-essayer")
        return redirect(
            url_for("auth.login")
        )  # if the user doesn't exist or password is wrong, reload the page

    # if the above check passes, then we know the user has the right credentials
    login_user(user, remember=remember)

    return redirect(url_for("main.projects"))


@auth.route("/signup")
def signup():
    if production_env:
        return redirect(url_for("auth.google_login"))

    return render_template("signup.html")


@auth.route("/signup", methods=["POST"])
def signup_post():
    if production_env:
        return redirect(url_for("auth.google_login"))

    form = SignupForm()
    # validate and add user to database
    email = request.form.get("email")
    password = request.form.get("password")

    # only authorized users can register
    personnel = Personnel.query.filter_by(email=email).first()
    if not personnel:
        flash("Cette adresse e-mail n'est pas reconnue.")
        return redirect(url_for("auth.signup"))

    # if this returns a user, then the email already exists in database
    user = db.session.query(User).join(Personnel).filter(Personnel.email == email).first()

    # if a user is found, we want to redirect back to signup page so user can try again
    if user:
        flash("Cette adresse e-mail est déjà utilisée")
        return redirect(url_for("auth.signup"))

    # create a new user with the form data
    # hash the password so the plaintext version isn't saved
    new_user = User(
        password=generate_password_hash(password, method="pbkdf2:sha1"),
        date_registered=datetime.now(tz=ZoneInfo("Asia/Seoul")),
    )

    # associate the User with the Personnel record
    personnel.user = new_user

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()

    logger.info(f"New user registered ({email})")

    return redirect(url_for("auth.login"))


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    if production_env:
        return redirect("https://www.google.com/accounts/Logout")
    else:
        return redirect(url_for("main.index"))
