import logging
import base64
import os
from email.message import EmailMessage
from email.utils import formataddr

from googleapiclient.errors import HttpError

from . import gmail_service_api

APP_EMAIL = os.getenv("APP_EMAIL")

logger = logging.getLogger(__name__)


def gmail_send_message(sender, recipients, text, subject, html=None):
    """
    sender: reply-to address (string)
    recipients: string (comma-separated) or list of addresses
    text: plain-text body
    subject: subject string
    html: optional HTML body (string)
    """
    # 2. Guard clause: Do not attempt to send if the service is offline or disabled
    if not gmail_service_api:
        logger.warning(f"Email '{subject}' not sent: Gmail service is not initialized.")
        return None

    message = EmailMessage()

    # plain text fallback
    message.set_content(text)

    # HTML alternative
    if html:
        message.add_alternative(html, subtype="html")

    message["From"] = formataddr(("Projets LFS", APP_EMAIL))

    if isinstance(recipients, (list, tuple)):
        recipients = ", ".join(recipients)

    message["To"] = recipients
    message["Reply-To"] = sender
    message["Subject"] = subject

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    create_message = {"raw": encoded_message}

    try:
        send_message = (
            gmail_service_api.users().messages().send(userId="me", body=create_message).execute()
        )
        logger.info(f"Email sent successfully. Message ID: {send_message.get('id')}")
        return send_message

    # Catch the specific Google API error
    except HttpError as error:
        logger.error(f"Google API rejected the email: {error}")
        return None

    # Catch ANY other error (network drops, timeouts, bizarre bugs)
    # This guarantees the web route will never crash because of an email failure.
    except Exception as error:
        logger.error(f"An unexpected error occurred while sending email: {error}")
        return None
