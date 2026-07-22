"""Subscription data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class Subscription(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    subscription_type: str  # "keyword", "topic", "event"
    query: str
    filters: dict = Field(default_factory=dict)
    notify_email: bool = True
    notify_push: bool = False
    frequency: str = "realtime"  # "realtime", "daily", "weekly"
    is_active: bool = True
    last_checked: str = ""
    last_notified: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SubscriptionCreateRequest(BaseModel):
    name: str
    subscription_type: str = "keyword"
    query: str
    filters: dict = Field(default_factory=dict)
    notify_email: bool = True
    notify_push: bool = False
    frequency: str = "realtime"


class SubscriptionUpdateRequest(BaseModel):
    name: Optional[str] = None
    query: Optional[str] = None
    filters: Optional[dict] = None
    notify_email: Optional[bool] = None
    notify_push: Optional[bool] = None
    frequency: Optional[str] = None
    is_active: Optional[bool] = None


class Notification(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    subscription_id: str
    title: str
    body: str
    article_ids: list[str] = Field(default_factory=list)
    is_read: bool = False
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
