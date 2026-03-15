# routes/core.py
from flask import (
    Blueprint,
    render_template,
    send_from_directory,
    redirect,
    request,
    url_for,
    flash,
    session,
)
from flask_login import login_required, current_user
import os

from ..models import db
from ..decorators import require_unlocked_db

from ..project import MarkReadForm

from ..utils import get_new_messages

core_bp = Blueprint("core", __name__)


@core_bp.route("/")
def index():
    return render_template("index.html")


@core_bp.route("/profile", methods=["GET", "POST"])
@login_required
@require_unlocked_db(level=2)
def profile():
    form = MarkReadForm()

    if form.validate_on_submit():
        # set current_user.new_messages to 0
        current_user.new_messages = ""
        # update database
        db.session.commit()

        flash(
            "Tous les messages ont été <strong>marqués comme lus</strong> <br>avec succès !", "info"
        )

    new_messages = get_new_messages(current_user)

    return render_template("profile.html", form=form, new_messages=new_messages)


@core_bp.route("/help", methods=["GET"])
@login_required
def help():
    return render_template("help.html")


@core_bp.route("/language=<language>")
def set_language(language=None):
    session["language"] = language
    return redirect(request.referrer or url_for("core.index"))


@core_bp.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(core_bp.root_path, "../static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )
