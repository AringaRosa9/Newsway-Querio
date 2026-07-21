"""AI summary generation using the Claude API.

Synthesises a comprehensive, cited answer to a search query based on the
top retrieved articles. Uses claude-sonnet-4-20250514 via the Anthropic SDK.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

_MODEL_ID = "claude-sonnet-4-20250514"
_MAX_TOKENS = 1024

# How many chars of article content to include in the prompt (per article)
_CONTENT_SNIPPET_CHARS = 600

# Fallback response when the API call fails
_FALLBACK_SUMMARY = "Unable to generate a summary at this time. Please review the individual articles below."


def _build_prompt(query: str, articles: list[dict]) -> str:
    """Build the prompt sent to Claude."""
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

    prompt = f"""You are a knowledgeable news analyst. A user has searched for: "{query}"

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

    return prompt


def _extract_citations(articles: list[dict]) -> list[dict]:
    """Build citation objects from article metadata."""
    citations = []
    for i, article in enumerate(articles, start=1):
        citations.append(
            {
                "index": i,
                "title": article.get("title", "Untitled"),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
            }
        )
    return citations


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SummaryService:
    """Generates AI-powered search result summaries using Claude."""

    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    async def generate_summary(
        self, query: str, articles: list[dict]
    ) -> dict[str, Any]:
        """Synthesise a summary for the query based on the provided articles.

        Args:
            query: The original user search query.
            articles: List of article dicts, each with title, content, source,
                      url, and published_at fields.

        Returns:
            dict with:
              - summary_text (str): The synthesised answer.
              - citations (list[dict]): [{index, title, source, url}, ...]
              - generated_at (datetime): UTC timestamp of generation.
        """
        if not articles:
            return {
                "summary_text": "No articles found to summarise.",
                "citations": [],
                "generated_at": datetime.now(tz=timezone.utc),
            }

        prompt = _build_prompt(query, articles)

        try:
            # anthropic SDK is synchronous; wrap in asyncio if needed.
            # For FastAPI async endpoints, run sync call in thread pool.
            import asyncio

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=_MODEL_ID,
                    max_tokens=_MAX_TOKENS,
                    messages=[{"role": "user", "content": prompt}],
                ),
            )

            summary_text = response.content[0].text if response.content else _FALLBACK_SUMMARY

        except anthropic.AuthenticationError as exc:
            logger.error("Anthropic authentication error: %s", exc)
            summary_text = _FALLBACK_SUMMARY
        except anthropic.RateLimitError as exc:
            logger.warning("Anthropic rate limit hit: %s", exc)
            summary_text = _FALLBACK_SUMMARY
        except anthropic.APIError as exc:
            logger.error("Anthropic API error during summary generation: %s", exc)
            summary_text = _FALLBACK_SUMMARY
        except Exception as exc:
            logger.error("Unexpected error generating summary: %s", exc)
            summary_text = _FALLBACK_SUMMARY

        return {
            "summary_text": summary_text,
            "citations": _extract_citations(articles),
            "generated_at": datetime.now(tz=timezone.utc),
        }
