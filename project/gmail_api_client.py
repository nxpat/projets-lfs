import base64
from email.message import EmailMessage
from requests import HTTPError

from email.utils import formataddr

from . import service, logger


def gmail_send_message(sender, recipients, text, subject):
    message = EmailMessage()

    message.set_content(text)

    message["From"] = formataddr(("Projets LFS", "projets-lfs@lfseoul.org"))
    message["To"] = recipients
    message["Reply-To"] = sender
    message["Subject"] = subject

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
