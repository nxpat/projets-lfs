#
# author: patrice houlet
# created: Mon 08 Jul 2024
# license: GPL-v3
#
# Projets LFS : application Web pour la
# saisie et gestion des projets pédagogiques au LFS
#
# import sys
import os
from pathlib import Path
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from flask import Flask, flash, redirect, url_for
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_babel import Babel

from .babel import configure, get_locale
from ._version import __version__, __version_date__
from .models import db, User
from .google_api_service import create_service

from .template_filters import register_template_filters

# absolute path of the app
CURRENT_DIR = Path(__file__).resolve().parent

# Load environment variables early
env_path = CURRENT_DIR.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize global extensions (unbound to app)
login_manager = LoginManager()
babel = Babel()

# Initialize GMail Service (kept global so other modules can import it)
gmail_enabled = os.getenv("USE_GMAIL_SERVICE", "True").lower() in ("true", "1")

# Determine base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

if gmail_enabled:
    CLIENT_SECRET_FILE = CURRENT_DIR.parent / os.getenv("CLIENT_SECRET_FILE", "credentials.json")
    TOKEN_FILE = CURRENT_DIR.parent / os.getenv("TOKEN_FILE", "token.json")
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
    if CLIENT_SECRET_FILE:
        gmail_service_api = create_service(CLIENT_SECRET_FILE, TOKEN_FILE, "gmail", "v1", SCOPES)
    else:
        print("Attention: CLIENT_SECRET_FILE not found in environment.")
        gmail_service_api = None
else:
    print("Attention: GMail service not started.")
    gmail_service_api = None


def setup_logger(is_production):
    """Configures and returns the application logger."""
    log_level = logging.INFO if is_production else logging.DEBUG

    # Always log to the file
    handlers = [logging.FileHandler(BASE_DIR / "app.log", encoding="utf-8", mode="a")]

    # In development, also print logs to the terminal
    # if not is_production:
    #     handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(name)-12s %(levelname)-8s %(message)s",
        handlers=handlers,
    )

    logging.Formatter.converter = lambda *args: datetime.now(tz=ZoneInfo("Asia/Seoul")).timetuple()
    return logging.getLogger(__name__)


def create_app():
    """Application factory function."""

    # 1. Determine Environment
    # Set FLASK_ENV=production or FLASK_ENV=development in .env file
    env = os.getenv("FLASK_ENV", "production")
    is_production = env == "production"

    # 2. Setup Logging
    logger = setup_logger(is_production)
    logger.info(
        f"Projets LFS version {__version__} - {__version_date__} - {env.capitalize()} - started..."
    )

    # 3. Create App Instance
    app = Flask(__name__)

    # Tell Flask it is behind a secure proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # 4. Load Configurations
    if is_production:
        app.config.from_object("config.ProdConfig")
    else:
        app.config.from_object("config.DevConfig")

    # 5. Initialize Database (Connects to the SQL URI defined in config)
    db.init_app(app)

    # 6. Initialize App Extensions
    configure(app)
    babel.init_app(app, locale_selector=get_locale)
    register_template_filters(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))  # Optimized lookup

    @login_manager.unauthorized_handler
    def unauthorized():
        # Gracefully tell the user their session expired or they need to log in
        flash("Veuillez vous connecter pour accéder à cette page.", "warning")
        return redirect(url_for("core.index"))

    # 7. Register Blueprints & Errors
    from .auth import auth as auth_blueprint, oauth

    app.register_blueprint(auth_blueprint)
    oauth.init_app(app)  # Initialize it with the app

    from .routes.core import core_bp

    app.register_blueprint(core_bp)

    from .routes.projects import projects_bp

    app.register_blueprint(projects_bp)

    from .routes.admin import admin_bp

    app.register_blueprint(admin_bp)

    from .errors import register_error_handlers

    register_error_handlers(app)

    # 8. Create Tables (Development only)
    if not is_production:
        with app.app_context():
            db.create_all()

    return app
