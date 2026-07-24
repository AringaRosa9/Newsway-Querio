from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from core.deps import get_redis_client_sync

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key prefixes
# ---------------------------------------------------------------------------
_PREFIX_SEARCH = "cache:search:"
_PREFIX_SUMMARY = "cache:summary:"
_PREFIX_HITS = "cache_hits:"
_PREFIX_MISSES = "cache_misses:"


class CacheService:
    """Redis-backed cache for search results and AI-generated summaries."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    # ------------------------------------------------------------------
    # Key generation
    # ------------------------------------------------------------------

    def _make_search_key(self, query: str, filters: dict) -> str:
        """Deterministic cache key for a search query + filter combination."""
        normalized_query = query.lower().strip()
        # Sort filter items so key is order-independent
        canonical = json.dumps(
            {"q": normalized_query, "f": dict(sorted(filters.items()))},
            sort_keys=True,
            ensure_ascii=False,
        )
        digest = hashlib.md5(canonical.encode("utf-8")).hexdigest()
        return f"{_PREFIX_SEARCH}{digest}"

    def _make_summary_key(self, query: str, article_ids: list[str]) -> str:
        """Deterministic cache key for an AI summary over a set of articles."""
        normalized_query = query.lower().strip()
        canonical = json.dumps(
            {"q": normalized_query, "ids": sorted(article_ids)},
            sort_keys=True,
            ensure_ascii=False,
        )
        digest = hashlib.md5(canonical.encode("utf-8")).hexdigest()
        return f"{_PREFIX_SUMMARY}{digest}"

    # ------------------------------------------------------------------
    # Search result caching
    # ------------------------------------------------------------------

    async def get_cached_results(self, query: str, filters: dict) -> dict | None:
        """Return cached search results, or None on a miss."""
        key = self._make_search_key(query, filters)
        try:
            raw = await self._redis.get(key)
            if raw is None:
                await self.record_miss("search")
                logger.debug("Cache miss  [search] key=%s", key)
                return None
            await self.record_hit("search")
            logger.debug("Cache hit   [search] key=%s", key)
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Cache read error [search] key=%s: %s", key, exc)
            return None

    async def cache_results(
        self,
        query: str,
        filters: dict,
        results: dict,
        ttl: int = 300,
    ) -> None:
        """Store search results in Redis for *ttl* seconds (default 5 min)."""
        key = self._make_search_key(query, filters)
        try:
            await self._redis.setex(key, ttl, json.dumps(results, ensure_ascii=False))
            logger.debug("Cached      [search] key=%s ttl=%ds", key, ttl)
        except Exception as exc:
            logger.warning("Cache write error [search] key=%s: %s", key, exc)

    # ------------------------------------------------------------------
    # Summary caching (the main cost saver — Claude API calls are expensive)
    # ------------------------------------------------------------------

    async def get_cached_summary(
        self, query: str, article_ids: list[str]
    ) -> dict | None:
        """Return a cached AI summary, or None on a miss."""
        key = self._make_summary_key(query, article_ids)
        try:
            raw = await self._redis.get(key)
            if raw is None:
                await self.record_miss("summary")
                logger.debug("Cache miss  [summary] key=%s", key)
                return None
            await self.record_hit("summary")
            logger.debug("Cache hit   [summary] key=%s", key)
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Cache read error [summary] key=%s: %s", key, exc)
            return None

    async def cache_summary(
        self,
        query: str,
        article_ids: list[str],
        summary: dict,
        ttl: int = 1800,
    ) -> None:
        """Store an AI summary in Redis for *ttl* seconds (default 30 min)."""
        key = self._make_summary_key(query, article_ids)
        try:
            await self._redis.setex(key, ttl, json.dumps(summary, ensure_ascii=False))
            logger.debug("Cached      [summary] key=%s ttl=%ds", key, ttl)
        except Exception as exc:
            logger.warning("Cache write error [summary] key=%s: %s", key, exc)

    # ------------------------------------------------------------------
    # Cache invalidation
    # ------------------------------------------------------------------

    async def invalidate_query(self, query: str) -> int:
        """Delete all cache entries whose key embeds *query*.

        Because keys are MD5 hashes we cannot query by query text directly,
        so this method performs a full scan of ``cache:search:*`` and
        ``cache:summary:*`` keys and compares the stored payload's ``q``
        field against the normalised query.  This is O(n) in the number of
        cached entries and is intended for maintenance / admin use only.

        Returns the number of keys deleted.
        """
        normalized = query.lower().strip()
        deleted = 0
        patterns = [f"{_PREFIX_SEARCH}*", f"{_PREFIX_SUMMARY}*"]

        try:
            for pattern in patterns:
                async for key in self._redis.scan_iter(match=pattern, count=100):
                    try:
                        raw = await self._redis.get(key)
                        if raw is None:
                            continue
                        payload = json.loads(raw)
                        if payload.get("q") == normalized or payload.get(
                            "query"
                        ) == normalized:
                            await self._redis.delete(key)
                            deleted += 1
                    except Exception as inner_exc:
                        logger.debug(
                            "Skipping key %s during invalidation: %s", key, inner_exc
                        )
        except Exception as exc:
            logger.warning("invalidate_query error for %r: %s", query, exc)

        logger.info("invalidate_query(%r): deleted %d key(s)", query, deleted)
        return deleted

    async def invalidate_all(self) -> int:
        """Delete every cache entry under the ``cache:*`` namespace.

        Returns the number of keys deleted.
        """
        deleted = 0
        try:
            async for key in self._redis.scan_iter(match="cache:*", count=100):
                await self._redis.delete(key)
                deleted += 1
        except Exception as exc:
            logger.warning("invalidate_all error: %s", exc)

        logger.info("invalidate_all: deleted %d key(s)", deleted)
        return deleted

    # ------------------------------------------------------------------
    # Cache metrics
    # ------------------------------------------------------------------

    async def record_hit(self, cache_type: str) -> None:
        """Increment the Redis hit counter for *cache_type*."""
        try:
            await self._redis.incr(f"{_PREFIX_HITS}{cache_type}")
        except Exception as exc:
            logger.debug("record_hit error [%s]: %s", cache_type, exc)

    async def record_miss(self, cache_type: str) -> None:
        """Increment the Redis miss counter for *cache_type*."""
        try:
            await self._redis.incr(f"{_PREFIX_MISSES}{cache_type}")
        except Exception as exc:
            logger.debug("record_miss error [%s]: %s", cache_type, exc)

    async def get_stats(self) -> dict[str, Any]:
        """Return hit/miss counts and hit rate for each tracked cache type.

        Example return value::

            {
                "search":  {"hits": 42, "misses": 8,  "hit_rate": 0.84},
                "summary": {"hits": 17, "misses": 3,  "hit_rate": 0.85},
            }
        """
        stats: dict[str, Any] = {}
        try:
            # Discover all tracked cache types by scanning counter keys
            hit_keys: list[str] = []
            async for key in self._redis.scan_iter(
                match=f"{_PREFIX_HITS}*", count=100
            ):
                hit_keys.append(key)

            for hit_key in hit_keys:
                cache_type = hit_key[len(_PREFIX_HITS):]
                miss_key = f"{_PREFIX_MISSES}{cache_type}"

                hits_raw = await self._redis.get(hit_key)
                misses_raw = await self._redis.get(miss_key)

                hits = int(hits_raw) if hits_raw is not None else 0
                misses = int(misses_raw) if misses_raw is not None else 0
                total = hits + misses
                hit_rate = round(hits / total, 4) if total > 0 else 0.0

                stats[cache_type] = {
                    "hits": hits,
                    "misses": misses,
                    "hit_rate": hit_rate,
                }
        except Exception as exc:
            logger.warning("get_stats error: %s", exc)

        return stats


# ---------------------------------------------------------------------------
# Module-level factory
# ---------------------------------------------------------------------------


def get_cache_service() -> CacheService:
    """Create a :class:`CacheService` backed by the shared sync Redis client."""
    return CacheService(get_redis_client_sync())
