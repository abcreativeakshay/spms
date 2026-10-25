"""In-app notifications + email queue (FR-37)."""

from __future__ import annotations

from typing import Iterable

from app.models.enums import NotificationType
from app.repositories import Repos
from app.services.metrics import utcnow


class NotificationService:
    def __init__(self, repos: Repos) -> None:
        self.repos = repos

    def notify(
        self,
        user_ids: Iterable[str],
        *,
        notification_type: NotificationType,
        title: str,
        body: str,
        link: str | None = None,
        email: bool = False,
    ) -> int:
        created = 0
        for user_id in {uid for uid in user_ids if uid}:
            self.repos.notifications.create(
                {
                    "userId": user_id,
                    "type": notification_type.value,
                    "title": title,
                    "body": body,
                    "read": False,
                    "link": link,
                    "createdAt": utcnow(),
                }
            )
            created += 1
            if email:
                self.queue_email(user_id, title, body)
        return created

    def queue_email(self, user_id: str, subject: str, body: str) -> None:
        """Writes to the `mail` collection consumed by the Trigger Email extension."""
        user = self.repos.users.get(user_id)
        if not user or not user.get("email"):
            return
        self.repos.store.set(
            "mail",
            self.repos.store.new_id(),
            {
                "to": [user["email"]],
                "message": {"subject": subject, "text": body},
                "createdAt": utcnow(),
            },
        )

    def notify_college_admins(
        self,
        college_id: str,
        *,
        notification_type: NotificationType,
        title: str,
        body: str,
        link: str | None = None,
    ) -> None:
        admins = self.repos.users.by_role("admin", college_id)
        # Super admins carry collegeIds=["*"], so `array_contains` never matches
        # them. Include every super admin explicitly.
        super_admins = [
            user for user in self.repos.users.by_role("admin") if user.get("superAdmin")
        ]
        self.notify(
            [user["id"] for user in [*admins, *super_admins]],
            notification_type=notification_type,
            title=title,
            body=body,
            link=link,
        )

    def list_for_user(
        self,
        user_id: str,
        *,
        unread_only: bool = False,
        limit: int | None = None,
        cursor: str | None = None,
    ):
        filters: list[tuple[str, str, object]] = [("userId", "==", user_id)]
        if unread_only:
            filters.append(("read", "==", False))
        page = self.repos.notifications.list(
            filters, order_by="createdAt", descending=True, limit=limit, cursor=cursor
        )
        page.items = page.items
        return page

    def mark_read(self, user_id: str, notification_id: str) -> dict:
        from app.core.errors import Forbidden, NotFound

        notification = self.repos.notifications.get(notification_id)
        if notification is None:
            raise NotFound("Notification not found", code="notification_not_found")
        if notification.get("userId") != user_id:
            raise Forbidden("You can only update your own notifications", code="notification_forbidden")
        return self.repos.notifications.update(notification_id, {"read": True})

    def mark_all_read(self, user_id: str) -> int:
        docs = self.repos.notifications.for_user(user_id, limit=1000)
        updated = 0
        for doc in docs:
            if not doc.get("read"):
                self.repos.notifications.update(doc["id"], {"read": True})
                updated += 1
        return updated
