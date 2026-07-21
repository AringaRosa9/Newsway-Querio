"""Ingestion pipeline and APScheduler integration.

Pipeline stages (in order):
  1. Fetch RSS feeds           – rss_fetcher.fetch_all_feeds()
  2. Extract full article text – cleaner.extract_article()  (optional, gated by flag)
  3. Normalise                 – cleaner.normalize_article()
  4. Deduplicate               – dedup.DedupStore.check_and_add()
  5. NLP / AI enrichment       – ai.processor.enrich_article()  (stub)
  6. Embed                     – search.embedder.embed_article()  (stub)
  7. Index to ES + Qdrant      – search.indexer.index_article()  (stub)

Stages 5-7 are thin stubs here; the real implementations live in the
ai/ and search/ packages and are imported at runtime (lazy imports) to
avoid circular dependency issues at startup.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.config import get_settings
from core.deps import get_redis_client_sync

from .cleaner import Article, extract_article, normalize_article
from .dedup import DedupStore
from .rss_fetcher import fetch_all_feeds

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pipeline statistics
# ---------------------------------------------------------------------------


@dataclass
class PipelineStats:
    fetched: int = 0
    extracted: int = 0
    normalized: int = 0
    duplicates: int = 0
    enriched: int = 0
    indexed: int = 0
    errors: int = 0

    def summary(self) -> str:
        return (
            f"fetched={self.fetched} extracted={self.extracted} "
            f"normalized={self.normalized} duplicates={self.duplicates} "
            f"enriched={self.enriched} indexed={self.indexed} errors={self.errors}"
        )


# ---------------------------------------------------------------------------
# Stub interfaces for downstream modules (replaced by real impls later)
# ---------------------------------------------------------------------------


async def _enrich_article(article: Article) -> Article:
    """NLP / AI enrichment stub.

    Replace with:  from ai.processor import enrich_article
    """
    try:
        from ai.processor import enrich_article  # type: ignore[import]

        return await enrich_article(article)
    except ImportError:
        return article


async def _embed_and_index(article: Article) -> None:
    """Embedding + ES/Qdrant indexing stub.

    Replace with the real search.indexer when it is implemented.
    """
    try:
        from search.indexer import index_article  # type: ignore[import]

        await index_article(article)
    except ImportError:
        logger.debug("search.indexer not yet available – skipping index for %s", article.url)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class IngestPipeline:
    """Orchestrates the full ingestion flow.

    Parameters
    ----------
    extract_full_text:
        If True, fetch the full article page for each RSS item.
        Slower but produces richer content.  Default False during early MVP.
    """

    def __init__(self, extract_full_text: bool = False) -> None:
        self._extract_full = extract_full_text
        self._dedup: DedupStore | None = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> PipelineStats:
        stats = PipelineStats()

        # Lazy-init dedup store (needs async Redis)
        if self._dedup is None:
            self._dedup = DedupStore(get_redis_client_sync())

        # Stage 1: Fetch
        raw_articles = await fetch_all_feeds()
        stats.fetched = len(raw_articles)
        logger.info("Pipeline stage 1 complete: %d articles fetched", stats.fetched)

        # Stages 2-7: process each article
        tasks = [self._process_one(raw, stats) for raw in raw_articles]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("Pipeline run complete – %s", stats.summary())
        return stats

    # ------------------------------------------------------------------
    # Per-article processing
    # ------------------------------------------------------------------

    async def _process_one(self, raw: dict[str, Any], stats: PipelineStats) -> None:
        try:
            # Stage 2: optional full-text extraction
            if self._extract_full and raw.get("url"):
                extracted = await extract_article(raw["url"])
                raw = {**raw, **extracted}  # merge, extracted fields take priority
                stats.extracted += 1

            # Stage 3: normalise
            article = normalize_article(raw)
            if not article.title and not article.content:
                logger.debug("Skipping empty article: %s", article.url)
                return
            stats.normalized += 1

            # Stage 4: dedup
            assert self._dedup is not None
            is_dup = await self._dedup.check_and_add(article)
            if is_dup:
                stats.duplicates += 1
                return

            # Stage 5: NLP / AI enrichment
            article = await _enrich_article(article)
            stats.enriched += 1

            # Stages 6-7: embed + index
            await _embed_and_index(article)
            stats.indexed += 1

        except Exception as exc:
            stats.errors += 1
            logger.exception("Error processing article %s: %s", raw.get("url", "?"), exc)


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


class IngestionScheduler:
    """Wraps APScheduler to run IngestPipeline on a fixed interval."""

    def __init__(self, pipeline: IngestPipeline | None = None) -> None:
        self._pipeline = pipeline or IngestPipeline()
        self._scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        settings = get_settings()
        self._scheduler.add_job(
            self._run_pipeline,
            trigger=IntervalTrigger(seconds=settings.RSS_FETCH_INTERVAL),
            id="ingest_pipeline",
            replace_existing=True,
            # Run immediately on startup, then on the interval.
            next_run_time=_now_utc(),
        )
        self._scheduler.start()
        logger.info(
            "Ingestion scheduler started (interval=%ds)", settings.RSS_FETCH_INTERVAL
        )

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("Ingestion scheduler stopped")

    async def _run_pipeline(self) -> None:
        logger.info("Ingestion pipeline triggered")
        try:
            await self._pipeline.run()
        except Exception as exc:
            logger.exception("Ingestion pipeline failed: %s", exc)


def _now_utc() -> Any:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Convenience function for manual trigger from API
# ---------------------------------------------------------------------------

_default_pipeline: IngestPipeline | None = None


async def trigger_now() -> PipelineStats:
    """Run a single ingestion cycle immediately (called from API route)."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = IngestPipeline()
    return await _default_pipeline.run()
