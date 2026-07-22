"""Online evaluation pipeline.

Tracks real-time search quality metrics from user interactions:
- Search success rate (searches that produce clicks)
- Zero-result rate
- Re-search rate (users reformulating queries)
- Response latency percentiles
- Click-through rate per position

Metrics are stored in Redis for real-time dashboards and periodically
flushed to persistent storage for trend analysis.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_KEY_PREFIX = "metrics:"
_SESSION_TTL = 3600
_METRICS_TTL = 86400 * 7


class SearchEvent(BaseModel):
    session_id: str
    query: str
    results_count: int
    took_ms: float
    timestamp: str = ""


class ClickEvent(BaseModel):
    session_id: str
    query: str
    article_id: str
    position: int
    timestamp: str = ""


class OnlineMetrics(BaseModel):
    period: str
    total_searches: int = 0
    successful_searches: int = 0
    zero_result_searches: int = 0
    re_searches: int = 0
    total_clicks: int = 0
    search_success_rate: float = 0.0
    zero_result_rate: float = 0.0
    re_search_rate: float = 0.0
    ctr: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    position_ctr: dict[int, float] = {}


class OnlineEvaluationService:
    """Tracks and computes online search quality metrics."""

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def record_search(self, event: SearchEvent) -> None:
        """Record a search event."""
        ts = event.timestamp or datetime.now(tz=timezone.utc).isoformat()
        day = ts[:10]
        pipe = self._redis.pipeline()

        pipe.incr(f"{_KEY_PREFIX}searches:{day}")
        pipe.expire(f"{_KEY_PREFIX}searches:{day}", _METRICS_TTL)

        if event.results_count == 0:
            pipe.incr(f"{_KEY_PREFIX}zero_results:{day}")
            pipe.expire(f"{_KEY_PREFIX}zero_results:{day}", _METRICS_TTL)

        pipe.rpush(f"{_KEY_PREFIX}latencies:{day}", str(event.took_ms))
        pipe.expire(f"{_KEY_PREFIX}latencies:{day}", _METRICS_TTL)

        prev_query = await self._redis.get(f"{_KEY_PREFIX}session_query:{event.session_id}")
        if prev_query and prev_query != event.query:
            pipe.incr(f"{_KEY_PREFIX}re_searches:{day}")
            pipe.expire(f"{_KEY_PREFIX}re_searches:{day}", _METRICS_TTL)

        pipe.set(
            f"{_KEY_PREFIX}session_query:{event.session_id}",
            event.query,
            ex=_SESSION_TTL,
        )

        await pipe.execute()

    async def record_click(self, event: ClickEvent) -> None:
        """Record a click event."""
        ts = event.timestamp or datetime.now(tz=timezone.utc).isoformat()
        day = ts[:10]
        pipe = self._redis.pipeline()

        pipe.incr(f"{_KEY_PREFIX}clicks:{day}")
        pipe.expire(f"{_KEY_PREFIX}clicks:{day}", _METRICS_TTL)

        pipe.incr(f"{_KEY_PREFIX}pos_clicks:{day}:{event.position}")
        pipe.expire(f"{_KEY_PREFIX}pos_clicks:{day}:{event.position}", _METRICS_TTL)

        pipe.sadd(f"{_KEY_PREFIX}clicked_sessions:{day}", event.session_id)
        pipe.expire(f"{_KEY_PREFIX}clicked_sessions:{day}", _METRICS_TTL)

        await pipe.execute()

    async def get_metrics(self, day: str | None = None) -> OnlineMetrics:
        """Compute aggregated metrics for a given day."""
        if day is None:
            day = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        total_searches = int(await self._redis.get(f"{_KEY_PREFIX}searches:{day}") or 0)
        zero_results = int(await self._redis.get(f"{_KEY_PREFIX}zero_results:{day}") or 0)
        re_searches = int(await self._redis.get(f"{_KEY_PREFIX}re_searches:{day}") or 0)
        total_clicks = int(await self._redis.get(f"{_KEY_PREFIX}clicks:{day}") or 0)
        successful = int(await self._redis.scard(f"{_KEY_PREFIX}clicked_sessions:{day}") or 0)

        latencies_raw = await self._redis.lrange(f"{_KEY_PREFIX}latencies:{day}", 0, -1)
        latencies = sorted(float(x) for x in latencies_raw) if latencies_raw else []

        position_ctr: dict[int, float] = {}
        for pos in range(1, 11):
            pos_clicks = int(await self._redis.get(f"{_KEY_PREFIX}pos_clicks:{day}:{pos}") or 0)
            if total_searches > 0:
                position_ctr[pos] = round(pos_clicks / total_searches, 4)

        return OnlineMetrics(
            period=day,
            total_searches=total_searches,
            successful_searches=successful,
            zero_result_searches=zero_results,
            re_searches=re_searches,
            total_clicks=total_clicks,
            search_success_rate=round(successful / total_searches, 4) if total_searches else 0,
            zero_result_rate=round(zero_results / total_searches, 4) if total_searches else 0,
            re_search_rate=round(re_searches / total_searches, 4) if total_searches else 0,
            ctr=round(total_clicks / total_searches, 4) if total_searches else 0,
            avg_latency_ms=round(sum(latencies) / len(latencies), 2) if latencies else 0,
            p50_latency_ms=_percentile(latencies, 50),
            p95_latency_ms=_percentile(latencies, 95),
            p99_latency_ms=_percentile(latencies, 99),
            position_ctr=position_ctr,
        )


def _percentile(sorted_values: list[float], p: int) -> float:
    if not sorted_values:
        return 0.0
    idx = int(len(sorted_values) * p / 100)
    idx = min(idx, len(sorted_values) - 1)
    return round(sorted_values[idx], 2)
