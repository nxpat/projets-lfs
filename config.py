import os
from pathlib import Path
from dotenv import load_dotenv

# Determine the absolute path of base directory of the project
BASE_DIR = Path(__file__).resolve().parent

env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)


class Config(object):
    """Base config."""

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-secret-key")

    # Sessions
    REMEMBER_COOKIE_DURATION = 4233600  # 7 days
    SESSION_PROTECTION = "strong"
    SESSION_CLEANUP_N_REQUESTS = 100

    # Flask Folders
    STATIC_FOLDER = "static"
    TEMPLATES_FOLDER = "templates"

    # SQLAlchemy Base
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Suppresses a deprecation warning and saves memory


class DevConfig(Config):
    """Development config."""

    FLASK_ENV = "development"
    FLASK_DEBUG = True

    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"

    # Paths
    APP_PATH = BASE_DIR / os.getenv("APPLICATION_PACKAGE", "app")
    DATA_PATH = APP_PATH / os.getenv("DATA_DIR", "data")

    # Local Database (SQLite)
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URI", "sqlite:///db.dev.sqlite")


class ProdConfig(Config):
    """Production config."""

    FLASK_ENV = "production"
    FLASK_DEBUG = False

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Paths
    APP_PATH = BASE_DIR / os.getenv("APPLICATION_PACKAGE", "app")
    DATA_PATH = APP_PATH / os.getenv("DATA_DIR", "data")

    # Production Database (MySQL)
    SQLALCHEMY_DATABASE_URI = os.getenv("PROD_DATABASE_URI")
