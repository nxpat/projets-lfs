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

from ..models import db, Personnel, User
from ..decorators import require_unlocked_db

from ..project import MarkReadForm, NotificationPreferencesForm

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

    return render_template(
        "profile.html",
        form=form,
        new_messages=new_messages,
        formt=NotificationPreferencesForm(),  # To pull labels & descriptions
    )


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

    return render_template(
        "profile.html",
        form=form,
        new_messages=new_messages,
        formt=NotificationPreferencesForm(),  # To pull labels & descriptions
    )


@core_bp.route("/profile/notifications", methods=["GET", "POST"])
@login_required
def notification_preferences():
    # Only allow 'gestion' and 'direction' to access this page
    if current_user.p.role not in ["gestion", "direction"]:
        flash("Vous n'avez pas accès à ces paramètres de notification.", "warning")
        return redirect(url_for("core.profile"))

    form = NotificationPreferencesForm()

    if form.validate_on_submit():
        # Encode bitwise values: the sum() function handles the bitwise math perfectly!
        # If user selects Primary (1) and Secondary (2), sum([1, 2]) = 3.
        proposed_prefs = {
            "notify_new_msg_team": sum(form.notify_new_msg_team.data),
            "notify_approval_req": sum(form.notify_approval_req.data),
            "notify_validation_req": sum(form.notify_validation_req.data),
            "notify_approved": sum(form.notify_approved.data),
            "notify_validated": sum(form.notify_validated.data),
        }

        # --- THE LAST-RESPONDER SAFETY CHECK ---
        mandatory_keys = {
            "notify_new_msg_team": form.notify_new_msg_team.label.text,
            "notify_approval_req": form.notify_approval_req.label.text,
            "notify_validation_req": form.notify_validation_req.label.text,
        }

        # 1. Fetch all other gestion/direction personnel, excluding current_user
        other_admins = (
            User.query.join(Personnel)
            .filter(Personnel.role.in_(["gestion", "direction"]), User.id != current_user.id)
            .all()
        )

        for key, label in mandatory_keys.items():
            # Calculate the combined bitmask of all other administrators for this key
            others_mask = 0
            for adm in other_admins:
                others_mask |= (adm.preferences or {}).get(key, 0)

            old_global_mask = others_mask | (current_user.preferences or {}).get(key, 0)
            new_global_mask = others_mask | proposed_prefs[key]

            # Rule A: The channel cannot be left entirely dead
            if new_global_mask == 0:
                field = getattr(form, key)  # get the Field instance
                field.errors.append(
                    "Au moins un membre de la gestion ou de la direction doit recevoir cette notification."
                )
                flash(
                    f"<strong>Modifications refusées</strong><br> Les notifications « {label} » (Primaireet Secondaire)<br> doivent être attribuée à au moins un gestionnaire.",
                    "danger",
                )
                return render_template("preferences.html", form=form)

            # Rule B: Bit Conservation (Catches orphaned school sections)
            # If (Old & ~New) > 0, it means a '1' bit was lost in the transition.
            orphaned_bits = old_global_mask & ~new_global_mask

            if orphaned_bits > 0:
                # Decode the exact name of the orphaned school to give a crystal-clear UX error
                lost_names = [
                    name
                    for bit, name in [(1, "Primaire"), (2, "Secondaire")]
                    if orphaned_bits & bit
                ]
                sections_str = " et ".join(lost_names)

                field = getattr(form, key)  # get the Field instance
                field.errors.append(
                    "Au moins un membre de la gestion ou de la direction doit recevoir cette notification."
                )
                flash(
                    f"<strong>Modifications refusées</strong><br> Vous êtes le dernier gestionnaire assigné aux notifications <strong>« {label} » ({sections_str})</strong>.<br> Vous devez déléguer cette notification à un collègue avant de vous désabonner.",
                    "danger",
                )
                return render_template("preferences.html", form=form)

        # If it passes the gauntlet, commit to DB
        current_user.preferences = proposed_prefs
        db.session.commit()

        flash("Vos préférences de notification\n ont été mises à jour avec succès.", "info")
        return redirect(url_for("core.profile"))

    elif request.method == "GET":
        # Load current preferences or default to an empty dictionary
        prefs = current_user.preferences or {}

        # Helper function to decode bitwise integer back to a list of ints for WTForms
        # e.g., 3 -> [1, 2] | 1 -> [1] | 2 -> [2] | 0 -> []
        def decode_bitwise(val):
            return [i for i in (1, 2) if val & i]

        # Pre-check the boxes based on the stored integer
        form.notify_new_msg_team.data = decode_bitwise(prefs.get("notify_new_msg_team", 0))
        form.notify_approval_req.data = decode_bitwise(prefs.get("notify_approval_req", 0))
        form.notify_validation_req.data = decode_bitwise(prefs.get("notify_validation_req", 0))
        form.notify_approved.data = decode_bitwise(prefs.get("notify_approved", 0))
        form.notify_validated.data = decode_bitwise(prefs.get("notify_validated", 0))

    return render_template("preferences.html", form=form)


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
