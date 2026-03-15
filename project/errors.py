# errors.py
import logging

from flask import render_template, flash, redirect, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from .models import db

from flask_login import current_user
from . import gmail_service_api
from .utils import get_datetime

if gmail_service_api:
    from .notifications import send_notification

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """
    register error handlers at application level
    """

    @app.errorhandler(400)
    def bad_request_error(error):
        logger.error(f"Bad request: {request.url}")
        return render_template("index.html")

    @app.errorhandler(403)
    def forbidden_error(error):
        logger.error(
            f"Forbidden access: {request.url} by user {current_user.p.email if current_user.is_authenticated else 'anonymous'}"
        )
        return render_template("index.html")

    @app.errorhandler(404)
    def not_found_error(error):
        logger.error(
            f"Page not found: {request.url} requested by {current_user.p.email if current_user.is_authenticated else 'anonymous'}"
        )
        if current_user.is_authenticated:
            flash("La page demandée n'existe pas.", "danger")
            return redirect(url_for("projects.list_projects"))
        else:
            return render_template("index.html")

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(
            f"Server error: {error}\nRoute: {request.url}\nUser: {current_user.p.email if current_user.is_authenticated else 'anonymous'}"
        )
        db.session.rollback()
        if gmail_service_api:
            send_notification("admin", project=None, text=f"{get_datetime()} - {str(error)}")
        return render_template("500.html"), 500

    # Global SQLAlchemy error handler
    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        # Log the error for debugging
        logger.error(f"Global Database Error: {str(error)}")

        # Rollback the session to prevent leaving the database in a bad state
        db.session.rollback()

        # Flash a user-friendly message
        flash("Une erreur de communication avec la base de données est survenue.", "danger")

        # Redirect the user safely
        return redirect(request.referrer or url_for("core.index"))
