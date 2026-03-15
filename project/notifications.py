import os
from sqlalchemy.orm import joinedload
from urllib.parse import urljoin
from email.utils import formataddr

from flask import render_template
from flask_login import current_user
from jinja2 import TemplateNotFound

from .gmail_api_client import gmail_send_message
from .models import Personnel
from .utils import division_names

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
    recipients = [
        personnel.email for personnel in Personnel.query.filter(Personnel.role == "admin").first()
    ]
    if not recipients:
        return None

    message = "Bonjour,\n"
    message += f"An Internal Server Error occured at {text}. User : {current_user.p.email if current_user else None}.\n"
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

    summary = "Accédez au projet pour gérer les prochaines étapes et ajouter vos commentaires."

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

    summary = "Accédez au projet pour gérer son développement et ajouter vos commentaires."

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
