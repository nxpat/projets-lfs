from flask_login import current_user

from email.utils import formataddr
from .gmail_api_client import gmail_send_message

from .models import Personnel, Comment
from . import website


def format_addr(emails):
    f_email = []
    for email in emails:
        personnel = Personnel.query.filter_by(email=email).first()
        f_email.append(formataddr((f"{personnel.firstname} {personnel.name}", email)))
    return ",".join(f_email)


def send_notification(notification, project, text=""):
    if notification not in ["comment", "ready-1", "ready", "validation"]:
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
            if recipient is None:
                recipients = [
                    personnel.email
                    for personnel in Personnel.query.filter(
                        Personnel.role == "gestion"
                    ).all()
                ]
            else:
                recipients = [recipient.email]
        else:
            recipients = project.teachers.split(",")
    elif notification == "ready-1":
        recipients = [
            personnel.email
            for personnel in Personnel.query.filter(Personnel.role == "gestion").all()
            if personnel.user.preferences == "email"
        ]
    elif notification == "ready":
        recipients = [
            personnel.email
            for personnel in Personnel.query.filter(
                Personnel.role.in_(["gestion", "direction"])
            ).all()
            if personnel.user.preferences in ["email", "email-v"]
        ]
    elif notification == "validation":
        recipients = project.teachers.split(",")

    if recipients == []:
        return "Attention : aucune notification par e-mail n'a pu être envoyée"

    message = "Bonjour,"

    # email message
    if notification == "comment":
        message += f'\n\nUn nouveau commentaire sur le projet "{project.title}" a été ajouté par {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}):\n\n'
        message += text
    elif notification == "ready":
        message += f"\n\nUne demande de validation {'initiale (inclusion au budget)' if project.status == 'ready-1' else 'finale'} vient d'être déposée :\nAutheur : {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}) \nProjet : {project.title}"
    elif notification == "validation":
        message += f"\n\nVotre projet :\n{project.title}\n\na été validé {'et inclu au budget' if project.status == 'validated-1' else ''} (validation {'initiale' if project.status == 'validated-1' else 'finale'})."
    elif notification == "print":
        message += f'La fiche de sortie scolaire du projet "{project.title}" est prête pour envoi à l\'ambassade.'

    if current_user.p.role in ["gestion", "direction"]:
        if notification == "print":
            message += "\n\nPour générer la fiche de sortie scolaire au format PDF, connectez-vous à l'application Projets LFS : "
        else:
            message += "\n\nPour consulter la fiche projet, ajouter un commentaire ou modifier votre projet, connectez-vous à l'application Projets LFS : "
    else:
        message += "\n\nPour consulter cette fiche projet, valider le projet ou ajouter un commentaire, connectez-vous à l'application Projets LFS : "

    message += f"\n{website}project/{project.id}"

    # email subject
    if notification == "comment":
        subject = "Projets LFS : nouveau commentaire"
    elif notification == "ready":
        subject = f"Projets LFS : demande de validation {'initiale' if project.status == 'ready-1' else 'finale'}"
    elif notification == "validation":
        subject = f"Projets LFS : votre projet a été {'inclu au budget' if project.status == 'validated-1' else 'validé'})"

    gmail_send_message(
        format_addr([current_user.p.email]),
        format_addr(recipients),
        message,
        subject,
    )

    return None
