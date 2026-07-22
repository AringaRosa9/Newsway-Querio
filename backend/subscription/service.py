"""Subscription management service.

Handles CRUD for subscriptions and processes notifications when
new articles match subscription criteria.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from elasticsearch import AsyncElasticsearch, NotFoundError

from core.config import get_settings

logger = logging.getLogger(__name__)

_SUBS_INDEX = "news_subscriptions"
_NOTIFICATIONS_INDEX = "news_notifications"


class SubscriptionService:
    """Manages user subscriptions and notification delivery."""

    def __init__(self, es: AsyncElasticsearch) -> None:
        self._es = es

    async def ensure_indices(self) -> None:
        for index, mapping in [
            (
                _SUBS_INDEX,
                {
                    "mappings": {
                        "properties": {
                            "user_id": {"type": "keyword"},
                            "name": {"type": "text"},
                            "subscription_type": {"type": "keyword"},
                            "query": {"type": "text"},
                            "filters": {"type": "object", "enabled": False},
                            "notify_email": {"type": "boolean"},
                            "notify_push": {"type": "boolean"},
                            "frequency": {"type": "keyword"},
                            "is_active": {"type": "boolean"},
                            "last_checked": {"type": "date"},
                            "last_notified": {"type": "date"},
                            "created_at": {"type": "date"},
                        }
                    }
                },
            ),
            (
                _NOTIFICATIONS_INDEX,
                {
                    "mappings": {
                        "properties": {
                            "user_id": {"type": "keyword"},
                            "subscription_id": {"type": "keyword"},
                            "title": {"type": "text"},
                            "body": {"type": "text"},
                            "article_ids": {"type": "keyword"},
                            "is_read": {"type": "boolean"},
                            "created_at": {"type": "date"},
                        }
                    }
                },
            ),
        ]:
            exists = await self._es.indices.exists(index=index)
            if not exists:
                await self._es.indices.create(index=index, body=mapping)
                logger.info("Created index '%s'", index)

    async def create(self, user_id: str, data: dict) -> dict:
        """Create a new subscription."""
        sub_id = str(uuid.uuid4())
        doc = {
            "user_id": user_id,
            "name": data["name"],
            "subscription_type": data.get("subscription_type", "keyword"),
            "query": data["query"],
            "filters": data.get("filters", {}),
            "notify_email": data.get("notify_email", True),
            "notify_push": data.get("notify_push", False),
            "frequency": data.get("frequency", "realtime"),
            "is_active": True,
            "last_checked": "",
            "last_notified": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._es.index(index=_SUBS_INDEX, id=sub_id, body=doc)
        await self._es.indices.refresh(index=_SUBS_INDEX)
        doc["id"] = sub_id
        return doc

    async def list_by_user(self, user_id: str) -> list[dict]:
        """List all subscriptions for a user."""
        result = await self._es.search(
            index=_SUBS_INDEX,
            body={
                "query": {"term": {"user_id": user_id}},
                "sort": [{"created_at": {"order": "desc"}}],
                "size": 100,
            },
        )
        subs = []
        for hit in result["hits"]["hits"]:
            doc = hit["_source"]
            doc["id"] = hit["_id"]
            subs.append(doc)
        return subs

    async def get(self, sub_id: str, user_id: str) -> dict | None:
        """Get a subscription by ID, verifying ownership."""
        try:
            doc = await self._es.get(index=_SUBS_INDEX, id=sub_id)
            source = doc["_source"]
            if source["user_id"] != user_id:
                return None
            source["id"] = doc["_id"]
            return source
        except NotFoundError:
            return None

    async def update(self, sub_id: str, user_id: str, updates: dict) -> dict | None:
        """Update a subscription."""
        existing = await self.get(sub_id, user_id)
        if existing is None:
            return None

        clean = {k: v for k, v in updates.items() if v is not None}
        if not clean:
            return existing

        await self._es.update(index=_SUBS_INDEX, id=sub_id, body={"doc": clean})
        return await self.get(sub_id, user_id)

    async def delete(self, sub_id: str, user_id: str) -> bool:
        """Delete a subscription."""
        existing = await self.get(sub_id, user_id)
        if existing is None:
            return False
        await self._es.delete(index=_SUBS_INDEX, id=sub_id)
        return True

    async def create_notification(
        self, user_id: str, subscription_id: str, title: str, body: str, article_ids: list[str]
    ) -> dict:
        """Create a notification for a subscription match."""
        notif_id = str(uuid.uuid4())
        doc = {
            "user_id": user_id,
            "subscription_id": subscription_id,
            "title": title,
            "body": body,
            "article_ids": article_ids,
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._es.index(index=_NOTIFICATIONS_INDEX, id=notif_id, body=doc)
        doc["id"] = notif_id
        return doc

    async def list_notifications(
        self, user_id: str, unread_only: bool = False, limit: int = 50
    ) -> list[dict]:
        """List notifications for a user."""
        query: dict[str, Any] = {"bool": {"must": [{"term": {"user_id": user_id}}]}}
        if unread_only:
            query["bool"]["must"].append({"term": {"is_read": False}})

        result = await self._es.search(
            index=_NOTIFICATIONS_INDEX,
            body={
                "query": query,
                "sort": [{"created_at": {"order": "desc"}}],
                "size": limit,
            },
        )
        notifications = []
        for hit in result["hits"]["hits"]:
            doc = hit["_source"]
            doc["id"] = hit["_id"]
            notifications.append(doc)
        return notifications

    async def mark_notification_read(self, notif_id: str, user_id: str) -> bool:
        """Mark a notification as read."""
        try:
            doc = await self._es.get(index=_NOTIFICATIONS_INDEX, id=notif_id)
            if doc["_source"]["user_id"] != user_id:
                return False
            await self._es.update(
                index=_NOTIFICATIONS_INDEX,
                id=notif_id,
                body={"doc": {"is_read": True}},
            )
            return True
        except NotFoundError:
            return False

    async def check_subscriptions(
        self, search_fn: Any, es: AsyncElasticsearch
    ) -> int:
        """Check all active subscriptions for new matches.

        Returns the number of notifications created.
        """
        result = await self._es.search(
            index=_SUBS_INDEX,
            body={
                "query": {"term": {"is_active": True}},
                "size": 1000,
            },
        )

        count = 0
        for hit in result["hits"]["hits"]:
            sub = hit["_source"]
            sub_id = hit["_id"]
            try:
                articles = await search_fn(sub["query"])
                if not articles:
                    continue

                new_articles = []
                last_checked = sub.get("last_checked", "")
                for a in articles[:10]:
                    pub = a.get("published_at", "")
                    if pub > last_checked:
                        new_articles.append(a)

                if new_articles:
                    title = f"「{sub['name']}」有 {len(new_articles)} 条新动态"
                    body = " | ".join(
                        a.get("title", "")[:50] for a in new_articles[:3]
                    )
                    await self.create_notification(
                        sub["user_id"],
                        sub_id,
                        title,
                        body,
                        [a.get("id", "") for a in new_articles],
                    )
                    count += 1

                await self._es.update(
                    index=_SUBS_INDEX,
                    id=sub_id,
                    body={
                        "doc": {
                            "last_checked": datetime.now(timezone.utc).isoformat()
                        }
                    },
                )
            except Exception as exc:
                logger.warning("Failed to check subscription %s: %s", sub_id, exc)

        return count
