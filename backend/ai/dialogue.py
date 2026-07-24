"""Multi-turn dialogue engine for AI news search conversations.

Persists conversation sessions in Redis and uses Claude to generate
contextually-aware responses that understand follow-up questions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import anthropic
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_MODEL_ID = "claude-sonnet-4-20250514"
_MAX_TOKENS = 1024
_SESSION_TTL_SECONDS = 86400  # 24 hours
_MAX_HISTORY_MESSAGES = 20
_CONTENT_SNIPPET_CHARS = 400
_SESSION_KEY_PREFIX = "dialogue:"
_INDEX_KEY_PREFIX = "dialogue_index:"

_SYSTEM_PROMPT = """\
You are a helpful AI news search assistant. You help users find and understand recent news articles.

Guidelines:
- Use the conversation history to understand the full context of follow-up questions.
- When the user asks a question that requires fetching new articles (e.g., "tell me more about X", \
"what happened with Y", "show me news about Z"), output a JSON marker on the very first line of \
your response in this exact format, followed by a newline, then your answer:
  {"needs_search": true, "query": "your resolved search query here"}
- If the user's question can be answered from the current conversation context and articles already \
provided, do NOT output the JSON marker.
- Always respond in the same language the user is writing in.
- Be concise, factual, and cite article sources when referencing specific claims.
- If search results are provided in the context, use them to ground your answer.
"""

_NEEDS_SEARCH_RE = re.compile(
    r'^\s*(\{"needs_search"\s*:\s*true\s*,\s*"query"\s*:\s*"[^"]*"\})',
    re.MULTILINE,
)


@dataclass
class ConversationSession:
    session_id: str
    user_id: str | None
    messages: list[dict]
    search_context: list[dict]
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> ConversationSession:
        data = dict(data)
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


def _build_context_block(search_context: list[dict]) -> str:
    if not search_context:
        return ""
    lines = ["## Articles available in this conversation\n"]
    for i, article in enumerate(search_context[-10:], start=1):
        title = article.get("title", "Untitled")
        source = article.get("source", "")
        url = article.get("url", "")
        published_at = article.get("published_at", "")
        snippet = (article.get("content", "") or "")[:_CONTENT_SNIPPET_CHARS]
        lines.append(
            f"[{i}] {title}\n"
            f"Source: {source} | URL: {url} | Published: {published_at}\n"
            f"{snippet}\n"
        )
    return "\n".join(lines)


def _build_api_messages(session: ConversationSession) -> list[dict]:
    """Return the last N messages trimmed to context window budget."""
    return session.messages[-_MAX_HISTORY_MESSAGES:]


def _extract_needs_search(response_text: str) -> tuple[str | None, str]:
    """Parse optional JSON marker from the start of Claude's response.

    Returns (query_or_None, cleaned_response_text).
    """
    match = _NEEDS_SEARCH_RE.match(response_text)
    if not match:
        return None, response_text

    try:
        marker = json.loads(match.group(1))
        query = marker.get("query") or None
    except json.JSONDecodeError:
        return None, response_text

    cleaned = response_text[match.end():].lstrip("\n")
    return query, cleaned


class DialogueService:
    """Manages multi-turn conversations for the news search assistant."""

    def __init__(self, redis_client: aioredis.Redis, anthropic_api_key: str) -> None:
        self._redis = redis_client
        self._anthropic = anthropic.Anthropic(api_key=anthropic_api_key)

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------

    def _session_key(self, session_id: str) -> str:
        return f"{_SESSION_KEY_PREFIX}{session_id}"

    def _index_key(self, user_id: str) -> str:
        return f"{_INDEX_KEY_PREFIX}{user_id}"

    async def _save_session(self, session: ConversationSession) -> None:
        key = self._session_key(session.session_id)
        await self._redis.setex(key, _SESSION_TTL_SECONDS, json.dumps(session.to_dict()))

    async def create_session(self, user_id: str | None = None) -> ConversationSession:
        now = datetime.now(tz=timezone.utc)
        session = ConversationSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            messages=[],
            search_context=[],
            created_at=now,
            updated_at=now,
        )
        await self._save_session(session)

        if user_id:
            index_key = self._index_key(user_id)
            await self._redis.zadd(
                index_key, {session.session_id: now.timestamp()}
            )
            await self._redis.expire(index_key, _SESSION_TTL_SECONDS * 7)

        logger.debug("Created dialogue session %s for user %s", session.session_id, user_id)
        return session

    async def get_session(self, session_id: str) -> ConversationSession | None:
        raw = await self._redis.get(self._session_key(session_id))
        if raw is None:
            return None
        try:
            return ConversationSession.from_dict(json.loads(raw))
        except Exception as exc:
            logger.error("Failed to deserialise session %s: %s", session_id, exc)
            return None

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        search_results: list[dict] | None = None,
    ) -> None:
        session = await self.get_session(session_id)
        if session is None:
            logger.warning("add_message called on unknown session %s", session_id)
            return

        session.messages.append({"role": role, "content": content})

        if search_results:
            seen_urls = {a.get("url") for a in session.search_context}
            for article in search_results:
                if article.get("url") not in seen_urls:
                    session.search_context.append(article)
                    seen_urls.add(article.get("url"))

        session.updated_at = datetime.now(tz=timezone.utc)
        await self._save_session(session)

    async def delete_session(self, session_id: str) -> None:
        session = await self.get_session(session_id)
        await self._redis.delete(self._session_key(session_id))
        if session and session.user_id:
            await self._redis.zrem(self._index_key(session.user_id), session_id)
        logger.debug("Deleted dialogue session %s", session_id)

    async def list_sessions(self, user_id: str, limit: int = 20) -> list[dict]:
        index_key = self._index_key(user_id)
        # Fetch most-recent first (highest score = most recent timestamp)
        session_ids: list[str] = await self._redis.zrevrange(index_key, 0, limit - 1)

        results: list[dict] = []
        for sid in session_ids:
            session = await self.get_session(sid)
            if session is None:
                await self._redis.zrem(index_key, sid)
                continue
            results.append(
                {
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "message_count": len(session.messages),
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "preview": _session_preview(session),
                }
            )
        return results

    # ------------------------------------------------------------------
    # Claude integration
    # ------------------------------------------------------------------

    def _call_claude(
        self, messages: list[dict], system: str
    ) -> anthropic.types.Message:
        return self._anthropic.messages.create(
            model=_MODEL_ID,
            max_tokens=_MAX_TOKENS,
            system=system,
            messages=messages,
        )

    async def generate_response(
        self,
        session_id: str,
        user_message: str,
        search_results: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Generate a contextual assistant response and persist both turns.

        Returns:
            {
                "response": str,
                "follow_up_query": str | None,
                "session_id": str,
            }
        """
        session = await self.get_session(session_id)
        if session is None:
            session = await self.create_session(user_id=None)
            logger.warning(
                "Session %s not found; created new session %s",
                session_id,
                session.session_id,
            )

        await self.add_message(
            session.session_id, "user", user_message, search_results
        )
        session = await self.get_session(session.session_id)
        assert session is not None

        context_block = _build_context_block(session.search_context)
        system = _SYSTEM_PROMPT
        if context_block:
            system = f"{_SYSTEM_PROMPT}\n\n{context_block}"

        api_messages = _build_api_messages(session)

        try:
            loop = asyncio.get_event_loop()
            api_response = await loop.run_in_executor(
                None,
                lambda: self._call_claude(api_messages, system),
            )
            raw_text: str = (
                api_response.content[0].text if api_response.content else ""
            )
        except anthropic.AuthenticationError as exc:
            logger.error("Anthropic auth error in dialogue: %s", exc)
            raw_text = "I'm sorry, I'm unable to respond right now due to an authentication error."
        except anthropic.RateLimitError as exc:
            logger.warning("Anthropic rate limit in dialogue: %s", exc)
            raw_text = "I'm currently experiencing high demand. Please try again in a moment."
        except anthropic.APIError as exc:
            logger.error("Anthropic API error in dialogue: %s", exc)
            raw_text = "An error occurred while generating a response. Please try again."
        except Exception as exc:
            logger.error("Unexpected error in dialogue generate_response: %s", exc)
            raw_text = "An unexpected error occurred. Please try again."

        follow_up_query, response_text = _extract_needs_search(raw_text)

        await self.add_message(session.session_id, "assistant", response_text)

        return {
            "response": response_text,
            "follow_up_query": follow_up_query,
            "session_id": session.session_id,
        }

    async def resolve_follow_up(self, session_id: str, user_message: str) -> str:
        """Resolve an ambiguous follow-up into a standalone search query.

        Uses conversation context to rewrite the message so it can be used
        as a search query without implicit reference to prior turns.
        """
        session = await self.get_session(session_id)
        if session is None:
            return user_message

        history_snippet = _format_history_snippet(session.messages)
        resolution_prompt = (
            f"Given this conversation history:\n{history_snippet}\n\n"
            f"The user just said: \"{user_message}\"\n\n"
            "Rewrite the user's message as a complete, self-contained news search query "
            "that captures their intent without relying on the conversation context. "
            "Output only the rewritten query string, nothing else."
        )

        try:
            loop = asyncio.get_event_loop()
            api_response = await loop.run_in_executor(
                None,
                lambda: self._anthropic.messages.create(
                    model=_MODEL_ID,
                    max_tokens=128,
                    messages=[{"role": "user", "content": resolution_prompt}],
                ),
            )
            resolved = (
                api_response.content[0].text.strip() if api_response.content else user_message
            )
            logger.debug(
                "Resolved follow-up '%s' -> '%s' for session %s",
                user_message,
                resolved,
                session_id,
            )
            return resolved
        except Exception as exc:
            logger.error("Failed to resolve follow-up query: %s", exc)
            return user_message


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _session_preview(session: ConversationSession) -> str:
    """Return a short preview string from the first user message."""
    for msg in session.messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            return content[:80] + ("…" if len(content) > 80 else "")
    return ""


def _format_history_snippet(messages: list[dict], max_turns: int = 6) -> str:
    """Format the last few conversation turns as plain text."""
    recent = messages[-max_turns * 2:]
    lines = []
    for msg in recent:
        role = msg.get("role", "unknown").capitalize()
        content = (msg.get("content", "") or "")[:200]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)
