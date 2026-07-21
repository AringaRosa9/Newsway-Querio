"""Near-duplicate detection for ingested articles.

Two layers:
  1. Exact URL deduplication – cheapest check, done first.
  2. Content SimHash – catches reposts / near-identical articles with
     different URLs (syndicated content, mirror sites, etc.).

Redis keys:
  dedup:url:<sha256 of url>   → "1"   (SET with TTL)
  dedup:simhash:<hash_int>    → "1"   (SET with TTL)

A simhash collision is detected by comparing the integer fingerprint of the
new article against all stored hashes whose hamming distance is ≤ threshold.
We store hashes in a Redis sorted set keyed by the hash value and use a
brute-force scan – acceptable at news-feed scale (<100k articles / day).
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict

import redis.asyncio as aioredis

from .cleaner import Article

logger = logging.getLogger(__name__)

_URL_KEY_PREFIX = "dedup:url:"
_SIMHASH_ZSET = "dedup:simhashes"
_TTL_SECONDS = 60 * 60 * 24 * 7  # keep fingerprints for 7 days


# ---------------------------------------------------------------------------
# Low-level fingerprint functions (pure, no I/O)
# ---------------------------------------------------------------------------


def compute_simhash(text: str, hashbits: int = 64) -> int:
    """Return a 64-bit SimHash integer fingerprint for *text*.

    Pure Python implementation: tokenize into shingles, hash each,
    then combine via a weighted bit vector.
    """
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return 0
    v = [0] * hashbits
    for token in tokens:
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        for i in range(hashbits):
            bitmask = 1 << i
            if h & bitmask:
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(hashbits):
        if v[i] > 0:
            fingerprint |= 1 << i
    return fingerprint


def hamming_distance(a: int, b: int) -> int:
    """Compute the number of differing bits between two 64-bit integers."""
    x = a ^ b
    # Brian Kernighan's bit-count
    count = 0
    while x:
        x &= x - 1
        count += 1
    return count


def is_duplicate(new_hash: int, existing_hashes: set[int], threshold: int = 3) -> bool:
    """Return True if *new_hash* is within *threshold* bits of any existing hash."""
    return any(hamming_distance(new_hash, h) <= threshold for h in existing_hashes)


# ---------------------------------------------------------------------------
# Redis-backed store
# ---------------------------------------------------------------------------


class DedupStore:
    """Stateful deduplication store backed by Redis.

    Usage::

        store = DedupStore(redis_client)
        is_dup = await store.check_and_add(article)
    """

    def __init__(self, redis: aioredis.Redis, simhash_threshold: int = 3) -> None:
        self._redis = redis
        self._threshold = simhash_threshold

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def check_and_add(self, article: Article) -> bool:
        """Return True (is duplicate) and skip indexing, or False and register.

        Checks URL first (O(1)), then SimHash (O(n) over stored hashes).
        """
        # 1. Exact URL check
        url_key = _url_key(article.url)
        if await self._redis.exists(url_key):
            logger.debug("Duplicate URL: %s", article.url)
            return True

        # 2. Content SimHash check
        text = f"{article.title} {article.content}"
        new_hash = compute_simhash(text)

        stored_hashes = await self._load_simhashes()
        if is_duplicate(new_hash, stored_hashes, self._threshold):
            logger.debug(
                "Near-duplicate content detected for URL: %s", article.url
            )
            # Still register the URL so we don't re-check the same URL
            await self._register_url(url_key)
            return True

        # Not a duplicate – register both signals
        await self._register_url(url_key)
        await self._register_simhash(new_hash)
        return False

    async def reset(self) -> None:
        """Clear all stored fingerprints (useful for testing)."""
        keys = await self._redis.keys(f"{_URL_KEY_PREFIX}*")
        if keys:
            await self._redis.delete(*keys)
        await self._redis.delete(_SIMHASH_ZSET)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_simhashes(self) -> set[int]:
        # Stored as a sorted set with score = hash value for O(1) insertion.
        # We retrieve all members – acceptable given typical daily volumes.
        members = await self._redis.zrange(_SIMHASH_ZSET, 0, -1)
        return {int(m) for m in members}

    async def _register_url(self, url_key: str) -> None:
        await self._redis.set(url_key, "1", ex=_TTL_SECONDS)

    async def _register_simhash(self, hash_value: int) -> None:
        await self._redis.zadd(_SIMHASH_ZSET, {str(hash_value): hash_value})
        # Set / refresh TTL on the whole set
        await self._redis.expire(_SIMHASH_ZSET, _TTL_SECONDS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _url_key(url: str) -> str:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    return f"{_URL_KEY_PREFIX}{digest}"
