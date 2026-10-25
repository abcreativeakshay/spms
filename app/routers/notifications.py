"""Notification + audit log endpoints (FR-37, FR-39)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.security import Principal, get_current_user, require_admin
from app.models.common import MessageResponse, PageResponse
from app.models.feedback import AuditLog, Notification
from app.routers.deps import as_page, get_audit_service, get_notifications_service
from app.services.audit import AuditService
from app.services.notify import NotificationService

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=PageResponse[Notification])
def list_notifications(
    unread_only: bool = Query(False, alias="unreadOnly"),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(get_current_user),
    service: NotificationService = Depends(get_notifications_service),
) -> dict:
    return as_page(
        service.list_for_user(user.uid, unread_only=unread_only, limit=limit, cursor=cursor)
    )


@router.patch("/notifications/read-all", response_model=MessageResponse)
def mark_all_read(
    user: Principal = Depends(get_current_user),
    service: NotificationService = Depends(get_notifications_service),
) -> dict:
    updated = service.mark_all_read(user.uid)
    return {"message": f"{updated} notification(s) marked as read"}


@router.patch("/notifications/{notification_id}/read", response_model=Notification)
def mark_read(
    notification_id: str,
    user: Principal = Depends(get_current_user),
    service: NotificationService = Depends(get_notifications_service),
) -> dict:
    return service.mark_read(user.uid, notification_id)


@router.get("/audit-logs", response_model=PageResponse[AuditLog])
def list_audit_logs(
    entity: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=100),
    cursor: str | None = Query(None),
    user: Principal = Depends(require_admin),
    service: AuditService = Depends(get_audit_service),
) -> dict:
    return as_page(service.list_logs(user, entity=entity, limit=limit, cursor=cursor))
