# routes/core.py
from flask import (
    Blueprint,
    render_template,
    redirect,
    request,
    url_for,
    flash,
    session,
    jsonify,
)
from flask_login import login_required, current_user

from ..models import db
from ..decorators import require_unlocked_db

from ..project import MarkReadForm

from ..utils import get_new_messages

core_bp = Blueprint("core", __name__)


@core_bp.route("/")
def index():
    return render_template("index.html")


@core_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    form = MarkReadForm()

    new_messages = get_new_messages(current_user)

    return render_template("profile.html", form=form, new_messages=new_messages)


@core_bp.route("/profile", methods=["POST"])
@login_required
@require_unlocked_db(level=2)
def profile_post():
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


@core_bp.route("/set_theme", methods=["POST"])
@login_required
def set_theme():
    data = request.get_json()
    theme = data.get("theme")

    # Validate the input
    if theme in ["light", "dark", "legacy"]:
        session["theme"] = theme

        return jsonify({"status": "success", "theme": theme}), 200

    return jsonify({"status": "error", "message": "Invalid theme"}), 400
