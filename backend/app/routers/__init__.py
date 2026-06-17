from backend.app.routers.auth import router as auth_router
from backend.app.routers.session import router as session_router
from backend.app.routers.dashboard import router as dashboard_router

__all__ = ["auth_router", "session_router", "dashboard_router"]