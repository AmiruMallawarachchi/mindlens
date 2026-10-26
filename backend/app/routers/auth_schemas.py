"""Pydantic request and response schemas for authentication routes."""

import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator
class UserRegister(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=13, le=100)
    nickname: str | None = Field(None, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_bcrypt_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return value


class UserLogin(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Response containing JWT access token."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str
    role: str = "user"
    csrf_token: str


class TokenRefreshResponse(BaseModel):
    """Response after token refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    csrf_token: str


class UserResponse(BaseModel):
    """Public user profile."""

    id: str
    email: str
    name: str
    nickname: str | None
    age: int
    age_group: str
    role: str
    onboarding_complete: bool
    created_at: datetime.datetime


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminTokenResponse(BaseModel):
    """Admin token response."""

    admin_token: str
    token_type: str = "bearer"
    expires_in: int

class ProfileUpdate(BaseModel):
    """Settings > General. Only what the user is allowed to change about
    themselves â€” email, role and onboarding state are deliberately absent."""

    nickname: str | None = Field(None, min_length=1, max_length=60)

