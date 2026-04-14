import os
from sqlalchemy.orm import joinedload
from urllib.parse import urljoin
from email.utils import formataddr

from flask import render_template
from flask_login import current_user
from jinja2 import TemplateNotFound

from .gmail_api_client import gmail_send_message
from .models import db, Personnel, ProjectComment, QueuedAction
from .utils import get_datetime, get_project_dates, division_names

from . import gmail_service_api

# environment/config
APP_BASE_URL = os.getenv("APP_BASE_URL")
APP_DASHBOARD = os.getenv("APP_DASHBOARD")


def format_addr(emails):
    """
    Accepts list of email strings. Returns comma-joined "Name <email>" addresses.
    """
    if not emails:
        return ""

    personnel_list = Personnel.query.filter(Personnel.email.in_(emails)).all()
    p_map = {p.email: p for p in personnel_list}

    f_email = []
    for email in emails:
        p = p_map.get(email)
        name = f"{p.firstname} {p.name}".replace("é", "e") if p else email
        f_email.append(formataddr((name, email)))
    return ",".join(f_email)


# --- Notification builders ---
# Each returns: {
#   "recipients": list[str],
#   "subject": str,
#   "message": str (plain text),
#   "template": str (template name),
#   "template_vars": dict (optional vars for template)
# }


def create_admin_notification(text):
    admin = Personnel.query.filter_by(role="admin").first()
    recipients = [admin.email] if admin else []

    if not recipients:
        return None

    message = "Bonjour,\n"
    user_email = current_user.p.email if current_user.is_authenticated else "Anonymous"
    message += f"An Internal Server Error occured at {text}. User : {user_email}.\n"
    message += f"Access to log files:\n{APP_DASHBOARD}"

    subject = "Projets LFS : Internal Server Error"

    return {
        "recipients": recipients,
        "subject": subject,
        "message": message,
        "template": None,
        "template_vars": None,
    }


def create_comment_notification(project, recipients, text):
    personnel_list = Personnel.query.filter(Personnel.id.in_(recipients)).all()
    resolved = [p.email for p in personnel_list]

    if not resolved:
        return None

    author = getattr(current_user, "p", None)
    author_name = f"{author.firstname} {author.name}" if author else ""
    author_email = author.email if author else ""

    msg = "Bonjour,\n\n"
    msg += f'Un nouveau commentaire sur le projet "{project.title}" a été ajouté par {author_name} ({author_email}) :\n\n'
    msg += text + "\n\n"

    message = "Un nouveau commentaire a été ajouté."

    summary = "Accédez au projet pour gérer les prochaines étapes et ajouter un commentaire."

    project_url = urljoin(APP_BASE_URL or "", f"project/{project.id}")

    msg = msg + summary[:-1] + " :\n" + project_url

    subject = "Projets LFS : nouveau commentaire"

    return {
        "recipients": resolved,
        "subject": subject,
        "message": msg,
        "template": "project_notification.html",
        "template_vars": {
            "title": "Nouveau commentaire",
            "subtitle": None,
            "message": message,
            "author_name": author_name,
            "author_email": author_email,
            "project_title": project.title,
            "project_date": get_project_dates(project.start_date, project.end_date, br=False),
            "divisions": division_names(project.divisions, "FSs"),
            "comment_text": text,
            "project_url": project_url,
            "print_url": None,
            "summary": summary,
        },
    }


def create_rejected_comment_notification(project, recipients, text):
    personnel_list = Personnel.query.filter(Personnel.id.in_(recipients)).all()
    resolved = [p.email for p in personnel_list]

    if not resolved:
        return None

    author = getattr(current_user, "p", None)
    author_name = f"{author.firstname} {author.name}" if author else ""

    msg = "Bonjour,\n\n"
    msg += f'Votre projet "{project.title}" n\'a pas été retenu par {author_name} :\n\n'
    msg += text + "\n\n"

    message = f"Votre projet n'a pas été retenu par {author_name}."

    summary = "Accédez au projet pour ajouter un commentaire."

    project_url = urljoin(APP_BASE_URL or "", f"project/{project.id}")

    msg = msg + summary[:-1] + " :\n" + project_url

    subject = "Projets LFS : projet non retenu"

    return {
        "recipients": resolved,
        "subject": subject,
        "message": msg,
        "template": "project_notification.html",
        "template_vars": {
            "title": "Projet non retenu",
            "subtitle": None,
            "message": message,
            "author_name": None,
            "author_email": None,
            "project_title": project.title,
            "project_date": get_project_dates(project.start_date, project.end_date, br=False),
            "divisions": division_names(project.divisions, "FSs"),
            "comment_text": text,
            "project_url": project_url,
            "print_url": None,
            "summary": summary,
        },
    }


def create_validation_request_notification(project):
    # query personnels with 'gestion' and 'direction' roles
    query = (
        Personnel.query.options(joinedload(Personnel.user))
        .filter(Personnel.role.in_(["gestion", "direction"]))
        .all()
    )

    # filter preferences
    target_pref = f"email={project.status}"

    recipients = [
        p.email
        for p in query
        if p.user and p.user.preferences and target_pref in p.user.preferences.split(",")
    ]

    if not recipients:
        return None

    author = getattr(current_user, "p", None)
    author_name = f"{author.firstname} {author.name}" if author else ""
    author_email = author.email if author else ""

    msg = "Bonjour,\n\n"

    topic = (
        "demande "
        + ("d'accord" if project.status == "ready-1" else "de validation")
        + (
            " et inclusion au budget"
            if project.status == "ready-1" and project.has_budget()
            else ""
        )
    )
    message = "Une " + topic + " a été déposée."
    msg += message + "\n"

    msg += f"Auteur : {author_name} ({author_email})\n"
    msg += f"Projet : {project.title}\n"
    msg += f"Classes concernées : {division_names(project.divisions, 'FSs')}\n\n"

    summary = (
        "Consultez le projet pour finaliser l'accord"
        + (" budgétaire" if project.status == "ready-1" and project.has_budget() else "")
        + " et lancer les prochaines étapes."
    )

    project_url = urljoin(APP_BASE_URL or "", f"project/{project.id}")

    msg += summary[:-1] + project_url

    subject = "Projets LFS : " + topic

    title = "Nouvelle " + topic

    return {
        "recipients": recipients,
        "subject": subject,
        "message": msg,
        "template": "project_notification.html",
        "template_vars": {
            "title": title,
            "subtitle": None,
            "message": message,
            "author_name": author_name,
            "author_email": author_email,
            "project_title": project.title,
            "project_date": get_project_dates(project.start_date, project.end_date, br=False),
            "divisions": division_names(project.divisions, "FSs"),
            "comment_text": None,
            "project_url": project_url,
            "print_url": None,
            "summary": summary,
        },
    }


def create_validation_result_notification(project):
    recipients = [member.p.email for member in project.members]
    recipients = [r for r in recipients if r]
    if not recipients:
        return None

    author = getattr(current_user, "p", None)
    author_name = f"{author.firstname} {author.name}" if author else ""

    msg = "Bonjour,\n"

    if project.status in ["validated-1", "validated"]:
        message = (
            f"Votre projet a été {'approuvé' if project.status == 'validated-1' else 'validé'}"
        )
        message += f"{' et inclu au budget' if project.status == 'validated-1' and project.has_budget() else ''} par {author_name}."
    elif project.status == "validated-10":
        message = f"Votre projet a été dévalidé par {author_name}. Vous pouvez le modifier et effectuer une nouvelle demande de validation."
    elif project.status == "rejected":
        message = f"Votre projet n'a pas été retenu par {author_name}."

    summary = "Accédez au projet pour gérer son développement et ajouter un commentaire."

    project_url = urljoin(APP_BASE_URL or "", f"project/{project.id}")

    msg += f"\n{message}\n\n{summary}\n\nProjet : {project.title}\n{project_url}"

    if project.status in ["validated-1", "validated"]:
        title = f"projet {'et budget ' if project.status == 'validated-1' and project.has_budget() else ''}"
        title += f"{'approuvé' if project.status == 'validated-1' else 'validé'}"
    elif project.status == "validated-10":
        title = "projet dévalidé"
    elif project.status == "rejected":
        title = "projet non retenu"
    else:
        title = "mise à jour projet"

    return {
        "recipients": recipients,
        "subject": "Projets LFS : " + title,
        "message": msg,
        "template": "project_notification.html",
        "template_vars": {
            "title": title.capitalize(),
            "subtitle": None,
            "message": message,
            "author_name": None,
            "author_email": None,
            "project_title": project.title,
            "project_date": get_project_dates(project.start_date, project.end_date, br=False),
            "divisions": division_names(project.divisions, "FSs"),
            "comment_text": None,
            "project_url": project_url,
            "print_url": None,
            "summary": summary,
        },
    }


def create_validation_notification(project):
    personnel_query = (
        Personnel.query.options(joinedload(Personnel.user))
        .filter(Personnel.role == "gestion")
        .all()
    )

    target_pref = "email=validated"

    recipients = [
        p.email
        for p in personnel_query
        if p.user and p.user.preferences and target_pref in p.user.preferences.split(",")
    ]

    if not recipients:
        return None

    msg = f"Bonjour,\n\nLe projet :\n{project.title}\nClasses concernées : {division_names(project.divisions, 'FSs')}\na été validé.\n"

    message = "Un nouveau projet a été validé."

    summary = f"Accédez au projet pour consulter les dernières mises à jour{',' if project.location == 'outer' else ' et'} échanger avec l'équipe{' et imprimer la fiche de sortie' if project.location == 'outer' else ''}."

    project_url = urljoin(APP_BASE_URL or "", f"project/{project.id}")
    print_url = urljoin(APP_BASE_URL or "", f"project/print/{project.id}")

    msg += "\n" + summary[:-1] + " :\n" + project_url

    if project.location == "outer":
        msg += "\nLien direct pour imprimer la fiche de sortie :\n"
        msg += print_url

    subject = "Projets LFS : nouveau projet validé"

    return {
        "recipients": recipients,
        "subject": subject,
        "message": msg,
        "template": "project_notification.html",
        "template_vars": {
            "title": "Nouveau projet validé",
            "subtitle": None,
            "message": message,
            "author_name": None,
            "author_email": None,
            "project_title": project.title,
            "project_date": get_project_dates(project.start_date, project.end_date, br=False),
            "divisions": division_names(project.divisions, "FSs"),
            "comment_text": None,
            "project_url": project_url,
            "print_url": print_url,
            "summary": summary,
        },
    }


# --- Renderer helper ---


def _render_html_from_notification(notification):
    """
    Renders HTML using template specified in notification["template"] and template_vars.
    If template missing or error occurs, returns None.
    """
    template_name = notification.get("template", None)
    vars = notification.get("template_vars", {})

    if not template_name or not vars:
        return None  # skip HTML rendering for plain-text admin alerts

    try:
        return render_template(template_name, **vars)
    except TemplateNotFound:
        return None


# --- send_notification ---


def send_notification(notification_type, project, recipients=None, text=""):
    """
    notification_type: as before
    project: Project instance (may be None for admin)
    recipients: used by comment notification (list of Personnel ids)
    text: used for admin (error text) and comment content
    """
    notifications = []

    if notification_type == "admin":
        notif = create_admin_notification(text)
        if notif:
            notifications.append(notif)

    elif notification_type == "comment":
        notif = create_comment_notification(project, recipients or [], text)
        if notif:
            notifications.append(notif)

    elif notification_type == "rejected_comment":
        notif = create_rejected_comment_notification(project, recipients or [], text)
        if notif:
            notifications.append(notif)

    elif notification_type in ["ready-1", "ready"]:
        notif = create_validation_request_notification(project)
        if notif:
            notifications.append(notif)

    elif notification_type in ["validated-1", "validated", "validated-10", "rejected"]:
        notif = create_validation_result_notification(project)
        if notif:
            notifications.append(notif)
        if notification_type == "validated":
            notif2 = create_validation_notification(project)
            if notif2:
                notifications.append(notif2)
    else:
        return f"Attention : notification inconnue ({notification_type})."

    if not notifications:
        return "Attention : aucune notification n'a pu être envoyée (aucun destinataire)."

    for notification in notifications:
        # compute reply-to and recipients
        reply_to = (
            format_addr([current_user.p.email])
            if current_user and getattr(current_user, "p", None)
            else ""
        )
        recipients_list = notification.get("recipients", [])

        # render HTML
        html_body = _render_html_from_notification(notification)

        # call gmail_send_message
        gmail_send_message(
            reply_to,
            format_addr(recipients_list),
            notification.get("message", ""),
            notification.get("subject", ""),
            html=html_body,
        )

    return None


def queue_notification(user_id, action_type, parameters, options=None):
    """
    Queues a notification action in the database.
    Returns a warning string if the GMail API is disconnected, else None.
    """
    if not gmail_service_api:
        return "API GMail non connectée : aucune notification envoyée par e-mail."

    async_action = QueuedAction(
        uid=user_id,
        timestamp=get_datetime(),
        status="pending",
        action_type=action_type,
        parameters=parameters,
        options=options,
    )
    db.session.add(async_action)
    return None


def queue_status_notification(project, user_id):
    """Shortcut for queuing project status changes"""
    return queue_notification(
        user_id=user_id,
        action_type="send_notification",
        parameters=f"{project.status},{project.id}",
    )


def queue_comment_notification(project_id, comment_id, user_id, recipients_str, is_rejection=False):
    """Shortcut for queuing new comment notifications"""
    if is_rejection:
        parameters = f"rejected_comment,{project_id},{comment_id}"
    else:
        parameters = f"comment,{project_id},{comment_id}"

    return queue_notification(
        user_id=user_id,
        action_type="send_notification",
        parameters=parameters,
        options=recipients_str,
    )


def process_add_comment(project, user, message_data, recipients_data, is_rejection=False):
    """
    Core logic for adding a comment to a project.
    Returns a tuple: (success_boolean, list_of_flash_messages)
    """
    # 1. Authorization check
    is_authorized = (
        user.id == project.uid
        or any(member.pid == user.pid for member in project.members)
        or user.p.role in ["gestion", "direction"]
    )

    if not is_authorized:
        return False, [("Vous ne pouvez pas commenter ce projet.", "danger")]

    flashes = []

    # 2. Add the comment
    date = get_datetime()
    comment = ProjectComment(
        message=message_data,
        posted_at=date,
        project_id=project.id,
        uid=user.id,
    )
    db.session.add(comment)
    db.session.flush()  # Flush to get comment.id for the notification

    # 3. Handle recipients and e-mail notifications
    warning_flash = None
    if recipients_data:
        # Safely create both a list (for looping) and a string (for the DB)
        if isinstance(recipients_data, list):
            recipients_list = recipients_data
            recipients_str = ",".join([str(r) for r in recipients_data])
        else:
            recipients_list = recipients_data.split(",")
            recipients_str = recipients_data

        # Update user table: set new_message notification
        for pid in recipients_list:
            personnel = Personnel.query.filter(Personnel.id == pid).first()
            if personnel and personnel.user:
                u = personnel.user
                if u.new_messages:
                    u.new_messages += f",{str(project.id)}"
                else:
                    u.new_messages = str(project.id)
                db.session.flush()

        warning_flash = queue_comment_notification(
            project.id, comment.id, user.id, recipients_str, is_rejection
        )
    else:
        warning_flash = "Attention : aucune notification n'a pu être envoyée (aucun destinataire)."

    # 4. Prepare flash messages
    flashes.append(("Nouveau message enregistré avec succès !", "info"))
    if warning_flash:
        flashes.append((warning_flash, "warning"))

    return True, flashes
