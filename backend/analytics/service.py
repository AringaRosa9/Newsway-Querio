"""Analytics tracking service.

Records and aggregates user interaction events for search quality
monitoring and product analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_KEY_PREFIX = "analytics:"
_TTL = 86400 * 30


class TrackEvent(BaseModel):
    event_type: str  # "search", "click", "view", "subscribe"
    session_id: str = ""
    user_id: str = ""
    query: str = ""
    article_id: str = ""
    position: int = 0
    duration_ms: int = 0
    metadata: dict = {}


class AnalyticsService:
    """Lightweight analytics backed by Redis counters."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def track(self, event: TrackEvent) -> None:
        """Record a tracking event."""
        day = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        pipe = self._redis.pipeline()

        pipe.incr(f"{_KEY_PREFIX}{event.event_type}:{day}")
        pipe.expire(f"{_KEY_PREFIX}{event.event_type}:{day}", _TTL)

        if event.event_type == "search" and event.query:
            pipe.zincrby(f"{_KEY_PREFIX}popular_queries:{day}", 1, event.query)
            pipe.expire(f"{_KEY_PREFIX}popular_queries:{day}", _TTL)

        if event.event_type == "click" and event.article_id:
            pipe.zincrby(f"{_KEY_PREFIX}popular_articles:{day}", 1, event.article_id)
            pipe.expire(f"{_KEY_PREFIX}popular_articles:{day}", _TTL)

        if event.event_type == "view" and event.duration_ms:
            pipe.rpush(f"{_KEY_PREFIX}dwell_times:{day}", str(event.duration_ms))
            pipe.expire(f"{_KEY_PREFIX}dwell_times:{day}", _TTL)

        await pipe.execute()

    async def get_summary(self, day: str | None = None) -> dict:
        """Get analytics summary for a day."""
        if day is None:
            day = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        searches = int(await self._redis.get(f"{_KEY_PREFIX}search:{day}") or 0)
        clicks = int(await self._redis.get(f"{_KEY_PREFIX}click:{day}") or 0)
        views = int(await self._redis.get(f"{_KEY_PREFIX}view:{day}") or 0)
        subscriptions = int(await self._redis.get(f"{_KEY_PREFIX}subscribe:{day}") or 0)

        popular_queries = await self._redis.zrevrange(
            f"{_KEY_PREFIX}popular_queries:{day}", 0, 9, withscores=True
        )
        popular_articles = await self._redis.zrevrange(
            f"{_KEY_PREFIX}popular_articles:{day}", 0, 9, withscores=True
        )

        return {
            "date": day,
            "searches": searches,
            "clicks": clicks,
            "views": views,
            "subscriptions": subscriptions,
            "ctr": round(clicks / searches, 4) if searches else 0,
            "popular_queries": [
                {"query": q, "count": int(s)} for q, s in popular_queries
            ],
            "popular_articles": [
                {"article_id": a, "count": int(s)} for a, s in popular_articles
            ],
        }
