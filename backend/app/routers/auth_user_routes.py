"""Register, login, refresh, and logout routes."""

from __future__ import annotations

import datetime
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import PyJWTError as JWTError
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.db import document_id_filter, get_db
from app.middleware.auth import create_token_pair, get_rate_limit_store, require_user, verify_refresh_token
from app.routers.account import record_login_session
from app.routers.auth_helpers import _audit_ip_hash, _clear_auth_cookies, _set_auth_cookies, hash_password, verify_password
from app.routers.auth_schemas import TokenRefreshResponse, TokenResponse, UserLogin, UserRegister
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)
@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    user_data: UserRegister,
    response: Response,
    request: Request,
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

    csrf_token = _set_auth_cookies(response, token_pair)
    await record_login_session(
        db, user_id, token_pair["jti"], token_pair["refresh_jti"], request
    )

    return TokenResponse(
        access_token=token_pair["access_token"],
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user_id=user_id,
        role=settings.USER_ROLE_NAME,
        csrf_token=csrf_token,
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
    - Checks login lockout (5 failed attempts ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ 15 min lockout)
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

    csrf_token = _set_auth_cookies(response, token_pair)
    await record_login_session(
        db, user_id, token_pair["jti"], token_pair["refresh_jti"], request
    )

    # Log login event (anonymized IP)
    ip = request.client.host if request.client else "unknown"
    await db.audit_log.insert_one({
        "event": "user_login",
        "user_id": user_id,
        "ip_hash": _audit_ip_hash(ip),
        "timestamp": datetime.datetime.now(datetime.UTC),
    })

    return TokenResponse(
        access_token=token_pair["access_token"],
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        user_id=user_id,
        role=role,
        csrf_token=csrf_token,
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
    - Issues new access token (and optionally new refresh token ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â rotation)
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
    user_filter = document_id_filter(jwt_user.id)
    user_filter["is_active"] = True
    user = await db.users.find_one(user_filter)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new token pair (refresh token rotation)
    token_pair = create_token_pair(
        jwt_user.id, jwt_user.email, role=jwt_user.role
    )

    csrf_token = _set_auth_cookies(response, token_pair)

    return TokenRefreshResponse(
        access_token=token_pair["access_token"],
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60,
        csrf_token=csrf_token,
    )
