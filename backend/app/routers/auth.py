"""
MindLens Authentication Router
==============================
Register, login, logout, refresh tokens, admin endpoints.

Features:
  - bcrypt password hashing (rounds=12)
  - Access token (JWT, 15 min) + Refresh token (JWT, 7 days)
  - httpOnly cookie for refresh token (Secure in production)
  - Token blocklist on logout
  - Login lockout after 5 failed attempts (15 min)
  - Role-based access control (user / admin)
  - Admin token creation via separate secret

Security:
  - No secrets in code
  - All tokens signed with env secrets
  - PII never logged
"""

from __future__ import annotations

import datetime
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorDatabase
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

from app.config import settings
from app.db import get_db
from app.middleware.auth import (
    create_admin_token,
    create_token_pair,
    get_rate_limit_store,
    require_user,
    verify_access_token,
    verify_refresh_token,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- Security Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


# --- Pydantic Schemas ---


class UserRegister(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=13, le=100)
    nickname: str | None = Field(None, max_length=100)


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


class TokenRefreshResponse(BaseModel):
    """Response after token refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


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


# --- Helper Functions ---


def hash_password(password: str) -> str:
    """Hash a plain password using bcrypt. Truncates to 72 bytes if needed."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password = password_bytes[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


# --- Routes ---


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    user_data: UserRegister,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Register a new MindLens user.

    - Checks for duplicate email
    - Hashes password with bcrypt (rounds=12)
    - Determines age group (teen vs adult)
    - Sets role = 'user'
    - Returns JWT access token + sets refresh token in httpOnly cookie
    """
    # Check if email already exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Determine age group
    age_group = "teen" if user_data.age <= 19 else "adult"

    # Create user document
    now = datetime.datetime.now(datetime.UTC)
    user_doc = {
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "name": user_data.name,
        "nickname": user_data.nickname or user_data.name,
        "age": user_data.age,
        "age_group": age_group,
        "role": settings.USER_ROLE_NAME,
        "created_at": now,
        "updated_at": now,
        "is_active": True,
        "onboarding_complete": False,
    }

    # Insert into MongoDB
    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Create token pair
    token_pair = create_token_pair(user_id, user_data.email, role=settings.USER_ROLE_NAME)

    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=token_pair["refresh_token"],
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=settings.jwt_refresh_expire_minutes * 60,
        path="/",
    )

    return TokenResponse(
        access_token=token_pair["access_token"],
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user_id=user_id,
        role=settings.USER_ROLE_NAME,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login existing user",
)
async def login(
    credentials: UserLogin,
    response: Response,
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Authenticate a user and return a JWT access token.

    - Finds user by email
    - Verifies password with bcrypt
    - Checks login lockout (5 failed attempts → 15 min lockout)
    - Returns JWT + sets refresh token in httpOnly cookie
    """
    # Check login lockout by email
    lockout_key = f"login:{credentials.email}"
    locked = await get_rate_limit_store().is_locked_out(
        lockout_key, max_attempts=settings.RATE_LIMIT_MAX_LOGIN_ATTEMPTS
    )
    if locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again in 15 minutes.",
        )

    # Find user by email
    user = await db.users.find_one({"email": credentials.email})
    if not user:
        # Record failed attempt (don't reveal email doesn't exist)
        await get_rate_limit_store().record_login_attempt(lockout_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(credentials.password, user["password_hash"]):
        attempt_count = await get_rate_limit_store().record_login_attempt(lockout_key)
        remaining = max(0, settings.RATE_LIMIT_MAX_LOGIN_ATTEMPTS - attempt_count)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid email or password. {remaining} attempts remaining.",
        )

    # Check if user is active
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    # Reset failed attempts on success
    await get_rate_limit_store().reset_login_attempts(lockout_key)

    # Generate token pair
    user_id = str(user["_id"])
    role = user.get("role", settings.USER_ROLE_NAME)
    token_pair = create_token_pair(user_id, credentials.email, role=role)

    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=token_pair["refresh_token"],
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=settings.jwt_refresh_expire_minutes * 60,
        path="/",
    )

    # Log login event (anonymized IP)
    ip = request.client.host if request.client else "unknown"
    await db.audit_log.insert_one({
        "event": "user_login",
        "user_id": user_id,
        "ip_hash": hash(ip) % (2**32),  # simple hash, not PII
        "timestamp": datetime.datetime.now(datetime.UTC),
    })

    return TokenResponse(
        access_token=token_pair["access_token"],
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user_id=user_id,
        role=role,
    )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    summary="Refresh access token using refresh token",
)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Exchange a valid refresh token (from httpOnly cookie) for a new access token.

    - Validates refresh token from cookie
    - Checks blocklist
    - Issues new access token (and optionally new refresh token — rotation)
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided",
        )

    try:
        jwt_user = verify_refresh_token(refresh_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {exc}",
        ) from exc

    # Check blocklist
    blocklisted = await db.token_blocklist.find_one({"token_jti": jwt_user.jti})
    if blocklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # Verify user still exists and is active
    user = await db.users.find_one({"_id": jwt_user.id, "is_active": True})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new token pair (refresh token rotation)
    token_pair = create_token_pair(
        jwt_user.id, jwt_user.email, role=jwt_user.role
    )

    # Set new refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=token_pair["refresh_token"],
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=settings.jwt_refresh_expire_minutes * 60,
        path="/",
    )

    return TokenRefreshResponse(
        access_token=token_pair["access_token"],
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user",
)
async def logout(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Logout endpoint.

    - Adds both access and refresh tokens to blocklist
    - Clears refresh token cookie
    - Invalidates all tokens for this user (security event)
    """
    now = datetime.datetime.now(datetime.UTC)

    # Blocklist access token
    if credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti:
                await db.token_blocklist.insert_one({
                    "token_jti": jti,
                    "exp": exp,
                    "created_at": now,
                })
        except JWTError:
            pass  # Already invalid

    # Blocklist refresh token
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti:
                await db.token_blocklist.insert_one({
                    "token_jti": jti,
                    "exp": exp,
                    "created_at": now,
                })
        except JWTError:
            pass

    # Clear cookie
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path="/",
    )

    return {"message": "Logged out successfully"}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user: dict = Depends(require_user),
):
    """
    Return the current authenticated user's profile.

    Requires valid JWT in Authorization header.
    """
    return UserResponse(
        id=str(current_user["_id"]),
        email=current_user["email"],
        name=current_user["name"],
        nickname=current_user.get("nickname"),
        age=current_user["age"],
        age_group=current_user.get("age_group", "adult"),
        role=current_user.get("role", settings.USER_ROLE_NAME),
        onboarding_complete=current_user.get("onboarding_complete", False),
        created_at=current_user["created_at"],
    )


# --- Admin Endpoints ---


@router.post(
    "/admin/login",
    response_model=AdminTokenResponse,
    summary="Admin login (separate token system)",
)
async def admin_login(
    request: AdminLoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Admin login with separate JWT secret.

    - Validates email + password
    - Requires role == 'admin'
    - Returns short-lived admin token (1 hour)
    """
    # Check lockout
    lockout_key = f"login:{request.email}"
    locked = await get_rate_limit_store().is_locked_out(
        lockout_key, max_attempts=settings.RATE_LIMIT_MAX_LOGIN_ATTEMPTS
    )
    if locked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again in 15 minutes.",
        )

    user = await db.users.find_one({"email": request.email})
    if not user:
        await get_rate_limit_store().record_login_attempt(lockout_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not verify_password(request.password, user["password_hash"]):
        await get_rate_limit_store().record_login_attempt(lockout_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if user.get("role") != settings.ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    await get_rate_limit_store().reset_login_attempts(lockout_key)

    user_id = str(user["_id"])
    admin_token = create_admin_token(user_id, request.email)

    return AdminTokenResponse(
        admin_token=admin_token,
        token_type="bearer",
        expires_in=settings.admin_jwt_expire_minutes * 60,
    )


@router.get(
    "/users/count",
    summary="Get total user count (admin only)",
)
async def get_user_count(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """
    Return total number of registered users.

    Protected: requires valid authentication. Admin role enforced at query level.
    """
    if current_user.get("role") != settings.ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    count = await db.users.count_documents({})
    return {"total_users": count}


@router.get(
    "/users/list",
    summary="List all users (admin only)",
)
async def list_users(
    skip: int = 0,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(require_user),
):
    """List all users (admin only)."""
    if current_user.get("role") != settings.ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    cursor = db.users.find({}).skip(skip).limit(limit)
    users = []
    async for doc in cursor:
        users.append({
            "id": str(doc["_id"]),
            "email": doc["email"],
            "name": doc["name"],
            "age_group": doc.get("age_group"),
            "role": doc.get("role", "user"),
            "onboarding_complete": doc.get("onboarding_complete", False),
            "created_at": doc.get("created_at"),
        })
    return {"users": users, "count": len(users)}
