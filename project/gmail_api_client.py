import base64
from email.message import EmailMessage
from requests import HTTPError

from email.utils import formataddr

from . import service, logger

import os

APP_EMAIL = os.getenv("APP_EMAIL")


def gmail_send_message(sender, recipients, text, subject, html=None):
    """
    sender: reply-to address (string)
    recipients: string (comma-separated) or list of addresses
    text: plain-text body
    subject: subject string
    html: optional HTML body (string)
    """
    message = EmailMessage()

    # plain text fallback
    message.set_content(text)

    # HTML alternative
    if html:
        message.add_alternative(html, subtype="html")

    message["From"] = formataddr(("Projets LFS", APP_EMAIL))
    # recipients can be list or comma-joined string
    if isinstance(recipients, (list, tuple)):
        recipients = ", ".join(recipients)
    message["To"] = recipients
    message["Reply-To"] = sender
    message["Subject"] = subject

    print(html)

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {"raw": encoded_message}

    try:
        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        logger.info(send_message)
        return send_message
    except HTTPError as error:
        logger.error(f"An error occurred: {error}")
        return None
