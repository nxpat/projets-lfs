from flask import render_template, redirect, url_for, flash, request
from flask_login import current_user
from . import db, logger, gmail_service
from .utils import get_datetime

if gmail_service:
    from .communication import send_notification

    
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
        logger.error(f"Forbidden access: {request.url} by user {current_user.p.email if current_user.is_authenticated else 'anonymous'}")
        return render_template("index.html")


    @app.errorhandler(404)
    def not_found_error(error):
        logger.error(f"Page not found: {request.url} requested by {current_user.p.email if current_user.is_authenticated else 'anonymous'}")
        if current_user.is_authenticated:
            flash("La page demandée n'existe pas.", "danger")
            return redirect(url_for("main.projects"))
        else:
            return render_template("index.html")


    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Server error: {error}\nRoute: {request.url}\nUser: {current_user.p.email if current_user.is_authenticated else 'anonymous'}")
        db.session.rollback()
        if gmail_service:
            send_notification("admin", project=None, text=f"{get_datetime()} - {str(error)}")
        return render_template('500.html'), 500