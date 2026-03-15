from .models import db, QueuedAction
from .utils import get_datetime
from . import gmail_service_api


def queue_notification(user_id, action_type, parameters, options=None):
    """
    Queues a notification action in the database.
    Returns a warning string if the GMail API is disconnected, else None.
    """
    if not gmail_service_api:
        return "API GMail non connectée : aucune notification envoyée par e-mail."

    async_action = QueuedAction(
        uid=user_id,
        timestamp=get_datetime(),
        status="pending",
        action_type=action_type,
        parameters=parameters,
        options=options,
    )
    db.session.add(async_action)
    return None


def queue_status_notification(project, user_id):
    """Shortcut for queuing project status changes"""
    return queue_notification(
        user_id=user_id,
        action_type="send_notification",
        parameters=f"{project.status},{project.id}",
    )


def queue_comment_notification(project_id, comment_id, user_id, recipients_str):
    """Shortcut for queuing new comment notifications"""
    return queue_notification(
        user_id=user_id,
        action_type="send_notification",
        parameters=f"comment,{project_id},{comment_id}",
        options=recipients_str,
    )
