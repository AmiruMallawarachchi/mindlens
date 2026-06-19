from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.session import router as session_router

__all__ = ["auth_router", "session_router", "dashboard_router"]
