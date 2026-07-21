"""Async RSS feed fetcher.

Uses httpx to download raw feed bytes (feedparser is synchronous but
fast for parsing), then parses with feedparser in a thread pool to avoid
blocking the event loop on large feeds.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from .sources import NEWS_SOURCES, NewsSource

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_MAX_CONCURRENT = 10  # guard against thundering-herd on startup


RawArticle = dict[str, Any]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fetch_feed(source: NewsSource) -> list[RawArticle]:
    """Download and parse a single RSS source.

    Returns a (possibly empty) list of raw article dicts.  Never raises –
    errors are logged and an empty list is returned so one bad feed doesn't
    abort the whole pipeline.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "AI-News-Bot/1.0"},
        ) as client:
            resp = await client.get(source["url"])
            resp.raise_for_status()
            raw_bytes = resp.content

        # feedparser is CPU-bound / blocking; run in thread pool
        parsed = await asyncio.to_thread(feedparser.parse, raw_bytes)

        articles: list[RawArticle] = []
        seen_urls: set[str] = set()

        for entry in parsed.entries:
            url = _get_field(entry, "link", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            articles.append(
                {
                    "title": _get_field(entry, "title", ""),
                    "url": url,
                    "summary": _get_field(entry, "summary", ""),
                    "published": _parse_date(entry),
                    "author": _get_field(entry, "author", ""),
                    "source": source["name"],
                    "category": source["category"],
                    "language": source["language"],
                }
            )

        logger.debug("Fetched %d articles from '%s'", len(articles), source["name"])
        return articles

    except Exception as exc:
        logger.warning("Failed to fetch feed '%s': %s", source["name"], exc)
        return []


async def fetch_all_feeds(
    sources: list[NewsSource] | None = None,
) -> list[RawArticle]:
    """Fetch all configured RSS sources concurrently.

    Uses a semaphore so we never open more than _MAX_CONCURRENT connections
    at once.  Results from all sources are merged into a single list with
    URL-level deduplication applied across sources.
    """
    if sources is None:
        sources = NEWS_SOURCES

    sem = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _bounded_fetch(src: NewsSource) -> list[RawArticle]:
        async with sem:
            return await fetch_feed(src)

    results = await asyncio.gather(*[_bounded_fetch(s) for s in sources])

    # Cross-source URL deduplication
    merged: list[RawArticle] = []
    global_seen: set[str] = set()
    for batch in results:
        for article in batch:
            url = article.get("url", "")
            if url and url not in global_seen:
                global_seen.add(url)
                merged.append(article)

    logger.info(
        "Fetched %d unique articles from %d sources", len(merged), len(sources)
    )
    return merged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_field(entry: Any, field: str, default: str = "") -> str:
    value = getattr(entry, field, None)
    if value is None:
        value = entry.get(field, default) if hasattr(entry, "get") else default
    return str(value).strip() if value else default


def _parse_date(entry: Any) -> str:
    """Return an ISO-8601 UTC timestamp or empty string if unparseable."""
    # feedparser provides a parsed 9-tuple in published_parsed / updated_parsed
    for attr in ("published_parsed", "updated_parsed"):
        timetuple = getattr(entry, attr, None)
        if timetuple:
            try:
                dt = datetime(*timetuple[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except Exception:
                pass

    # Fall back to raw string (RFC-2822 or similar)
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                return dt.astimezone(timezone.utc).isoformat()
            except Exception:
                pass

    return ""
