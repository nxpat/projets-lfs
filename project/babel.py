from flask_babel import Babel
from flask import request

babel = Babel()

LANGUAGES = {"en": "English", "fr": "French", "kr": "Korean"}


def configure(app):
    babel.init_app(app)
    app.config["LANGUAGES"] = LANGUAGES


def get_locale():
    return request.cookies.get("lang", "fr")
