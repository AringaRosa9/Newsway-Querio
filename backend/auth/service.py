"""Authentication and user management service.

Uses Elasticsearch as the user store and JWT for stateless auth.
Passwords are hashed with SHA-256 + salt (no bcrypt dependency).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone
from typing import Any, Optional

from elasticsearch import AsyncElasticsearch

from core.config import get_settings

logger = logging.getLogger(__name__)

_USERS_INDEX = "news_users"
_TOKEN_EXPIRY = 86400 * 7  # 7 days


def _hash_password(password: str, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    parts = stored.split(":", 1)
    if len(parts) != 2:
        return False
    salt = parts[0]
    return _hash_password(password, salt) == stored


def _create_jwt(payload: dict, secret: str) -> str:
    header = urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_b64 = urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    msg = f"{header}.{payload_b64}"
    sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return f"{msg}.{sig}"


def _decode_jwt(token: str, secret: str) -> dict | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    msg = f"{parts[0]}.{parts[1]}"
    expected_sig = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, parts[2]):
        return None
    padding = 4 - len(parts[1]) % 4
    payload_bytes = urlsafe_b64decode(parts[1] + "=" * padding)
    payload = json.loads(payload_bytes)
    if payload.get("exp", 0) < time.time():
        return None
    return payload


class AuthService:
    """Handles user registration, authentication, and profile management."""

    def __init__(self, es: AsyncElasticsearch) -> None:
        self._es = es
        self._secret = get_settings().JWT_SECRET

    async def ensure_index(self) -> None:
        exists = await self._es.indices.exists(index=_USERS_INDEX)
        if not exists:
            await self._es.indices.create(
                index=_USERS_INDEX,
                body={
                    "mappings": {
                        "properties": {
                            "email": {"type": "keyword"},
                            "username": {"type": "keyword"},
                            "hashed_password": {"type": "keyword", "index": False},
                            "profile": {"type": "object", "enabled": False},
                            "reading_history": {"type": "keyword"},
                            "created_at": {"type": "date"},
                            "is_active": {"type": "boolean"},
                        }
                    }
                },
            )
            logger.info("Created users index '%s'", _USERS_INDEX)

    async def register(self, email: str, username: str, password: str) -> dict:
        """Register a new user."""
        existing = await self._es.search(
            index=_USERS_INDEX,
            body={"query": {"term": {"email": email}}},
            size=1,
        )
        if existing["hits"]["total"]["value"] > 0:
            raise ValueError("该邮箱已被注册")

        import uuid
        user_id = str(uuid.uuid4())
        user_doc = {
            "email": email,
            "username": username,
            "hashed_password": _hash_password(password),
            "profile": {
                "interests": [],
                "preferred_sources": [],
                "preferred_categories": [],
                "language": "zh",
            },
            "reading_history": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }

        await self._es.index(index=_USERS_INDEX, id=user_id, body=user_doc)
        await self._es.indices.refresh(index=_USERS_INDEX)

        token = self._create_token(user_id, email)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": email,
                "username": username,
                "profile": user_doc["profile"],
                "created_at": user_doc["created_at"],
            },
        }

    async def login(self, email: str, password: str) -> dict:
        """Authenticate a user and return a JWT."""
        result = await self._es.search(
            index=_USERS_INDEX,
            body={"query": {"term": {"email": email}}},
            size=1,
        )
        hits = result["hits"]["hits"]
        if not hits:
            raise ValueError("邮箱或密码错误")

        user = hits[0]
        user_doc = user["_source"]
        if not _verify_password(password, user_doc["hashed_password"]):
            raise ValueError("邮箱或密码错误")

        token = self._create_token(user["_id"], email)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user["_id"],
                "email": user_doc["email"],
                "username": user_doc["username"],
                "profile": user_doc.get("profile", {}),
                "created_at": user_doc["created_at"],
            },
        }

    async def get_user(self, user_id: str) -> dict | None:
        """Fetch a user by ID."""
        try:
            doc = await self._es.get(index=_USERS_INDEX, id=user_id)
            source = doc["_source"]
            return {
                "id": doc["_id"],
                "email": source["email"],
                "username": source["username"],
                "profile": source.get("profile", {}),
                "created_at": source["created_at"],
            }
        except Exception:
            return None

    async def update_profile(self, user_id: str, updates: dict) -> dict | None:
        """Update user profile."""
        try:
            await self._es.update(
                index=_USERS_INDEX,
                id=user_id,
                body={"doc": updates},
            )
            return await self.get_user(user_id)
        except Exception as exc:
            logger.error("Failed to update user %s: %s", user_id, exc)
            return None

    async def record_reading(self, user_id: str, article_id: str) -> None:
        """Add an article to the user's reading history."""
        try:
            await self._es.update(
                index=_USERS_INDEX,
                id=user_id,
                body={
                    "script": {
                        "source": """
                            if (ctx._source.reading_history == null) {
                                ctx._source.reading_history = [];
                            }
                            if (!ctx._source.reading_history.contains(params.article_id)) {
                                ctx._source.reading_history.add(0, params.article_id);
                                if (ctx._source.reading_history.size() > 200) {
                                    ctx._source.reading_history = ctx._source.reading_history.subList(0, 200);
                                }
                            }
                        """,
                        "params": {"article_id": article_id},
                    }
                },
            )
        except Exception as exc:
            logger.warning("Failed to record reading for user %s: %s", user_id, exc)

    async def get_reading_history(self, user_id: str, limit: int = 50) -> list[str]:
        """Get user's recent reading history."""
        try:
            doc = await self._es.get(index=_USERS_INDEX, id=user_id, _source=["reading_history"])
            history = doc["_source"].get("reading_history", [])
            return history[:limit]
        except Exception:
            return []

    def verify_token(self, token: str) -> dict | None:
        """Verify and decode a JWT token."""
        return _decode_jwt(token, self._secret)

    def _create_token(self, user_id: str, email: str) -> str:
        payload = {
            "sub": user_id,
            "email": email,
            "exp": int(time.time()) + _TOKEN_EXPIRY,
            "iat": int(time.time()),
        }
        return _create_jwt(payload, self._secret)
