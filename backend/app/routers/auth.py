"""Public authentication route module and compatibility exports."""

from fastapi import APIRouter

from app.middleware.auth import get_rate_limit_store
from app.routers.auth_admin_routes import admin_login, get_user_count, list_users
from app.routers.auth_admin_routes import router as admin_router
from app.routers.auth_helpers import hash_password, verify_password
from app.routers.auth_logout_routes import logout
from app.routers.auth_logout_routes import router as logout_router
from app.routers.auth_profile_routes import get_me, update_me
from app.routers.auth_profile_routes import router as profile_router
from app.routers.auth_schemas import (
    AdminLoginRequest,
    AdminTokenResponse,
    ProfileUpdate,
    TokenRefreshResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.routers.auth_user_routes import login, refresh_token, register
from app.routers.auth_user_routes import router as user_router

__all__ = [
    "AdminLoginRequest",
    "AdminTokenResponse",
    "ProfileUpdate",
    "TokenRefreshResponse",
    "TokenResponse",
    "UserLogin",
    "UserRegister",
    "UserResponse",
    "admin_login",
    "get_me",
    "get_rate_limit_store",
    "get_user_count",
    "hash_password",
    "list_users",
    "login",
    "logout",
    "refresh_token",
    "register",
    "router",
    "update_me",
    "verify_password",
]

router = APIRouter()
router.include_router(user_router)
router.include_router(profile_router)
router.include_router(logout_router)
router.include_router(admin_router)
