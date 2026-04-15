import logging
import base64
import os
import time
from email.message import EmailMessage
from email.utils import formataddr

from googleapiclient.errors import HttpError

from . import gmail_service_api

APP_EMAIL = os.getenv("APP_EMAIL")

logger = logging.getLogger(__name__)


def gmail_send_message(sender, recipients, text, subject, html=None):
    if not gmail_service_api:
        logger.warning(f"Email '{subject}' not sent: Gmail service is not initialized.")
        return None

    message = EmailMessage()
    message.set_content(text)

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

    max_retries = 3

    for attempt in range(max_retries):
        try:
            send_message = (
                gmail_service_api.users()
                .messages()
                .send(userId="me", body=create_message)
                .execute()
            )
            logger.info(f"Email sent successfully. Message ID: {send_message.get('id')}")
            return send_message

        # Catch Google-specific errors (e.g., 400 Bad Request, invalid address)
        except HttpError as error:
            logger.error(f"Google API rejected the email '{subject}': {error}")
            # Do NOT retry. This is a hard error that will never succeed.
            break

        # Catch network errors (like the EOF protocol error or timeouts)
        except Exception as error:
            logger.warning(f"Connection dropped (attempt {attempt + 1}/{max_retries}): {error}")

            if attempt < max_retries - 1:
                time.sleep(2)  # Wait 2 seconds. The next loop will force a brand new, fresh socket!
            else:
                logger.error(f"Email failed after {max_retries} attempts. Final error: {error}")

    # If the loop finishes without returning, the email failed completely
    return None
