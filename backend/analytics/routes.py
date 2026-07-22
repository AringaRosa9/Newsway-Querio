"""Analytics API routes."""

from __future__ import annotations

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query

from core.deps import get_redis_client
from evaluation.online import ClickEvent, OnlineEvaluationService, SearchEvent
from .service import AnalyticsService, TrackEvent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _get_analytics_service(
    redis: aioredis.Redis = Depends(get_redis_client),
) -> AnalyticsService:
    return AnalyticsService(redis)


def _get_eval_service(
    redis: aioredis.Redis = Depends(get_redis_client),
) -> OnlineEvaluationService:
    return OnlineEvaluationService(redis)


@router.post("/track")
async def track_event(
    event: TrackEvent,
    analytics: AnalyticsService = Depends(_get_analytics_service),
    eval_svc: OnlineEvaluationService = Depends(_get_eval_service),
) -> dict:
    """Record a tracking event from the frontend."""
    await analytics.track(event)

    if event.event_type == "search":
        await eval_svc.record_search(
            SearchEvent(
                session_id=event.session_id,
                query=event.query,
                results_count=event.metadata.get("results_count", 0),
                took_ms=event.metadata.get("took_ms", 0),
            )
        )
    elif event.event_type == "click":
        await eval_svc.record_click(
            ClickEvent(
                session_id=event.session_id,
                query=event.query,
                article_id=event.article_id,
                position=event.position,
            )
        )

    return {"status": "ok"}


@router.get("/summary")
async def get_analytics_summary(
    day: str | None = Query(None, description="Date in YYYY-MM-DD format"),
    analytics: AnalyticsService = Depends(_get_analytics_service),
) -> dict:
    return await analytics.get_summary(day)


@router.get("/metrics")
async def get_online_metrics(
    day: str | None = Query(None, description="Date in YYYY-MM-DD format"),
    eval_svc: OnlineEvaluationService = Depends(_get_eval_service),
) -> dict:
    metrics = await eval_svc.get_metrics(day)
    return metrics.model_dump()
