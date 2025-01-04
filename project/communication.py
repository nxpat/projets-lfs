from flask_login import current_user

from email.utils import formataddr
from .gmail_api_client import gmail_send_message

from .models import Personnel, Comment


import os


def format_addr(emails):
    f_email = []
    for email in emails:
        personnel = Personnel.query.filter_by(email=email).first()
        f_email.append(formataddr((f"{personnel.firstname} {personnel.name}", email)))
    return ",".join(f_email)


def send_notification(notification, project, text=""):
    # app website
    APP_WEBSITE = os.getenv("APP_WEBSITE")

    if notification not in ["comment", "ready-1", "ready", "validated-1", "validated", "print"]:
        return "Erreur : notification inconnue"

    # email recipients
    if notification == "comment":
        if current_user.p.email in project.teachers:
            recipient = (
                Comment.query.filter(
                    Comment.project == project,
                    project.user.p.email not in (project.teachers.split(",")),
                )
                .order_by(Comment.id.desc())
                .first()
            )
            if not recipient:
                recipients = [
                    personnel.email
                    for personnel in Personnel.query.filter(Personnel.role == "gestion").all()
                ]
            else:
                recipients = [recipient.email]
        else:
            recipients = project.teachers.split(",")
    elif notification == "ready-1":
        recipients = [
            personnel.email
            for personnel in Personnel.query.filter(Personnel.role == "gestion").all()
            if personnel.user
            and personnel.user.preferences
            and "ready-1=email" in personnel.user.preferences
        ]
    elif notification == "ready":
        recipients = [
            personnel.email
            for personnel in Personnel.query.filter(
                Personnel.role.in_(["gestion", "direction"])
            ).all()
            if personnel.user
            and personnel.user.preferences
            and "ready=email" in personnel.user.preferences
        ]
    elif notification.startswith("validated"):
        recipients = project.teachers.split(",")

    if not recipients:
        return "Attention : aucune notification par e-mail n'a pu être envoyée"

    # email message
    message = "Bonjour,\n"

    if notification == "comment":
        message += f'\nUn nouveau commentaire sur le projet "{project.title}" a été ajouté par {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}) :\n'
        message += "\n" + text + "\n"

    elif notification == "ready-1":
        message += f"\nUne demande de validation initiale {'(inclusion au budget)' if project.has_budget() else ''} vient d'être enregistrée :\nAuteur : {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}) \nProjet : {project.title}\n"

    elif notification == "ready":
        message += f"\nUne demande de validation finale vient d'être enregistrée :\nAuteur : {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}) \nProjet : {project.title}\n"

    elif notification.startswith("validated"):
        message += f"\nVotre projet :\n{project.title}\na été validé{' et inclu au budget' if project.status == 'validated-1' and project.has_budget() else ''} (validation {'initiale' if project.status == 'validated-1' else 'finale'}).\n"

    elif notification == "print":
        message += f'\nLa fiche de sortie scolaire du projet "{project.title}" est prête pour envoi à l\'ambassade.\n'

    # ending paragraph with link to project
    if current_user.p.role in ["gestion", "direction"]:
        if notification == "print":
            message += "\nPour générer la fiche de sortie scolaire au format PDF, connectez-vous à l'application Projets LFS :\n"
        else:
            message += "\nPour consulter la fiche projet, ajouter un commentaire ou modifier votre projet, connectez-vous à l'application Projets LFS :\n"
    else:
        message += "\nPour consulter cette fiche projet, valider le projet ou ajouter un commentaire, connectez-vous à l'application Projets LFS :\n"

    message += f"{APP_WEBSITE}project/{project.id}"

    # email subject
    if notification == "comment":
        subject = "Projets LFS : nouveau commentaire"
    elif notification.startswith("ready"):
        subject = f"Projets LFS : demande de validation {'initiale' if project.status == 'ready-1' else 'finale'}"
    elif notification.startswith("validated"):
        subject = f"Projets LFS : votre projet a été {'inclu au budget' if project.status == 'validated-1' and project.has_budget() else 'validé'} {'(validation initiale)' if project.status == 'validated-1' else ''}"

    gmail_send_message(
        format_addr([current_user.p.email]),
        format_addr(recipients),
        message,
        subject,
    )

    return None
