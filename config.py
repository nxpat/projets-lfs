import os
from dotenv import load_dotenv

load_dotenv()


class Config(object):
    """Base config."""

    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    STATIC_FOLDER = "static"
    TEMPLATES_FOLDER = "templates"

    REMEMBER_COOKIE_DURATION = 4233600  # 7 days
    SESSION_PROTECTION = "strong"
    SESSION_CLEANUP_N_REQUESTS = 100


class DevConfig(Config):
    """Development config."""

    FLASK_ENV = "development"
    FLASK_DEBUG = True

    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_SAMESITE = "Lax"


class ProdConfig(Config):
    """Production config."""

    FLASK_ENV = "production"
    FLASK_DEBUG = False

    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Lax"
