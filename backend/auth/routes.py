"""Auth API routes."""

from __future__ import annotations

import logging
from typing import Optional

from elasticsearch import AsyncElasticsearch
from fastapi import APIRouter, Depends, HTTPException, Header

from core.deps import get_es_client
from .models import (
    UserLoginRequest,
    UserRegisterRequest,
    UserUpdateRequest,
    ReadingHistoryEntry,
)
from .service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_auth_service(es: AsyncElasticsearch = Depends(get_es_client)) -> AuthService:
    return AuthService(es)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict | None:
    """Extract current user from Authorization header. Returns None if not authenticated."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    payload = auth_svc.verify_token(token)
    if not payload:
        return None
    user = await auth_svc.get_user(payload["sub"])
    return user


async def require_current_user(
    user: dict | None = Depends(get_current_user),
) -> dict:
    """Require authentication — raises 401 if not logged in."""
    if user is None:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


@router.post("/register")
async def register(
    req: UserRegisterRequest,
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict:
    try:
        await auth_svc.ensure_index()
        result = await auth_svc.register(req.email, req.username, req.password)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/login")
async def login(
    req: UserLoginRequest,
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict:
    try:
        await auth_svc.ensure_index()
        result = await auth_svc.login(req.email, req.password)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.get("/me")
async def get_me(user: dict = Depends(require_current_user)) -> dict:
    return user


@router.put("/me")
async def update_me(
    req: UserUpdateRequest,
    user: dict = Depends(require_current_user),
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict:
    updates = {}
    if req.username is not None:
        updates["username"] = req.username
    if req.profile is not None:
        updates["profile"] = req.profile.model_dump()

    if not updates:
        return user

    result = await auth_svc.update_profile(user["id"], updates)
    if result is None:
        raise HTTPException(status_code=500, detail="更新失败")
    return result


@router.post("/reading-history")
async def record_reading(
    entry: ReadingHistoryEntry,
    user: dict = Depends(require_current_user),
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict:
    await auth_svc.record_reading(user["id"], entry.article_id)
    return {"status": "ok"}


@router.get("/reading-history")
async def get_reading_history(
    user: dict = Depends(require_current_user),
    auth_svc: AuthService = Depends(_get_auth_service),
) -> dict:
    history = await auth_svc.get_reading_history(user["id"])
    return {"history": history}
