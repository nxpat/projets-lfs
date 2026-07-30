from flask import request
from flask_babel import Babel

babel = Babel()

LANGUAGES = {"fr": "French", "en": "English", "kr": "Korean"}


def configure(app):
    babel.init_app(app)
    app.config["LANGUAGES"] = LANGUAGES


def get_locale():
    return request.cookies.get("lang", "fr")
