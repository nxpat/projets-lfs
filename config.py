from os import environ, path
from dotenv import load_dotenv

load_dotenv()

# Specify a `.env` file containing key/value config values
basedir = path.abspath(path.dirname(__file__))
load_dotenv(path.join(basedir, ".env"))


class Config(object):
    """Base config."""

    SECRET_KEY = environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = environ.get("SQLALCHEMY_DATABASE_URI")
    STATIC_FOLDER = "static"
    TEMPLATES_FOLDER = "templates"

    REMEMBER_COOKIE_DURATION = 4233600  # 7 days
    SESSION_PROTECTION = "strong"
    SESSION_CLEANUP_N_REQUESTS = 100

    # configure Redis for storing the session data on the server-side
    SESSION_TYPE = "redis"
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True


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
