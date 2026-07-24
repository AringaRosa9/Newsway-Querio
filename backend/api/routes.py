"""Top-level API router.

Individual feature routers (search, ingest, ai) are mounted here as the
backend grows. For now this file wires together the sub-routers that
already exist and exposes a single `router` that main.py includes.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from qdrant_client import QdrantClient
import redis.asyncio as aioredis

from core.config import get_settings
from core.deps import get_es_client, get_qdrant_client, get_redis_client
from ai.embedding import get_embedding_service
from ai.summary import SummaryService
from ai.streaming import stream_summary
from ai.event import aggregate_events
from search.query import ParsedQuery, parse_query
from search.retrieval import hybrid_search
from search.ranking import rerank
from search.personalization import personalize
from search.crosslingual import crosslingual_search, detect_language
from search.vertical import detect_vertical, apply_vertical_boost, list_verticals
from cache.service import CacheService
from security.middleware import sanitize_search_query
from auth.routes import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Existing status endpoint (preserved for backwards compatibility)
# ---------------------------------------------------------------------------


@router.get("/status", tags=["ops"])
async def api_status() -> dict:
    return {"status": "ready"}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ArticleResult(BaseModel):
    id: str
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    sentiment: Optional[str] = None
    entities: Optional[list[str]] = None
    summary: Optional[str] = None
    score: Optional[float] = None
    final_score: Optional[float] = None


class SummaryData(BaseModel):
    summary_text: str
    citations: list[dict[str, Any]]
    generated_at: Optional[datetime] = None


class SearchResponse(BaseModel):
    query: str
    parsed_query: ParsedQuery
    summary: SummaryData
    results: list[ArticleResult]
    total: int
    page: int
    page_size: int
    took_ms: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _article_result_from_dict(doc: dict) -> ArticleResult:
    """Convert a retrieval/ranking result dict to an ArticleResult model."""
    return ArticleResult(
        id=str(doc.get("id", "")),
        title=doc.get("title"),
        content=doc.get("content"),
        source=doc.get("source"),
        url=doc.get("url"),
        published_at=(
            doc["published_at"].isoformat()
            if isinstance(doc.get("published_at"), datetime)
            else doc.get("published_at")
        ),
        author=doc.get("author"),
        category=doc.get("category"),
        sentiment=doc.get("sentiment"),
        entities=doc.get("entities"),
        summary=doc.get("summary"),
        score=doc.get("score"),
        final_score=doc.get("final_score"),
    )


def _build_search_filters(
    time_from: Optional[datetime],
    time_to: Optional[datetime],
    source: Optional[str],
    category: Optional[str],
    sentiment: Optional[str],
    parsed: ParsedQuery,
) -> dict:
    """Merge explicit query-param filters with parsed time range."""
    filters: dict[str, Any] = {}

    # Explicit params take precedence over query-parsed time range
    if time_from:
        filters["time_from"] = time_from
    elif parsed.time_range:
        filters["time_from"] = parsed.time_range[0]

    if time_to:
        filters["time_to"] = time_to
    elif parsed.time_range:
        filters["time_to"] = parsed.time_range[1]

    if source:
        filters["source"] = source
    if category:
        filters["category"] = category
    if sentiment:
        filters["sentiment"] = sentiment

    return filters


# ---------------------------------------------------------------------------
# GET /api/search
# ---------------------------------------------------------------------------


@router.get("/api/search", response_model=SearchResponse, tags=["search"])
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    time_from: Optional[datetime] = Query(None, description="Filter articles from this datetime (ISO 8601)"),
    time_to: Optional[datetime] = Query(None, description="Filter articles up to this datetime (ISO 8601)"),
    source: Optional[str] = Query(None, description="Filter by news source"),
    category: Optional[str] = Query(None, description="Filter by category"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment: positive/negative/neutral"),
    language: Optional[str] = Query(None, description="Filter by language: zh/en"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    crosslingual: bool = Query(True, description="Enable cross-language search"),
    es: AsyncElasticsearch = Depends(get_es_client),
    qdrant: QdrantClient = Depends(get_qdrant_client),
    redis: aioredis.Redis = Depends(get_redis_client),
    current_user: dict | None = Depends(get_current_user),
) -> SearchResponse:
    """Full hybrid search with AI-generated summary, caching, cross-language, and vertical boost."""
    t0 = time.perf_counter()
    settings = get_settings()

    # 0. Sanitize input
    try:
        safe_q = sanitize_search_query(q)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid search query")

    # 0.5. Check cache
    cache_svc = CacheService(redis)
    filter_dict = {
        "time_from": time_from.isoformat() if time_from else None,
        "time_to": time_to.isoformat() if time_to else None,
        "source": source, "category": category,
        "sentiment": sentiment, "language": language,
    }
    cached = await cache_svc.get_cached_results(safe_q, filter_dict)
    if cached and not current_user:
        await cache_svc.record_hit("search")
        took_ms = (time.perf_counter() - t0) * 1000
        cached["took_ms"] = round(took_ms, 2)
        return SearchResponse(**cached)
    await cache_svc.record_miss("search")

    # 1. Parse the query
    parsed = parse_query(safe_q)

    # 2. Embed the query
    try:
        embedding_svc = get_embedding_service()
        query_vector = embedding_svc.get_query_embedding(safe_q)
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        raise HTTPException(status_code=503, detail="Embedding service unavailable")

    # 3. Build filters
    filters = _build_search_filters(time_from, time_to, source, category, sentiment, parsed)

    # 4. Hybrid search (with optional cross-language)
    try:
        if crosslingual and detect_language(safe_q) != "mixed":
            raw_results = await crosslingual_search(
                es_client=es,
                qdrant_client=qdrant,
                query=safe_q,
                query_vector=query_vector,
                filters=filters,
                top_k=settings.MAX_SEARCH_RESULTS,
                api_key=settings.ANTHROPIC_API_KEY,
            )
        else:
            raw_results = await hybrid_search(
                es_client=es,
                qdrant_client=qdrant,
                query=safe_q,
                query_vector=query_vector,
                filters=filters,
                top_k=settings.MAX_SEARCH_RESULTS,
            )
    except Exception as exc:
        logger.error("Search failed: %s", exc)
        raise HTTPException(status_code=503, detail="Search service error")

    # 5. Re-rank
    ranked_results = rerank(raw_results, safe_q)

    # 5.5. Industry vertical boost
    vertical = detect_vertical(safe_q)
    if vertical:
        ranked_results = apply_vertical_boost(ranked_results, vertical)

    # 5.6. Personalize (if user is authenticated)
    if current_user:
        user_profile = current_user.get("profile")
        from auth.service import AuthService
        auth_svc = AuthService(es)
        reading_history = await auth_svc.get_reading_history(current_user["id"])
        ranked_results = personalize(ranked_results, user_profile, reading_history)

    # 6. Paginate
    total = len(ranked_results)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = ranked_results[start:end]

    # 7. Generate AI summary (check cache first)
    summary_docs = ranked_results[: settings.SUMMARY_MAX_DOCS]
    article_ids = [str(d.get("id", "")) for d in summary_docs]

    cached_summary = await cache_svc.get_cached_summary(safe_q, article_ids)
    if cached_summary:
        await cache_svc.record_hit("summary")
        summary_data = cached_summary
    else:
        await cache_svc.record_miss("summary")
        try:
            summary_svc = SummaryService(api_key=settings.ANTHROPIC_API_KEY)
            summary_data = await summary_svc.generate_summary(safe_q, summary_docs)
            await cache_svc.cache_summary(safe_q, article_ids, summary_data)
        except Exception as exc:
            logger.error("Summary generation failed: %s", exc)
            summary_data = {
                "summary_text": "Summary unavailable.",
                "citations": [],
                "generated_at": datetime.now(tz=timezone.utc),
            }

    took_ms = (time.perf_counter() - t0) * 1000

    response_data = SearchResponse(
        query=safe_q,
        parsed_query=parsed,
        summary=SummaryData(**summary_data),
        results=[_article_result_from_dict(r) for r in page_results],
        total=total,
        page=page,
        page_size=page_size,
        took_ms=round(took_ms, 2),
    )

    if not current_user:
        await cache_svc.cache_results(safe_q, filter_dict, response_data.model_dump(mode="json"))

    return response_data


# ---------------------------------------------------------------------------
# GET /api/search/stream — SSE streaming summary
# ---------------------------------------------------------------------------


@router.get("/api/search/stream", tags=["search"])
async def search_stream(
    q: str = Query(..., min_length=1, description="Search query"),
    time_from: Optional[datetime] = Query(None),
    time_to: Optional[datetime] = Query(None),
    source: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None),
    es: AsyncElasticsearch = Depends(get_es_client),
    qdrant: QdrantClient = Depends(get_qdrant_client),
) -> StreamingResponse:
    """Streaming search: returns results immediately, then streams AI summary via SSE."""
    settings = get_settings()

    try:
        safe_q = sanitize_search_query(q)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid search query")

    try:
        embedding_svc = get_embedding_service()
        query_vector = embedding_svc.get_query_embedding(safe_q)
    except Exception as exc:
        logger.error("Embedding failed: %s", exc)
        raise HTTPException(status_code=503, detail="Embedding service unavailable")

    parsed = parse_query(safe_q)
    filters = _build_search_filters(time_from, time_to, source, category, sentiment, parsed)

    raw_results = await hybrid_search(
        es_client=es, qdrant_client=qdrant,
        query=safe_q, query_vector=query_vector,
        filters=filters, top_k=settings.MAX_SEARCH_RESULTS,
    )
    ranked = rerank(raw_results, safe_q)
    summary_docs = ranked[:settings.SUMMARY_MAX_DOCS]

    import json as _json

    async def _event_generator():
        results_data = [_article_result_from_dict(r).model_dump(mode="json") for r in ranked[:20]]
        yield f"event: results\ndata: {_json.dumps({'results': results_data, 'total': len(ranked)}, ensure_ascii=False)}\n\n"

        async for chunk in _async_stream_wrapper(stream_summary(safe_q, summary_docs)):
            yield chunk

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


async def _async_stream_wrapper(gen):
    async for item in gen:
        yield item


# ---------------------------------------------------------------------------
# Vertical & Cache utility endpoints
# ---------------------------------------------------------------------------


@router.get("/api/verticals", tags=["search"])
async def get_verticals() -> dict:
    return {"verticals": list_verticals()}


@router.get("/api/cache/stats", tags=["ops"])
async def cache_stats(
    redis: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    svc = CacheService(redis)
    return await svc.get_stats()


@router.post("/api/cache/invalidate", tags=["ops"])
async def invalidate_cache(
    redis: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    svc = CacheService(redis)
    count = await svc.invalidate_all()
    return {"invalidated": count}


# ---------------------------------------------------------------------------
# GET /api/article/{article_id}
# ---------------------------------------------------------------------------


@router.get("/api/article/{article_id}", response_model=ArticleResult, tags=["search"])
async def get_article(
    article_id: str,
    es: AsyncElasticsearch = Depends(get_es_client),
) -> ArticleResult:
    """Retrieve a full article by its Elasticsearch document ID."""
    settings = get_settings()
    try:
        doc = await es.get(index=settings.ES_INDEX, id=article_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Article '{article_id}' not found")
    except Exception as exc:
        logger.error("ES get error for id=%s: %s", article_id, exc)
        raise HTTPException(status_code=503, detail="Database error")

    source = doc.get("_source", {})
    source["id"] = doc["_id"]
    return _article_result_from_dict(source)


# ---------------------------------------------------------------------------
# POST /api/ingest/trigger
# ---------------------------------------------------------------------------


@router.post("/api/ingest/trigger", tags=["ops"])
async def trigger_ingestion() -> dict:
    """Manually trigger an ingestion cycle.

    The actual ingestion is delegated to the background scheduler. This
    endpoint signals that a cycle should run immediately.
    """
    try:
        # Import lazily to avoid circular imports if the ingestion module
        # hasn't been implemented yet.
        from ingestion.scheduler import trigger_now  # type: ignore

        await trigger_now()
        return {"status": "triggered", "message": "Ingestion cycle started"}
    except ImportError:
        logger.warning("Ingestion scheduler not available")
        return {
            "status": "unavailable",
            "message": "Ingestion module not yet configured",
        }
    except Exception as exc:
        logger.error("Failed to trigger ingestion: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to trigger ingestion")


# ---------------------------------------------------------------------------
# GET /api/stats
# ---------------------------------------------------------------------------


@router.get("/api/stats", tags=["ops"])
async def get_stats(
    es: AsyncElasticsearch = Depends(get_es_client),
    qdrant: QdrantClient = Depends(get_qdrant_client),
) -> dict:
    """Return basic index/collection statistics."""
    settings = get_settings()
    stats: dict[str, Any] = {}

    # Elasticsearch: total articles
    try:
        count_resp = await es.count(index=settings.ES_INDEX)
        stats["total_articles"] = count_resp.get("count", 0)
    except Exception as exc:
        logger.warning("Could not fetch ES article count: %s", exc)
        stats["total_articles"] = None

    # Elasticsearch: distinct sources
    try:
        agg_resp = await es.search(
            index=settings.ES_INDEX,
            body={
                "size": 0,
                "aggs": {
                    "sources": {
                        "cardinality": {"field": "source"}
                    }
                },
            },
        )
        stats["sources_count"] = (
            agg_resp.get("aggregations", {})
            .get("sources", {})
            .get("value", 0)
        )
    except Exception as exc:
        logger.warning("Could not fetch sources count: %s", exc)
        stats["sources_count"] = None

    # Qdrant: total vectors
    try:
        collection_info = qdrant.get_collection(settings.QDRANT_COLLECTION)
        stats["total_vectors"] = collection_info.vectors_count
    except Exception as exc:
        logger.warning("Could not fetch Qdrant vector count: %s", exc)
        stats["total_vectors"] = None

    return stats


# ---------------------------------------------------------------------------
# GET /api/events
# ---------------------------------------------------------------------------


@router.get("/api/events", tags=["events"])
async def get_events(
    hours: int = Query(72, ge=1, le=168, description="Look-back window in hours"),
    es: AsyncElasticsearch = Depends(get_es_client),
) -> dict:
    """Aggregate recent articles into event clusters with timelines."""
    try:
        events = await aggregate_events(es, hours=hours)
        return {
            "events": [e.model_dump() for e in events],
            "total": len(events),
            "hours": hours,
        }
    except Exception as exc:
        logger.error("Event aggregation failed: %s", exc)
        raise HTTPException(status_code=500, detail="事件聚合失败")


# ---------------------------------------------------------------------------
# GET /api/eval/run
# ---------------------------------------------------------------------------


@router.get("/api/eval/run", tags=["evaluation"])
async def run_evaluation(
    dataset_path: str = Query(
        "eval/dataset.json",
        description="Path to the evaluation dataset JSON file",
    ),
    es: AsyncElasticsearch = Depends(get_es_client),
    qdrant: QdrantClient = Depends(get_qdrant_client),
) -> dict:
    """Run offline evaluation and return the report."""
    import os

    if not os.path.exists(dataset_path):
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation dataset not found: {dataset_path}",
        )

    settings = get_settings()

    try:
        from evaluation.pipeline import load_eval_dataset, run_evaluation as _run_eval

        eval_queries = load_eval_dataset(dataset_path)

        embedding_svc = get_embedding_service()

        async def _search_fn(query: str) -> list[dict]:
            qvec = embedding_svc.get_query_embedding(query)
            results = await hybrid_search(
                es_client=es,
                qdrant_client=qdrant,
                query=query,
                query_vector=qvec,
                filters={},
                top_k=settings.MAX_SEARCH_RESULTS,
            )
            return rerank(results, query)

        report = await _run_eval(eval_queries, _search_fn)
        return report.model_dump(mode="json")

    except Exception as exc:
        logger.error("Evaluation run failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}")
