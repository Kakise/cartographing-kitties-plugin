"""Notification service for sending alerts and messages."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.models.user import User


class NotificationChannel(Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


@dataclass
class Notification:
    recipient: User
    subject: str
    body: str
    channel: NotificationChannel = NotificationChannel.EMAIL
    sent_at: datetime | None = None
    is_read: bool = False

    def mark_read(self) -> None:
        self.is_read = True


class NotificationService:
    """Manages sending and tracking notifications."""

    def __init__(self) -> None:
        self._sent: list[Notification] = []
        self._queue: list[Notification] = []

    def send(
        self,
        user: User,
        subject: str,
        body: str,
        channel: NotificationChannel = NotificationChannel.EMAIL,
    ) -> Notification:
        """Send a notification to a user."""
        notification = Notification(
            recipient=user,
            subject=subject,
            body=body,
            channel=channel,
            sent_at=datetime.now(),
        )
        self._sent.append(notification)
        return notification

    def queue(
        self,
        user: User,
        subject: str,
        body: str,
        channel: NotificationChannel = NotificationChannel.EMAIL,
    ) -> None:
        """Queue a notification for later delivery."""
        notification = Notification(
            recipient=user,
            subject=subject,
            body=body,
            channel=channel,
        )
        self._queue.append(notification)

    def flush_queue(self) -> int:
        """Send all queued notifications. Returns count sent."""
        count = 0
        for notification in self._queue:
            notification.sent_at = datetime.now()
            self._sent.append(notification)
            count += 1
        self._queue.clear()
        return count

    def get_unread(self, user: User) -> list[Notification]:
        """Get all unread notifications for a user."""
        return [n for n in self._sent if n.recipient.id == user.id and not n.is_read]

    def get_history(self, user: User, limit: int = 50) -> list[Notification]:
        """Get notification history for a user."""
        user_notifications = [n for n in self._sent if n.recipient.id == user.id]
        return sorted(user_notifications, key=lambda n: n.sent_at or datetime.min, reverse=True)[
            :limit
        ]
