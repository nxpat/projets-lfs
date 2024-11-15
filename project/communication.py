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
    if notification not in ["comment", "ready", "validation"]:
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
    elif notification == "ready":
        recipients = [
            personnel.email
            for personnel in Personnel.query.filter(Personnel.role == "gestion").all()
            if personnel.user.preferences == "email"
        ]
    elif notification == "validation":
        recipients = project.teachers.split(",")

    if recipients == []:
        return "Attention : aucune notification par e-mail n'a pu être envoyée"

    message = "Bonjour,"

    # email message
    if notification == "comment":
        message += f"\n\nUn nouveau commentaire sur le projet '{project.title}' a été ajouté par {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}):\n\n"
        message += text
    elif notification == "ready":
        message += f"\n\nUne demande de validation {'initiale' if project.status == 'ready-1' else 'finale'} vient d'être déposée :\nAutheur : {current_user.p.firstname} {current_user.p.name} ({current_user.p.email}) \nProjet : {project.title}"
    elif notification == "validation":
        message += f"\n\nVotre projet :\n{project.title}\n\na été validé {'et inclu au budget' if project.status == 'validated-1' else ''} (validation {'initiale' if project.status == 'validated-1' else 'finale'})."

    if current_user.p.role in ["gestion", "direction"]:
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
        subject = f"Projets LFS : votre projet a été validé (validation {'initiale' if project.status == 'validated-1' else 'finale'})"

    gmail_send_message(
        format_addr([current_user.p.email]),
        format_addr(recipients),
        message,
        subject,
    )

    return None
