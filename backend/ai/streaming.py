"""Streaming summary generation via Server-Sent Events (SSE)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator

import anthropic

from core.config import get_settings

logger = logging.getLogger(__name__)

_MODEL_ID = "claude-sonnet-4-20250514"
_CONTENT_SNIPPET_CHARS = 600


def _build_prompt(query: str, articles: list[dict]) -> str:
    articles_block = ""
    for i, article in enumerate(articles, start=1):
        title = article.get("title", "Untitled")
        source = article.get("source", "Unknown source")
        url = article.get("url", "")
        published_at = article.get("published_at", "")
        content = (article.get("content", "") or "")[:_CONTENT_SNIPPET_CHARS]
        articles_block += (
            f"[{i}] {title}\n"
            f"Source: {source} | URL: {url} | Published: {published_at}\n"
            f"{content}\n\n"
        )

    return f"""You are a knowledgeable news analyst. A user has searched for: "{query}"

Below are the most relevant news articles retrieved for this query:

{articles_block.strip()}

Please provide a comprehensive, factual synthesis that directly answers the user's query. Follow these guidelines:

1. **Language**: Respond in the same language as the user's query.
2. **Citations**: Reference articles using [1], [2], etc. (matching the article numbers above).
3. **Accuracy**: Only include facts supported by the articles above. Do not add information not present.
4. **Multiple perspectives**: If articles present conflicting information or different viewpoints, acknowledge this explicitly.
5. **Structure**: Use clear paragraphs. If appropriate, group by subtopic.
6. **Conciseness**: Aim for a focused synthesis, not a repetition of every article.
7. **Conflicts**: Clearly note when sources disagree on key facts or figures.

Write the synthesis now:"""


async def stream_summary(
    query: str,
    articles: list[dict],
    api_key: str | None = None,
) -> AsyncGenerator[str, None]:
    if not articles:
        yield _sse_event("done", {"summary_text": "No articles found to summarise."})
        return

    key = api_key or get_settings().ANTHROPIC_API_KEY
    if not key:
        yield _sse_event("done", {"summary_text": "API key not configured."})
        return

    prompt = _build_prompt(query, articles)
    citations = [
        {
            "index": i + 1,
            "title": a.get("title", "Untitled"),
            "source": a.get("source", ""),
            "url": a.get("url", ""),
        }
        for i, a in enumerate(articles)
    ]

    yield _sse_event("citations", citations)

    try:
        client = anthropic.Anthropic(api_key=key)
        loop = asyncio.get_event_loop()

        full_text: list[str] = []

        def _stream():
            with client.messages.stream(
                model=_MODEL_ID,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield text

        chunks = await loop.run_in_executor(None, lambda: list(_stream()))

        for chunk in chunks:
            full_text.append(chunk)
            yield _sse_event("chunk", {"text": chunk})

        yield _sse_event("done", {
            "summary_text": "".join(full_text),
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        })

    except Exception as exc:
        logger.error("Streaming summary error: %s", exc)
        yield _sse_event("error", {"message": "Summary generation failed."})


def _sse_event(event_type: str, data: Any) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
