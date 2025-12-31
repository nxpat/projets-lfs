from flask_login import current_user

from email.utils import formataddr
from .gmail_api_client import gmail_send_message

from .models import Personnel

from .utils import division_names

import os

# app website
APP_WEBSITE = os.getenv("APP_WEBSITE")
APP_DASHBOARD = os.getenv("APP_DASHBOARD")


def format_addr(emails):
    f_email = []
    for email in emails:
        personnel = Personnel.query.filter_by(email=email).first()
        f_email.append(
            formataddr(
                (
                    f"{personnel.firstname.replace('é', 'e')} {personnel.name.replace('é', 'e')}",
                    email,
                )
            )
        )
    return ",".join(f_email)


def create_admin_notification(text):
    # get recipients
    recipients = [
        personnel.email for personnel in Personnel.query.filter(Personnel.role == "admin").all()
    ]

    if recipients is None:
        return None

    # create message
    message = "Bonjour,\n"
    message += f"An Internal Server Error occured at {text}. User : {current_user.p.email if current_user else None}.\n"
    message += f"Access to log files:\n{APP_DASHBOARD}"

    # create subject
    subject = "Projets LFS : Internal Server Error"

    return {"recipients": recipients, "message": message, "subject": subject}


def create_comment_notification(project, recipients, text):
    # resolve recipients
    recipients = [Personnel.query.filter(Personnel.id == id).first().email for id in recipients]

    # create message
    message = "Bonjour,\n"
    message += f'\nUn nouveau commentaire sur le projet "{project.title}" a été ajouté par {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}) :\n'
    message += "\n" + text + "\n"
    message += f"\nPour consulter la fiche projet{', modifier votre projet' if current_user.p.role in ['gestion', 'direction'] else ''} ou ajouter un commentaire, "
    message += f"connectez-vous à l'application Projets LFS :\n{APP_WEBSITE}project/{project.id}"

    # create subject
    subject = "Projets LFS : nouveau commentaire"

    return {"recipients": recipients, "message": message, "subject": subject}


def create_validation_request_notification(project):
    # get recipients
    recipients = [
        personnel.email
        for personnel in Personnel.query.filter(Personnel.role.in_(["gestion", "direction"])).all()
        if personnel.user
        and personnel.user.preferences
        and "email=" + project.status in personnel.user.preferences.split(",")
    ]

    if recipients is None:
        return None

    # create message
    message = "Bonjour,\n"
    message += "\nUne demande "
    message += "d'accord" if project.status == "ready-1" else "de validation"
    message += f"{' et inclusion au budget' if project.status == 'ready-1' and project.has_budget() else ''} vient d'être déposée :\n"
    message += (
        f"Auteur : {current_user.p.firstname} {current_user.p.name} ({current_user.p.email})\n"
    )
    message += f"Projet : {project.title}\n"
    message += f"Classes concernées : {division_names(project.divisions, 'FSs')}\n"
    message += "\nPour consulter la fiche projet, ajouter un commentaire ou gérer le projet, "
    message += f"connectez-vous à l'application Projets LFS :\n{APP_WEBSITE}project/{project.id}"

    # create subject
    subject = "Projets LFS : demande "
    subject += "d'accord" if project.status == "ready-1" else "de validation"
    subject += f"{' et inclusion au budget' if project.status == 'ready-1' and project.has_budget() else ''}"

    return {"recipients": recipients, "message": message, "subject": subject}


def create_validation_result_notification(project):
    # get recipients
    recipients = [member.p.email for member in project.members]

    if recipients is None:
        return None

    # create message
    message = "Bonjour,\n"
    if project.status in ["validated-1", "validated"]:
        message += f"\nVotre projet :\n{project.title}\na été {'approuvé' if project.status == 'validated-1' else 'validé'}"
        message += f"{' et inclu au budget' if project.status == 'validated-1' and project.has_budget() else ''}.\n"
    elif project.status == "validated-10":
        message += f"\nVotre projet :\n{project.title}\na été dévalidé. "
        message += "Vous pouvez le modifier et effectuer une nouvelle demande de validation.\n"
    elif project.status == "rejected":
        message += f"\nVotre projet :\n{project.title}\nn'a pas été retenu.\n"

    message += "\nPour consulter la fiche projet"
    message += (
        f"{', modifier votre projet' if project.status not in ['validated', 'rejected'] else ''}"
    )
    message += " ou ajouter un commentaire, "
    message += f"connectez-vous à l'application Projets LFS :\n{APP_WEBSITE}project/{project.id}"

    # create subject
    if project.status in ["validated-1", "validated"]:
        subject = f"Projets LFS : projet {'et budget ' if project.status == 'validated-1' and project.has_budget() else ''}"
        subject += f"{'approuvé' if project.status == 'validated-1' else 'validé'}"
    elif project.status == "validated-10":
        subject = "Projets LFS : projet dévalidé"
    elif project.status == "rejected":
        subject = "Projets LFS : projet non retenu"

    return {"recipients": recipients, "message": message, "subject": subject}


def create_validation_notification(project):
    # get recipients
    recipients = [
        personnel.email
        for personnel in Personnel.query.filter(Personnel.role == "gestion").all()
        if personnel.user
        and personnel.user.preferences
        and "email=validated" in personnel.user.preferences.split(",")
    ]
    if recipients is None:
        return None

    # create message
    message = "Bonjour,\n"
    message += f"\nLe projet :\n{project.title}\nClasses concernées : {division_names(project.divisions, 'FSs')}\na été validé.\n"
    message += f"\nPour consulter la fiche projet{',' if project.location == 'outer' else ' ou'} ajouter un commentaire"
    message += f"{' ou générer la fiche de sortie scolaire au format PDF' if project.location == 'outer' else ''}, "
    message += f"connectez-vous à l'application Projets LFS :\n{APP_WEBSITE}project/{project.id}"

    if project.location == "outer":
        message += "\nLien direct pour imprimer la fiche de sortie :\n"
        message += f"{APP_WEBSITE}project/print/{project.id}\n"

    # create subject
    subject = "Projets LFS : nouveau projet validé"

    return {"recipients": recipients, "message": message, "subject": subject}


def send_notification(notification_type, project, recipients=None, text=""):
    notifications = []

    if notification_type == "admin":
        notification = create_admin_notification(text)
        if notification is not None:
            notifications.append(notification)

    elif notification_type == "comment":
        notification = create_comment_notification(project, recipients, text)
        if notification is not None:
            notifications.append(notification)

    elif notification_type in ["ready-1", "ready"]:
        notification = create_validation_request_notification(project)
        if notification is not None:
            notifications.append(notification)

    elif notification_type in ["validated-1", "validated", "validated-10", "rejected"]:
        notification = create_validation_result_notification(project)
        if notification is not None:
            notifications.append(notification)

        if notification_type == "validated":
            notification = create_validation_notification(project)
            if notification is not None:
                notifications.append(notification)
    else:
        return f"Attention : notification inconnue ({notification_type})."

    if notifications:
        for notification in notifications:
            gmail_send_message(
                format_addr([current_user.p.email]),
                format_addr(notification["recipients"]),
                notification["message"],
                notification["subject"],
            )
        # Notifications were sent successfully
        return None

    return "Attention : aucune notification n'a pu être envoyée (aucun destinataire)."
