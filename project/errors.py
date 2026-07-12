# errors.py
import logging

from flask import render_template, flash, redirect, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from .models import db, Project

from flask_login import current_user
from . import gmail_service_api
from .utils import get_datetime

if gmail_service_api:
    from .notifications import send_notification

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Custom exception raised when a project ID does not exist."""
    def __init__(self, project_id):
        self.project_id = project_id


def get_project_or_redirect(project_id):
    project = Project.query.get(project_id)
    if not project:
        raise ProjectNotFoundError(project_id)
    return project


def register_error_handlers(app):
    """
    register error handlers at application level
    """

    @app.errorhandler(ProjectNotFoundError)
    def handle_project_not_found(error):
        logger.warning(f"Project missing: ID {error.project_id} requested by {current_user.p.email if current_user.is_authenticated else 'anonymous'}")
        
        flash(f"Le projet demandé (id = {error.project_id}) n'existe pas ou a été supprimé.", "danger")
        return redirect(request.referrer or url_for("projects.list_projects"))

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
            f"404 - Ressource not found: {request.url} requested by {current_user.p.email if current_user.is_authenticated else 'anonymous'}"
        )

        silent_assets = request.path.lower().endswith(
            (".ico", ".png", ".jpg", ".jpeg", ".gif", ".map", ".css", ".js")
        )
        if silent_assets:
            return "Asset not found", 404

        if current_user.is_authenticated:
            if request.path.lower().endswith((".pdf", ".xlsx", ".xls")):
                msg = "Le document demandé est introuvable."
            else:
                msg = "La page demandée est introuvable."
            flash(msg, "danger")
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
        # Get user info
        user_info = current_user.p.email if current_user.is_authenticated else 'anonymous'
        
        # log error with the route name where it failed and user
        logger.error(f"Database error on route '{request.endpoint}': {str(error)} for user {user_info}")

        db.session.rollback()
        flash("Une erreur de communication avec la base de données est survenue.", "danger")
        
        return redirect(request.referrer or url_for("projects.list_projects"))
