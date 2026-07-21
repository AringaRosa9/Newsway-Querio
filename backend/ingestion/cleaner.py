"""Article content cleaner and normaliser.

Two jobs:
1. clean_html()     – strip tags, normalise whitespace from any HTML string.
2. extract_article() – fetch the full-page HTML of a URL and pull out the
                       main article body with heuristics (score text blocks by
                       length after removing boilerplate containers).
3. normalize_article() – map a raw fetcher dict → typed Article model.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = httpx.Timeout(20.0, connect=5.0)

# Tags whose subtree we discard entirely before scoring text blocks.
_NOISE_TAGS = {
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "form", "button", "iframe", "figure", "figcaption",
    "advertisement", "sidebar",
}

# CSS class / id substrings that strongly suggest boilerplate.
_NOISE_PATTERNS = re.compile(
    r"(nav|header|footer|sidebar|menu|ad|banner|cookie|popup|modal|promo"
    r"|share|social|comment|related|recommend|subscribe|newsletter)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


class Article(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    source: str
    url: str
    published_at: str  # ISO-8601
    author: str = ""
    category: str = "general"
    sentiment: str = "neutral"
    entities: list[str] = Field(default_factory=list)
    summary: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# HTML cleaning
# ---------------------------------------------------------------------------


def clean_html(html: str) -> str:
    """Strip all HTML tags and normalise whitespace."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ")
    # Collapse runs of whitespace / newlines into a single space
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Full-article extraction
# ---------------------------------------------------------------------------


async def extract_article(url: str) -> dict[str, Any]:
    """Download a URL and return {'title': ..., 'content': ...}.

    Falls back to empty strings on any error so callers can still index
    what they have from the RSS summary.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "AI-News-Bot/1.0"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as exc:
        logger.debug("Could not fetch article %s: %s", url, exc)
        return {"title": "", "content": ""}

    return _parse_html(html)


def _parse_html(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")

    # --- Title ---
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):  # type: ignore[union-attr]
        title = str(og_title["content"]).strip()  # type: ignore[index]
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()

    # --- Remove noise subtrees ---
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        if tag.name in _NOISE_TAGS:
            tag.decompose()
            continue
        cls = " ".join(tag.get("class", []))
        eid = tag.get("id", "")
        if _NOISE_PATTERNS.search(cls) or _NOISE_PATTERNS.search(str(eid)):
            tag.decompose()

    # --- Score remaining block elements by text length ---
    best_block: Tag | None = None
    best_score = 0

    for tag in soup.find_all(["article", "main", "section", "div", "p"]):
        if not isinstance(tag, Tag):
            continue
        text = tag.get_text(separator=" ", strip=True)
        # Heuristic: favour longer blocks; penalise shallow nesting (likely wrappers)
        score = len(text) - 50 * len(list(tag.children))
        if score > best_score:
            best_score = score
            best_block = tag

    if best_block is not None:
        content = best_block.get_text(separator=" ", strip=True)
    else:
        content = soup.get_text(separator=" ", strip=True)

    # Normalise whitespace
    content = re.sub(r"\s+", " ", content).strip()

    return {"title": title, "content": content}


# ---------------------------------------------------------------------------
# Article normalisation
# ---------------------------------------------------------------------------


def normalize_article(raw: dict[str, Any]) -> Article:
    """Map a raw RSS fetcher dict (+ optional extracted content) to Article."""
    title = raw.get("title", "").strip()
    # Prefer full extracted content; fall back to RSS summary
    content = raw.get("content", "").strip() or clean_html(
        raw.get("summary", "")
    )

    return Article(
        title=title,
        content=content,
        source=raw.get("source", ""),
        url=raw.get("url", ""),
        published_at=raw.get("published", ""),
        author=raw.get("author", ""),
        category=raw.get("category", "general"),
    )
