# decorators.py
from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user
from sqlalchemy.exc import SQLAlchemyError

from .models import db, Dashboard

from .utils import get_name

import logging

logger = logging.getLogger(__name__)


def require_unlocked_db(level=1):
    """
    Decorator to prevent access if the database is locked.
    level=1 triggers for any lock, level=2 triggers only for maintenance lock.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            dash = Dashboard.query.first()
            if dash and dash.lock >= level:
                flash(
                    "La base est momentanément fermée. <br>Les modifications sont impossibles.",
                    "danger",
                )
                return redirect(request.referrer or url_for("projects.list_projects"))
            return f(*args, **kwargs)

        return decorated_function

    return decorator
