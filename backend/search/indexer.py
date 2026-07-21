"""Article indexing to Elasticsearch and Qdrant."""

from __future__ import annotations

import logging

from core.config import get_settings
from core.deps import get_es_client_sync, get_qdrant_client_sync

logger = logging.getLogger(__name__)


async def index_article(article) -> None:
    """Index a single article into ES and Qdrant.

    Embeds the article, then writes to both stores.
    """
    settings = get_settings()
    es = get_es_client_sync()
    qdrant = get_qdrant_client_sync()

    article_dict = article.model_dump()
    doc_id = str(article_dict.pop("id"))

    # Index to Elasticsearch
    try:
        await es.index(
            index=settings.ES_INDEX,
            id=doc_id,
            document=article_dict,
        )
    except Exception as exc:
        logger.error("ES indexing failed for %s: %s", doc_id, exc)
        raise

    # Embed and index to Qdrant
    try:
        from ai.embedding import get_embedding_service

        embedding_svc = get_embedding_service()
        vector = embedding_svc.get_document_embedding(
            article_dict.get("title", ""),
            article_dict.get("content", ""),
        )

        from qdrant_client.models import PointStruct

        qdrant.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=[
                PointStruct(
                    id=doc_id,
                    vector=vector,
                    payload={
                        "title": article_dict.get("title", ""),
                        "source": article_dict.get("source", ""),
                        "category": article_dict.get("category", ""),
                        "sentiment": article_dict.get("sentiment", ""),
                        "published_at": article_dict.get("published_at", ""),
                    },
                )
            ],
        )
    except Exception as exc:
        logger.error("Qdrant indexing failed for %s: %s", doc_id, exc)
        raise

    logger.debug("Indexed article %s", doc_id)
