from flask_login import current_user

from email.utils import formataddr
from .gmail_api_client import gmail_send_message

from .models import Personnel

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


def send_notification(notification, project, recipients=None, text=""):
    # email recipients
    if notification == "admin":
        recipients = [
            personnel.email
            for personnel in Personnel.query.filter(Personnel.role == "admin").all()
            if personnel.user
        ]
    elif notification == "comment":
        recipients = [Personnel.query.get(id).email for id in recipients]
    elif notification == "ready-1":
        recipients = [
            personnel.email
            for personnel in Personnel.query.filter(Personnel.role == "gestion").all()
            if personnel.user
            and personnel.user.preferences
            and "email=ready-1" in personnel.user.preferences.split(",")
        ]
    elif notification == "ready":
        recipients = [
            personnel.email
            for personnel in Personnel.query.filter(
                Personnel.role.in_(["gestion", "direction"])
            ).all()
            if personnel.user
            and personnel.user.preferences
            and "email=ready" in personnel.user.preferences.split(",")
        ]
    elif notification.startswith("validated"):
        recipients = [member.p.email for member in project.members]
    else:
        return f"Attention : notification inconnue ({notification})."

    if not recipients:
        return "Attention : aucune notification par e-mail n'a pu être envoyée (aucun destinataire)."

    # email message
    message = "Bonjour,\n"

    if notification == "admin":
        message += f"An Internal Server Error occured at {text}.\n"

    elif notification == "comment":
        message += f'\nUn nouveau commentaire sur le projet "{project.title}" a été ajouté par {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}) :\n'
        message += "\n" + text + "\n"

    elif notification in ["ready-1", "ready"]:
        message += "\nUne demande "
        message += "d'accord" if project.status == "ready-1" else "de validation"
        message += f"{' avec inclusion au budget' if project.status == 'ready-1' and project.has_budget() else ''} vient d'être déposée :\n"
        message += f"Auteur : {current_user.p.firstname} {current_user.p.name} ({current_user.p.email})\n"
        message += f"Projet : {project.title}\n"

    elif notification in ["validated-1", "validated"]:
        message += f"\nVotre projet :\n{project.title}\na été {'approuvé' if project.status == 'validated-1' else 'validé'}{' et inclu au budget' if project.status == 'validated-1' and project.has_budget() else ''}.\n"

    elif notification == "validated-10":
        message += f"\nVotre projet :\n{project.title}\na été dévalidé pour vous permettre de le modifier.\nVous pourrez effectuer une nouvelle demande de validation.\n"

    elif notification == "print":
        message += f'\nLa fiche de sortie scolaire du projet "{project.title}" est prête pour envoi à l\'ambassade.\n'

    # ending paragraph with link to project
    if notification == "admin":
        message += "Access to log files:\n"
    elif current_user.p.role in ["gestion", "direction"]:
        if notification == "print":
            message += "\nPour générer la fiche de sortie scolaire au format PDF, connectez-vous à l'application Projets LFS :\n"
        else:
            message += f"\nPour consulter la fiche projet{', modifier votre projet' if project.status != 'validated' else ''} ou ajouter un commentaire, connectez-vous à l'application Projets LFS :\n"
    else:
        message += f"\nPour consulter cette fiche projet{',' if project.status.startswith('ready') else ' ou'} ajouter un commentaire"
        if project.status == "ready-1":
            message += " ou approuver le projet"
            if project.has_budget():
                message += " et son budget"
        elif project.status == "ready":
            message += " ou valider le projet"
        message += ", connectez-vous à l'application Projets LFS :\n"

    if notification == "admin":
        message += f"{APP_DASHBOARD}"
    else:
        message += f"{APP_WEBSITE}project/{project.id}"

    # email subject
    if notification == "admin":
        subject = "Projets LFS : Internal Server Error"
    elif notification == "comment":
        subject = "Projets LFS : nouveau commentaire"
    elif notification in ["ready-1", "ready"]:
        subject = "Projets LFS : demande "
        subject += "d'accord" if project.status == "ready-1" else "de validation"
        subject += f"{' avec inclusion au budget' if project.status == 'ready-1' and project.has_budget() else ''}"
    elif notification in ["validated-1", "validated"]:
        subject = f"Projets LFS : projet {'et budget ' if project.status == 'validated-1' and project.has_budget() else ''}{'approuvé' if project.status == 'validated-1' else 'validé'}"
    elif notification == "validated-10":
        subject = "Projets LFS : votre projet a été dévalidé"

    gmail_send_message(
        format_addr([current_user.p.email]),
        format_addr(recipients),
        message,
        subject,
    )

    # notification email sent successfully
    return None
