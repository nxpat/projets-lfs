# errors.py
import logging

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, selectinload

from . import gmail_service_api
from .models import Project, ProjectComment, ProjectHistory, ProjectMember, User, db
from .utils import get_datetime

if gmail_service_api:
    from .notifications import send_notification

logger = logging.getLogger(__name__)


class ProjectNotFoundError(Exception):
    """Custom exception raised when a project ID does not exist."""

    def __init__(self, project_id):
        self.project_id = project_id


def get_project_or_redirect(project_id: int, eagerload: str | None = None) -> Project:
    stmt = select(Project).where(Project.id == project_id)

    if eagerload == "form":
        stmt = stmt.options(
            selectinload(Project.members).joinedload(ProjectMember.p),
            selectinload(Project.history),
        )
    elif eagerload == "members":
        stmt = stmt.options(
            selectinload(Project.members).joinedload(ProjectMember.p),
        )
    elif eagerload == "comments":
        stmt = stmt.options(
            joinedload(Project.user).joinedload(User.p),
            joinedload(Project.modifier).joinedload(User.p),
            joinedload(Project.validator).joinedload(User.p),
            selectinload(Project.members).joinedload(ProjectMember.p),
            selectinload(Project.comments).joinedload(ProjectComment.user).joinedload(User.p),
        )
    elif eagerload == "history":
        stmt = stmt.options(
            selectinload(Project.history).joinedload(ProjectHistory.updater).joinedload(User.p)
        )

    project = db.session.scalar(stmt)

    if not project:
        raise ProjectNotFoundError(project_id)

    return project


def is_api_request() -> bool:
    """Check if the incoming request is meant for an API endpoint."""
    return (
        request.path.startswith("/api/")
        or request.is_json
        or request.accept_mimetypes.best_match(["application/json", "text/html"])
        == "application/json"
    )


def register_error_handlers(app):
    """Register error handlers at application level."""

    @app.errorhandler(ProjectNotFoundError)
    def handle_project_not_found(error):
        logger.warning(
            f"Project missing: ID {error.project_id} requested by {current_user.p.email if current_user.is_authenticated else 'anonymous'}"
        )

        msg = f"Le projet demandé (id = {error.project_id}) n'existe pas ou a été supprimé."

        if is_api_request():
            return jsonify({"error": msg}), 404

        flash(msg, "danger")
        return redirect(request.referrer or url_for("projects.list_projects"))

    @app.errorhandler(400)
    def bad_request_error(error):
        logger.error(f"Bad request: {request.url}")

        if is_api_request():
            return jsonify({"error": "Requête invalide."}), 400

        return render_template("index.html")

    @app.errorhandler(403)
    def forbidden_error(error):
        logger.error(
            f"Forbidden access: {request.url} by user {current_user.p.email if current_user.is_authenticated else 'anonymous'}"
        )

        if is_api_request():
            return jsonify({"error": "Accès non autorisé."}), 403

        return render_template("index.html")

    @app.errorhandler(404)
    def not_found_error(error):
        logger.error(
            f"404 - Resource not found: {request.url} requested by {current_user.p.email if current_user.is_authenticated else 'anonymous'}"
        )

        silent_assets = request.path.lower().endswith(
            (".ico", ".png", ".jpg", ".jpeg", ".gif", ".map", ".css", ".js")
        )
        if silent_assets:
            return "Asset not found", 404

        if is_api_request():
            return jsonify({"error": "La ressource ou l'endpoint demandé est introuvable."}), 404

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
            send_notification("admin", project=None, text=f"{get_datetime()} - {error!s}")

        if is_api_request():
            return jsonify({"error": "Une erreur interne du serveur est survenue."}), 500

        return render_template("500.html"), 500

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        user_info = current_user.p.email if current_user.is_authenticated else "anonymous"

        logger.error(
            f"Database error on route '{request.endpoint}': {error!s} for user {user_info}"
        )

        db.session.rollback()
        msg = "Une erreur de communication avec la base de données est survenue."

        if is_api_request():
            return jsonify({"error": msg}), 500

        flash(msg, "danger")
        return redirect(request.referrer or url_for("projects.list_projects"))
