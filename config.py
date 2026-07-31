import os
from pathlib import Path

from dotenv import load_dotenv

# Determine the absolute path of base directory of the project
BASE_DIR = Path(__file__).resolve().parent

env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)


class Config:
    """Base config."""

    # Flask Secret Key
    SECRET_KEY = os.getenv("SECRET_KEY")

    # Sessions
    REMEMBER_COOKIE_DURATION = 4233600  # 7 days
    SESSION_PROTECTION = "strong"
    SESSION_CLEANUP_N_REQUESTS = 100

    # Paths
    APP_PATH = BASE_DIR / os.getenv("APPLICATION_PACKAGE", "")
    DATA_PATH = APP_PATH / os.getenv("DATA_DIR", "data")

    # Flask Folders
    STATIC_FOLDER = "static"
    TEMPLATES_FOLDER = "templates"

    # SQLAlchemy Base
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Suppresses a deprecation warning and saves memory


class DevConfig(Config):
    """Development config."""

    DEBUG = True

    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"

    # Local Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URI", "sqlite:///db.sqlite")

    # Turns on raw SQL logging
    SQLALCHEMY_ECHO = False


class ProdConfig(Config):
    """Production config."""

    DEBUG = False

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Production Database
    SQLALCHEMY_DATABASE_URI = os.getenv("PROD_DATABASE_URI")
    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError("PROD_DATABASE_URI is not set")

    is_sqlite = SQLALCHEMY_DATABASE_URI.startswith("sqlite:")
    if not is_sqlite:
        SQLALCHEMY_ENGINE_OPTIONS = {"pool_recycle": 280, "connect_args": {"charset": "utf8mb4"}}

    # SERVER_NAME = os.getenv("SERVER_NAME")
    PREFERRED_URL_SCHEME = "https"
