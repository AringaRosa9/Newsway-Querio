"""Subscription API routes."""

from __future__ import annotations

import logging

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query

from auth.routes import require_current_user
from core.deps import get_es_client
from .models import SubscriptionCreateRequest, SubscriptionUpdateRequest
from .service import SubscriptionService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


def _get_sub_service(es: AsyncElasticsearch = Depends(get_es_client)) -> SubscriptionService:
    return SubscriptionService(es)


@router.post("")
async def create_subscription(
    req: SubscriptionCreateRequest,
    user: dict = Depends(require_current_user),
    svc: SubscriptionService = Depends(_get_sub_service),
) -> dict:
    await svc.ensure_indices()
    result = await svc.create(user["id"], req.model_dump())
    return result


@router.get("")
async def list_subscriptions(
    user: dict = Depends(require_current_user),
    svc: SubscriptionService = Depends(_get_sub_service),
) -> dict:
    await svc.ensure_indices()
    subs = await svc.list_by_user(user["id"])
    return {"subscriptions": subs, "total": len(subs)}


@router.get("/{sub_id}")
async def get_subscription(
    sub_id: str,
    user: dict = Depends(require_current_user),
    svc: SubscriptionService = Depends(_get_sub_service),
) -> dict:
    sub = await svc.get(sub_id, user["id"])
    if sub is None:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return sub


@router.put("/{sub_id}")
async def update_subscription(
    sub_id: str,
    req: SubscriptionUpdateRequest,
    user: dict = Depends(require_current_user),
    svc: SubscriptionService = Depends(_get_sub_service),
) -> dict:
    result = await svc.update(sub_id, user["id"], req.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return result


@router.delete("/{sub_id}")
async def delete_subscription(
    sub_id: str,
    user: dict = Depends(require_current_user),
    svc: SubscriptionService = Depends(_get_sub_service),
) -> dict:
    ok = await svc.delete(sub_id, user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="订阅不存在")
    return {"status": "deleted"}


@router.get("/notifications/list")
async def list_notifications(
    unread_only: bool = Query(False),
    user: dict = Depends(require_current_user),
    svc: SubscriptionService = Depends(_get_sub_service),
) -> dict:
    await svc.ensure_indices()
    notifications = await svc.list_notifications(user["id"], unread_only=unread_only)
    return {"notifications": notifications, "total": len(notifications)}


@router.post("/notifications/{notif_id}/read")
async def mark_read(
    notif_id: str,
    user: dict = Depends(require_current_user),
    svc: SubscriptionService = Depends(_get_sub_service),
) -> dict:
    ok = await svc.mark_notification_read(notif_id, user["id"])
    if not ok:
        raise HTTPException(status_code=404, detail="通知不存在")
    return {"status": "read"}
