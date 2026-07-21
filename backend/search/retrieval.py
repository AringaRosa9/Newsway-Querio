"""Hybrid retrieval module.

Combines Elasticsearch BM25 full-text search with Qdrant vector search,
fusing results via Reciprocal Rank Fusion (RRF).
"""

from __future__ import annotations

import logging
from typing import Any

from elasticsearch import AsyncElasticsearch
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BM25 (Elasticsearch) search
# ---------------------------------------------------------------------------


def _build_es_filter_clauses(filters: dict) -> list[dict]:
    """Convert a flat filters dict into Elasticsearch filter clauses."""
    clauses: list[dict] = []

    time_from = filters.get("time_from")
    time_to = filters.get("time_to")
    if time_from or time_to:
        range_clause: dict[str, Any] = {"range": {"published_at": {}}}
        if time_from:
            range_clause["range"]["published_at"]["gte"] = (
                time_from.isoformat() if hasattr(time_from, "isoformat") else time_from
            )
        if time_to:
            range_clause["range"]["published_at"]["lte"] = (
                time_to.isoformat() if hasattr(time_to, "isoformat") else time_to
            )
        clauses.append(range_clause)

    for field in ("source", "category", "sentiment"):
        value = filters.get(field)
        if value:
            clauses.append({"term": {field: value}})

    return clauses


async def bm25_search(
    es_client: AsyncElasticsearch,
    query: str,
    filters: dict,
    top_k: int = 100,
) -> list[dict]:
    """Full-text BM25 search on title and content fields.

    Returns a list of dicts with at least ``id`` and ``score`` plus all
    ``_source`` fields from the document.
    """
    settings = get_settings()
    index = settings.ES_INDEX

    filter_clauses = _build_es_filter_clauses(filters)

    bool_query: dict[str, Any] = {
        "must": [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["title^2", "content"],
                    "type": "best_fields",
                    "operator": "or",
                }
            }
        ]
    }
    if filter_clauses:
        bool_query["filter"] = filter_clauses

    body = {
        "query": {"bool": bool_query},
        "size": top_k,
        "_source": True,
    }

    try:
        response = await es_client.search(index=index, body=body)
    except Exception as exc:
        logger.error("BM25 search error: %s", exc)
        return []

    results: list[dict] = []
    for hit in response.get("hits", {}).get("hits", []):
        doc = {"id": hit["_id"], "score": hit["_score"]}
        doc.update(hit.get("_source", {}))
        results.append(doc)

    logger.debug("BM25 returned %d results for query: %s", len(results), query)
    return results


# ---------------------------------------------------------------------------
# Vector (Qdrant) search
# ---------------------------------------------------------------------------


def _build_qdrant_filter(filters: dict) -> Filter | None:
    """Build a Qdrant Filter object from the filters dict."""
    conditions: list[FieldCondition] = []

    for field in ("source", "category", "sentiment"):
        value = filters.get(field)
        if value:
            conditions.append(
                FieldCondition(key=field, match=MatchValue(value=value))
            )

    time_from = filters.get("time_from")
    time_to = filters.get("time_to")
    if time_from or time_to:
        range_kwargs: dict[str, Any] = {}
        if time_from:
            ts = time_from.timestamp() if hasattr(time_from, "timestamp") else time_from
            range_kwargs["gte"] = ts
        if time_to:
            ts = time_to.timestamp() if hasattr(time_to, "timestamp") else time_to
            range_kwargs["lte"] = ts
        conditions.append(
            FieldCondition(key="published_at_ts", range=Range(**range_kwargs))
        )

    if not conditions:
        return None
    return Filter(must=conditions)


def vector_search(
    qdrant_client: QdrantClient,
    query_vector: list[float],
    filters: dict,
    top_k: int = 100,
) -> list[dict]:
    """Semantic vector search via Qdrant.

    Returns a list of dicts with ``id``, ``score``, and payload fields.
    """
    settings = get_settings()
    collection = settings.QDRANT_COLLECTION

    qdrant_filter = _build_qdrant_filter(filters)

    try:
        hits = qdrant_client.search(
            collection_name=collection,
            query_vector=query_vector,
            query_filter=qdrant_filter,
            limit=top_k,
            with_payload=True,
        )
    except Exception as exc:
        logger.error("Vector search error: %s", exc)
        return []

    results: list[dict] = []
    for hit in hits:
        doc: dict[str, Any] = {"id": str(hit.id), "score": hit.score}
        if hit.payload:
            doc.update(hit.payload)
        results.append(doc)

    logger.debug("Vector search returned %d results", len(results))
    return results


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------


def rrf_fusion(
    bm25_results: list[dict],
    vector_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """Merge two ranked lists using Reciprocal Rank Fusion.

    Each result must have an ``id`` field.  The output is deduplicated by id
    and sorted by descending fused score.

    RRF score for document d = sum over each ranking list r of 1 / (k + rank(d, r))
    """
    # Build a lookup: id -> original doc (prefer the BM25 version for data richness)
    id_to_doc: dict[str, dict] = {}
    for doc in vector_results:
        id_to_doc[doc["id"]] = doc
    for doc in bm25_results:
        id_to_doc[doc["id"]] = doc  # BM25 doc takes precedence (richer _source)

    fused_scores: dict[str, float] = {}

    for rank, doc in enumerate(bm25_results, start=1):
        doc_id = doc["id"]
        fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    for rank, doc in enumerate(vector_results, start=1):
        doc_id = doc["id"]
        fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + 1.0 / (k + rank)

    # Sort by fused score descending
    sorted_ids = sorted(fused_scores, key=lambda x: fused_scores[x], reverse=True)

    results: list[dict] = []
    for doc_id in sorted_ids:
        doc = dict(id_to_doc[doc_id])
        doc["score"] = fused_scores[doc_id]
        results.append(doc)

    return results


# ---------------------------------------------------------------------------
# Orchestration: hybrid_search
# ---------------------------------------------------------------------------


async def hybrid_search(
    es_client: AsyncElasticsearch,
    qdrant_client: QdrantClient,
    query: str,
    query_vector: list[float],
    filters: dict,
    top_k: int = 50,
) -> list[dict]:
    """Run BM25 + vector search and fuse results.

    After fusion, fetches full article data from ES for any results that
    arrived only from Qdrant (which may have incomplete payloads).

    Returns the top ``top_k`` results with full article data.
    """
    settings = get_settings()

    # Run BM25 and vector search – BM25 is async, vector is sync (Qdrant client)
    bm25_results = await bm25_search(es_client, query, filters, top_k=100)
    vec_results = vector_search(qdrant_client, query_vector, filters, top_k=100)

    # Fuse
    fused = rrf_fusion(bm25_results, vec_results)

    # Limit to top_k
    top_results = fused[:top_k]

    # Identify IDs that don't have full ES source data (came only from Qdrant)
    bm25_ids = {r["id"] for r in bm25_results}
    missing_ids = [r["id"] for r in top_results if r["id"] not in bm25_ids]

    if missing_ids:
        try:
            mget_response = await es_client.mget(
                index=settings.ES_INDEX,
                body={"ids": missing_ids},
            )
            id_to_source: dict[str, dict] = {}
            for doc in mget_response.get("docs", []):
                if doc.get("found"):
                    id_to_source[doc["_id"]] = doc.get("_source", {})

            # Enrich results that were missing full data
            for result in top_results:
                if result["id"] in id_to_source:
                    result.update(id_to_source[result["id"]])
        except Exception as exc:
            logger.warning("Failed to enrich Qdrant-only results from ES: %s", exc)

    logger.info(
        "hybrid_search: bm25=%d, vector=%d, fused=%d, returned=%d",
        len(bm25_results),
        len(vec_results),
        len(fused),
        len(top_results),
    )
    return top_results
