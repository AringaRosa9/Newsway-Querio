"""User models and schemas."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class UserProfile(BaseModel):
    interests: list[str] = Field(default_factory=list)
    preferred_sources: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    language: str = "zh"


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    username: str
    hashed_password: str = ""
    profile: UserProfile = Field(default_factory=UserProfile)
    reading_history: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    is_active: bool = True


class UserRegisterRequest(BaseModel):
    email: str
    username: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少需要6个字符")
        return v

    @field_validator("email")
    @classmethod
    def email_format(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("请输入有效的邮箱地址")
        return v


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    profile: UserProfile
    created_at: str


class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    profile: Optional[UserProfile] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ReadingHistoryEntry(BaseModel):
    article_id: str
    query: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
