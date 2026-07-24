from __future__ import annotations

import logging
import math
import re
import time
import unicodedata
from typing import Callable

import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_INPUT_LENGTH = 2000
_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MB

_HEALTH_PATHS = frozenset({"/health", "/status"})

# Elasticsearch special characters that must be escaped in query strings.
_ES_SPECIAL_CHARS = r'+-=&|><!()\{\}\[\]^"~*?:\/'

_HTML_TAG_RE = re.compile(r"<[^>]*>", re.IGNORECASE)
_SCRIPT_RE = re.compile(
    r"(javascript\s*:|on\w+\s*=|<\s*script|</\s*script)",
    re.IGNORECASE,
)
_NULL_BYTE_RE = re.compile(r"\x00")

# Elasticsearch / JSON injection heuristics
_UNBALANCED_BRACES_RE = re.compile(r"\{[^}]*$|^[^{]*\}")
_SCRIPT_CONTEXT_RE = re.compile(
    r'(\"script\"\s*:|\'script\'\s*:|_script|painless|groovy|mvel)',
    re.IGNORECASE,
)
_SOURCE_MANIP_RE = re.compile(
    r"(_source|_index|_type|_id|_all)\s*[=:]",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Input sanitization
# ---------------------------------------------------------------------------


def sanitize_input(text: str) -> str:
    """Return a sanitized copy of *text* safe for use in downstream systems.

    Steps applied in order:
    1. Remove null bytes.
    2. Strip HTML tags.
    3. Remove common script-injection patterns.
    4. Normalize Unicode to NFC form.
    5. Truncate to ``_MAX_INPUT_LENGTH`` characters.
    """
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got {type(text).__name__!r}")

    text = _NULL_BYTE_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)
    text = _SCRIPT_RE.sub("", text)
    text = unicodedata.normalize("NFC", text)
    text = text[:_MAX_INPUT_LENGTH]
    return text


# ---------------------------------------------------------------------------
# Injection detection
# ---------------------------------------------------------------------------


def check_injection(text: str) -> bool:
    """Return *True* if *text* contains suspicious injection patterns.

    Checks for patterns commonly used against Elasticsearch query DSL:
    - Unbalanced braces suggesting JSON injection
    - Script execution contexts (``script``, ``painless``, ``groovy`` …)
    - ``_source`` / ``_index`` / ``_type`` manipulation
    """
    if _UNBALANCED_BRACES_RE.search(text):
        logger.warning("Injection check: unbalanced braces detected in input")
        return True
    if _SCRIPT_CONTEXT_RE.search(text):
        logger.warning("Injection check: script context pattern detected in input")
        return True
    if _SOURCE_MANIP_RE.search(text):
        logger.warning("Injection check: _source manipulation pattern detected in input")
        return True
    return False


# ---------------------------------------------------------------------------
# Search query helper
# ---------------------------------------------------------------------------


def sanitize_search_query(query: str) -> str:
    """Sanitize and validate *query* for use in an Elasticsearch query string.

    Raises:
        ValueError: If the query contains injection patterns.
    """
    query = sanitize_input(query)

    if check_injection(query):
        raise ValueError("Search query contains potentially unsafe patterns")

    # Escape Elasticsearch special characters
    escaped = re.sub(
        r"([" + re.escape(_ES_SPECIAL_CHARS) + r"])",
        r"\\\1",
        query,
    )
    return escaped


# ---------------------------------------------------------------------------
# Rate limiting middleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter backed by Redis.

    Each unique client IP is allowed at most *requests_per_minute* requests
    per 60-second window (plus a *burst_limit* grace on top).  Health-check
    paths are excluded.

    When Redis is unavailable the middleware fails open (the request is
    allowed) so that a Redis outage does not take down the API.
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_url: str,
        requests_per_minute: int = 60,
        burst_limit: int = 10,
    ) -> None:
        super().__init__(app)
        self._redis_url = redis_url
        self._rpm = requests_per_minute
        self._burst = burst_limit
        self._effective_limit = requests_per_minute + burst_limit
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis | None:
        if self._redis is None:
            try:
                client = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=1,
                )
                await client.ping()
                self._redis = client
                logger.info("RateLimitMiddleware: Redis connection established")
            except Exception as exc:  # noqa: BLE001
                logger.warning("RateLimitMiddleware: Redis unavailable (%s) – failing open", exc)
                return None
        return self._redis

    def _client_ip(self, request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip health-check endpoints
        if request.url.path in _HEALTH_PATHS:
            return await call_next(request)

        ip = self._client_ip(request)
        now = time.time()
        minute_bucket = int(now // 60)
        key = f"ratelimit:{ip}:{minute_bucket}"
        reset_ts = (minute_bucket + 1) * 60  # next minute boundary
        retry_after = int(reset_ts - now)

        redis = await self._get_redis()
        if redis is None:
            # Fail open
            return await call_next(request)

        try:
            pipe = redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, 120)
            results = await pipe.execute()
            current_count: int = results[0]
        except Exception as exc:  # noqa: BLE001
            logger.warning("RateLimitMiddleware: Redis error (%s) – failing open", exc)
            return await call_next(request)

        remaining = max(0, self._effective_limit - current_count)

        if current_count > self._effective_limit:
            logger.warning(
                "Rate limit exceeded for IP %s: %d requests (limit %d)",
                ip,
                current_count,
                self._effective_limit,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests", "retry_after": retry_after},
                headers={
                    "X-RateLimit-Limit": str(self._effective_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_ts),
                    "Retry-After": str(retry_after),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._effective_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_ts)
        return response


# ---------------------------------------------------------------------------
# Request validation middleware
# ---------------------------------------------------------------------------

_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

_BODY_METHODS = frozenset({"POST", "PUT"})
_ALLOWED_CONTENT_TYPES = ("application/json", "multipart/form-data")


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Validate request sizes and Content-Type; add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # --- Body size guard ---
        content_length_header = request.headers.get("content-length")
        if content_length_header is not None:
            try:
                content_length = int(content_length_header)
            except ValueError:
                content_length = None
            else:
                if content_length > _MAX_BODY_BYTES:
                    logger.warning(
                        "Request body too large from %s: %d bytes declared",
                        request.client.host if request.client else "unknown",
                        content_length,
                    )
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large (max 1 MB)"},
                    )
                    self._add_security_headers(response)
                    return response

        # --- Content-Type guard for body-bearing methods ---
        if request.method in _BODY_METHODS:
            content_type = request.headers.get("content-type", "")
            # Strip parameters (e.g. "; charset=utf-8") for comparison
            media_type = content_type.split(";")[0].strip().lower()
            if media_type and not any(
                media_type.startswith(allowed) for allowed in _ALLOWED_CONTENT_TYPES
            ):
                logger.warning(
                    "Unsupported Content-Type %r from %s",
                    content_type,
                    request.client.host if request.client else "unknown",
                )
                response = JSONResponse(
                    status_code=415,
                    content={
                        "detail": (
                            "Unsupported Media Type. "
                            "Use 'application/json' or 'multipart/form-data'."
                        )
                    },
                )
                self._add_security_headers(response)
                return response

        response = await call_next(request)
        self._add_security_headers(response)
        return response

    @staticmethod
    def _add_security_headers(response: Response) -> None:
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
