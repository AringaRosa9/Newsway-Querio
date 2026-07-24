"""Chat / multi-turn dialogue API routes.

Provides session-based conversational search with context tracking,
follow-up understanding, and integrated article retrieval.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from qdrant_client import QdrantClient
import redis.asyncio as aioredis

from core.config import get_settings
from core.deps import get_es_client, get_qdrant_client, get_redis_client
from auth.routes import get_current_user, require_current_user
from ai.dialogue import DialogueService
from ai.embedding import get_embedding_service
from ai.summary import SummaryService
from search.query import parse_query
from search.retrieval import hybrid_search
from search.ranking import rerank

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendMessageRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    follow_up_query: Optional[str] = None
    session_id: str
    citations: Optional[list[dict[str, Any]]] = None
    search_results: Optional[list[dict[str, Any]]] = None


def _get_dialogue_service(redis: aioredis.Redis) -> DialogueService:
    settings = get_settings()
    return DialogueService(redis_client=redis, anthropic_api_key=settings.ANTHROPIC_API_KEY)


async def _perform_search(
    query: str,
    es: AsyncElasticsearch,
    qdrant: QdrantClient,
) -> tuple[list[dict], dict]:
    settings = get_settings()
    try:
        embedding_svc = get_embedding_service()
        query_vector = embedding_svc.get_query_embedding(query)
    except Exception as exc:
        logger.error("Embedding failed for chat search: %s", exc)
        return [], {}

    parsed = parse_query(query)
    filters: dict[str, Any] = {}
    if parsed.time_range:
        filters["time_from"] = parsed.time_range[0]
        filters["time_to"] = parsed.time_range[1]

    try:
        raw = await hybrid_search(
            es_client=es,
            qdrant_client=qdrant,
            query=query,
            query_vector=query_vector,
            filters=filters,
            top_k=settings.MAX_SEARCH_RESULTS,
        )
        ranked = rerank(raw, query)
        top_results = ranked[: settings.SUMMARY_MAX_DOCS]

        summary_svc = SummaryService(api_key=settings.ANTHROPIC_API_KEY)
        summary_data = await summary_svc.generate_summary(query, top_results)

        return top_results, summary_data
    except Exception as exc:
        logger.error("Chat search failed: %s", exc)
        return [], {}


@router.post("/sessions")
async def create_session(
    redis: aioredis.Redis = Depends(get_redis_client),
    current_user: dict | None = Depends(get_current_user),
) -> dict:
    svc = _get_dialogue_service(redis)
    user_id = current_user["id"] if current_user else None
    session = await svc.create_session(user_id)
    return {"session_id": session.session_id, "created_at": session.created_at.isoformat()}


@router.get("/sessions")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    redis: aioredis.Redis = Depends(get_redis_client),
    current_user: dict | None = Depends(get_current_user),
) -> dict:
    if not current_user:
        return {"sessions": []}
    svc = _get_dialogue_service(redis)
    sessions = await svc.list_sessions(current_user["id"], limit=limit)
    return {"sessions": sessions}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    redis: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    svc = _get_dialogue_service(redis)
    session = await svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "messages": session.messages,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    redis: aioredis.Redis = Depends(get_redis_client),
) -> dict:
    svc = _get_dialogue_service(redis)
    await svc.delete_session(session_id)
    return {"status": "deleted"}


@router.post("/sessions/{session_id}/messages", response_model=ChatResponse)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    es: AsyncElasticsearch = Depends(get_es_client),
    qdrant: QdrantClient = Depends(get_qdrant_client),
    redis: aioredis.Redis = Depends(get_redis_client),
    current_user: dict | None = Depends(get_current_user),
) -> ChatResponse:
    svc = _get_dialogue_service(redis)
    session = await svc.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    search_results: list[dict] = []
    citations: list[dict] = []

    resolved_query = await svc.resolve_follow_up(session_id, body.message)

    top_results, summary_data = await _perform_search(resolved_query, es, qdrant)

    if top_results:
        search_results = [
            {
                "id": str(r.get("id", "")),
                "title": r.get("title", ""),
                "source": r.get("source", ""),
                "url": r.get("url", ""),
                "published_at": r.get("published_at", ""),
                "score": r.get("final_score"),
            }
            for r in top_results[:5]
        ]

    result = await svc.generate_response(
        session_id, body.message, search_results=top_results
    )

    if summary_data and summary_data.get("citations"):
        citations = summary_data["citations"]

    return ChatResponse(
        response=result["response"],
        follow_up_query=result.get("follow_up_query"),
        session_id=result["session_id"],
        citations=citations if citations else None,
        search_results=search_results if search_results else None,
    )
