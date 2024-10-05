#
# author: patrice houlet
# created: Mon 08 Jul 2024
# license: GPL-v3
# http://www.gnu.org/licenses/
#
# Projets LFS : application Web pour la
# saisie et gestion des projets pédagogiques au LFS
#
from ._version import __version__


from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

import logging

from datetime import datetime
from zoneinfo import ZoneInfo

from flask_babel import Babel
from .babel import configure, get_locale

from .google_api_service import create_service

import os

# set logging
app_log = True

# init SQLAlchemy so we can use it later in our models
db = SQLAlchemy()

# init GMail API
CLIENT_SECRET_FILE = os.getenv("CLIENT_SECRET_FILE")
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
service = create_service(CLIENT_SECRET_FILE, "gmail", "v1", SCOPES)

# init logger
logger = logging.getLogger(__name__)


def create_app():
    if app_log:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
            filename="app.log",
            filemode="w",
        )
        logging.Formatter.converter = lambda *args: datetime.now(
            tz=ZoneInfo("Asia/Seoul")
        ).timetuple()

    logger.info("Started...")

    # create a Flask instance
    app = Flask(__name__)

    # Babel
    configure(app)
    babel = Babel(app, locale_selector=get_locale)

    app.config.from_object("config.DevConfig")

    # Session(app)

    # initialise database session
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return User.query.get(int(user_id))

    # when using Google login
    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect(url_for("auth.google_login"))

    # blueprint for auth routes in our app
    from .auth import auth as auth_blueprint

    app.register_blueprint(auth_blueprint)

    # blueprint for non-auth parts of app
    from .main import main as main_blueprint

    app.register_blueprint(main_blueprint)

    # first execution only
    from . import models

    with app.app_context():
        db.create_all()

    return app
