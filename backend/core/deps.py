from __future__ import annotations

import logging
from typing import AsyncGenerator

import redis.asyncio as aioredis
from elasticsearch import AsyncElasticsearch
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from .config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons (created lazily on first request)
# ---------------------------------------------------------------------------
_es_client: AsyncElasticsearch | None = None
_qdrant_client: QdrantClient | None = None
_redis_client: aioredis.Redis | None = None


# ---------------------------------------------------------------------------
# Dependency providers
# ---------------------------------------------------------------------------


async def get_es_client() -> AsyncGenerator[AsyncElasticsearch, None]:
    global _es_client
    if _es_client is None:
        settings = get_settings()
        _es_client = AsyncElasticsearch(
            hosts=[settings.ES_URL],
            request_timeout=30,
            retry_on_timeout=True,
            max_retries=3,
        )
        logger.info("Elasticsearch client created: %s", settings.ES_URL)
    yield _es_client


async def get_qdrant_client() -> AsyncGenerator[QdrantClient, None]:
    global _qdrant_client
    if _qdrant_client is None:
        settings = get_settings()
        _qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        logger.info(
            "Qdrant client created: %s:%s", settings.QDRANT_HOST, settings.QDRANT_PORT
        )
    yield _qdrant_client


async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis client created: %s", settings.REDIS_URL)
    yield _redis_client


# ---------------------------------------------------------------------------
# Convenience accessors (for code outside FastAPI's DI context, e.g. scheduler)
# ---------------------------------------------------------------------------


def get_es_client_sync() -> AsyncElasticsearch:
    global _es_client
    if _es_client is None:
        settings = get_settings()
        _es_client = AsyncElasticsearch(hosts=[settings.ES_URL])
    return _es_client


def get_qdrant_client_sync() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        settings = get_settings()
        _qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST, port=settings.QDRANT_PORT
        )
    return _qdrant_client


def get_redis_client_sync() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _redis_client


# ---------------------------------------------------------------------------
# Startup initialisation
# ---------------------------------------------------------------------------

_ES_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "title": {"type": "text", "analyzer": "standard"},
            "content": {"type": "text", "analyzer": "standard"},
            "source": {"type": "keyword"},
            "url": {"type": "keyword"},
            "published_at": {"type": "date"},
            "author": {"type": "keyword"},
            "category": {"type": "keyword"},
            "sentiment": {"type": "keyword"},
            "entities": {"type": "keyword"},  # array of keywords
            "summary": {"type": "text", "analyzer": "standard"},
            "created_at": {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
}


async def init_services() -> None:
    settings = get_settings()

    # --- Elasticsearch ---
    es = get_es_client_sync()
    try:
        exists = await es.indices.exists(index=settings.ES_INDEX)
        if not exists:
            await es.indices.create(index=settings.ES_INDEX, body=_ES_INDEX_MAPPING)
            logger.info("Created ES index '%s'", settings.ES_INDEX)
        else:
            logger.info("ES index '%s' already exists", settings.ES_INDEX)
    except Exception as exc:
        logger.error("Failed to initialise Elasticsearch: %s", exc)
        raise

    # --- Qdrant ---
    qdrant = get_qdrant_client_sync()
    try:
        existing = [c.name for c in qdrant.get_collections().collections]
        if settings.QDRANT_COLLECTION not in existing:
            qdrant.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection '%s'", settings.QDRANT_COLLECTION)
        else:
            logger.info(
                "Qdrant collection '%s' already exists", settings.QDRANT_COLLECTION
            )
    except Exception as exc:
        logger.error("Failed to initialise Qdrant: %s", exc)
        raise

    logger.info("All services initialised successfully")
