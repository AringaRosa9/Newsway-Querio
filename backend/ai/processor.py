"""Article enrichment processor.

Bridges the ingestion pipeline with NLP analysis functions.
"""

from __future__ import annotations

import asyncio
import logging

from .nlp import process_article as _nlp_process

logger = logging.getLogger(__name__)


async def enrich_article(article):
    """Run NLP enrichment (classification, sentiment, entity extraction).

    Accepts an Article pydantic model, returns a copy with enriched fields.
    """
    try:
        article_dict = article.model_dump()
        text = f"{article_dict.get('title', '')} {article_dict.get('content', '')}"
        enriched = _nlp_process(article_dict)

        article.category = enriched.get("category", article.category)
        article.sentiment = enriched.get("sentiment", article.sentiment)
        article.entities = enriched.get("entities", article.entities)

    except Exception as exc:
        logger.warning("NLP enrichment failed for %s: %s", article.url, exc)

    return article
