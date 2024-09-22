import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from requests import HTTPError

from . import service, logger


def gmail_send(text, sender, recipients, subject=""):
    message = MIMEMultipart()
    message["to"] = recipients
    message["reply-to"] = sender
    if subject == "":
        message["subject"] = "Projets LFS : nouveau commentaire"
    else:
        message["subject"] = subject
    message.attach(MIMEText(text, "plain"))

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {"raw": encoded_message}

    try:
        send_message = (
            service.users().messages().send(userId="me", body=create_message).execute()
        )
        logger.info(send_message)
    except HTTPError as error:
        print(f"An error occurred: {error}")
        send_message = None
