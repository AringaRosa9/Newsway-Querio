#!/usr/bin/env python3
"""
seed_data.py — Populate Elasticsearch and Qdrant with initial news articles.

Usage (from the project root, with .venv active):
    python scripts/seed_data.py

The script fetches a handful of reliable RSS feeds, indexes each article into
Elasticsearch for full-text search and into Qdrant for semantic/vector search.
It leverages the backend modules so that the same field normalisation and
embedding logic used in production is applied to the seed data as well.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Make sure the backend package is importable when the script is run from the
# project root (i.e. python scripts/seed_data.py).
# ---------------------------------------------------------------------------
_BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import feedparser  # noqa: E402 — available in requirements.txt
from bs4 import BeautifulSoup  # noqa: E402
from elasticsearch import AsyncElasticsearch  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.models import Distance, PointStruct, VectorParams  # noqa: E402
from sentence_transformers import SentenceTransformer  # noqa: E402

from core.config import get_settings  # noqa: E402

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed RSS sources — chosen for stability and public availability
# ---------------------------------------------------------------------------
SEED_SOURCES = [
    {
        "name": "BBC News",
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "category": "general",
        "language": "en",
    },
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "tech",
        "language": "en",
    },
    {
        "name": "Hacker News (frontpage)",
        "url": "https://hnrss.org/frontpage",
        "category": "tech",
        "language": "en",
    },
    {
        "name": "NPR News",
        "url": "https://feeds.npr.org/1001/rss.xml",
        "category": "general",
        "language": "en",
    },
    {
        "name": "少数派 (SSPAI)",
        "url": "https://sspai.com/feed",
        "category": "tech",
        "language": "zh",
    },
]

# Maximum articles to index per source to keep the seed run fast
MAX_PER_SOURCE = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_html(raw: str) -> str:
    """Strip HTML tags and normalise whitespace."""
    if not raw:
        return ""
    text = BeautifulSoup(raw, "lxml").get_text(separator=" ")
    return " ".join(text.split())


def _doc_id(url: str) -> str:
    """Stable, URL-derived document ID."""
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def _parse_published(entry: Any) -> str:
    """Return an ISO-8601 datetime string from a feedparser entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat()


def _fetch_feed(source: dict) -> list[dict]:
    """Fetch and parse a single RSS feed, returning normalised article dicts."""
    logger.info("Fetching %s …", source["name"])
    try:
        feed = feedparser.parse(source["url"])
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", source["name"], exc)
        return []

    articles: list[dict] = []
    for entry in feed.entries[:MAX_PER_SOURCE]:
        url = getattr(entry, "link", "") or ""
        if not url:
            continue

        title = _clean_html(getattr(entry, "title", "") or "")
        summary = _clean_html(
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        content = _clean_html(
            getattr(entry, "content", [{}])[0].get("value", "") or summary
        )

        articles.append(
            {
                "id": _doc_id(url),
                "title": title,
                "content": content or summary,
                "summary": summary,
                "source": source["name"],
                "url": url,
                "category": source["category"],
                "language": source["language"],
                "published_at": _parse_published(entry),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "author": getattr(entry, "author", "") or "",
                "entities": [],
                "sentiment": "neutral",
            }
        )

    logger.info("  → %d articles from %s", len(articles), source["name"])
    return articles


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

async def _ensure_es_index(es: AsyncElasticsearch, index: str) -> None:
    exists = await es.indices.exists(index=index)
    if not exists:
        mapping = {
            "mappings": {
                "properties": {
                    "title": {"type": "text", "analyzer": "standard"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "summary": {"type": "text", "analyzer": "standard"},
                    "source": {"type": "keyword"},
                    "url": {"type": "keyword"},
                    "published_at": {"type": "date"},
                    "author": {"type": "keyword"},
                    "category": {"type": "keyword"},
                    "language": {"type": "keyword"},
                    "sentiment": {"type": "keyword"},
                    "entities": {"type": "keyword"},
                    "created_at": {"type": "date"},
                }
            },
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        }
        await es.indices.create(index=index, body=mapping)
        logger.info("Created ES index '%s'", index)


def _ensure_qdrant_collection(qdrant: QdrantClient, collection: str, dim: int) -> None:
    existing = [c.name for c in qdrant.get_collections().collections]
    if collection not in existing:
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s' (dim=%d)", collection, dim)


async def _index_articles(
    articles: list[dict],
    es: AsyncElasticsearch,
    qdrant: QdrantClient,
    model: SentenceTransformer,
    es_index: str,
    qdrant_collection: str,
) -> tuple[int, int]:
    """Index articles into ES and Qdrant. Returns (es_count, qdrant_count)."""
    if not articles:
        return 0, 0

    # --- Elasticsearch ---
    es_ok = 0
    for art in articles:
        doc_id = art["id"]
        body = {k: v for k, v in art.items() if k != "id"}
        try:
            await es.index(index=es_index, id=doc_id, document=body)
            es_ok += 1
        except Exception as exc:
            logger.warning("ES index failed for %s: %s", art["url"], exc)

    # --- Qdrant (batch) ---
    texts = [f"{a['title']} {a['content'][:512]}" for a in articles]
    logger.info("  Encoding %d texts for embeddings …", len(texts))
    t0 = time.time()
    vectors = model.encode(texts, show_progress_bar=False, batch_size=8)
    logger.info("  Encoding took %.1fs", time.time() - t0)

    points = []
    for art, vec in zip(articles, vectors):
        points.append(
            PointStruct(
                id=int(art["id"][:8], 16),  # use first 8 hex chars as uint64
                vector=vec.tolist(),
                payload={
                    "doc_id": art["id"],
                    "title": art["title"],
                    "source": art["source"],
                    "url": art["url"],
                    "category": art["category"],
                    "language": art["language"],
                    "published_at": art["published_at"],
                },
            )
        )

    qdrant_ok = 0
    try:
        qdrant.upsert(collection_name=qdrant_collection, points=points)
        qdrant_ok = len(points)
    except Exception as exc:
        logger.warning("Qdrant upsert failed: %s", exc)

    return es_ok, qdrant_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("AI News Search — Seed Data")
    logger.info("=" * 60)
    logger.info("ES_URL             : %s", settings.ES_URL)
    logger.info("ES_INDEX           : %s", settings.ES_INDEX)
    logger.info("QDRANT_HOST        : %s:%s", settings.QDRANT_HOST, settings.QDRANT_PORT)
    logger.info("QDRANT_COLLECTION  : %s", settings.QDRANT_COLLECTION)
    logger.info("EMBEDDING_MODEL    : %s", settings.EMBEDDING_MODEL)
    logger.info("=" * 60)

    # 1. Load embedding model
    logger.info("Loading embedding model '%s' …", settings.EMBEDDING_MODEL)
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    actual_dim = model.get_sentence_embedding_dimension()
    logger.info("Model loaded. Embedding dim = %d", actual_dim)

    # 2. Connect to services
    es = AsyncElasticsearch(
        hosts=[settings.ES_URL],
        request_timeout=30,
        retry_on_timeout=True,
        max_retries=3,
    )
    qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

    try:
        await _ensure_es_index(es, settings.ES_INDEX)
        _ensure_qdrant_collection(qdrant, settings.QDRANT_COLLECTION, actual_dim)

        # 3. Fetch feeds
        all_articles: list[dict] = []
        for source in SEED_SOURCES:
            articles = _fetch_feed(source)
            all_articles.extend(articles)

        logger.info("Total articles fetched: %d", len(all_articles))

        if not all_articles:
            logger.warning(
                "No articles fetched. Check your network connection and try again."
            )
            return

        # 4. Index
        logger.info("Indexing articles into Elasticsearch and Qdrant …")
        es_total = qdrant_total = 0
        # Process in chunks to avoid OOM on large embedding batches
        chunk_size = 20
        for i in range(0, len(all_articles), chunk_size):
            chunk = all_articles[i : i + chunk_size]
            es_n, q_n = await _index_articles(
                chunk,
                es,
                qdrant,
                model,
                settings.ES_INDEX,
                settings.QDRANT_COLLECTION,
            )
            es_total += es_n
            qdrant_total += q_n
            logger.info(
                "  Chunk %d/%d → ES: %d, Qdrant: %d",
                i // chunk_size + 1,
                (len(all_articles) + chunk_size - 1) // chunk_size,
                es_n,
                q_n,
            )

        # Refresh ES so documents are immediately searchable
        await es.indices.refresh(index=settings.ES_INDEX)

    finally:
        await es.close()

    # 5. Summary
    logger.info("=" * 60)
    logger.info("Seed complete!")
    logger.info("  Articles fetched  : %d", len(all_articles))
    logger.info("  Indexed in ES     : %d", es_total)
    logger.info("  Indexed in Qdrant : %d", qdrant_total)
    logger.info("")
    logger.info("Test the API:")
    logger.info('  curl "http://localhost:8000/api/v1/status"')
    logger.info('  curl "http://localhost:9200/%s/_count"', settings.ES_INDEX)
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
