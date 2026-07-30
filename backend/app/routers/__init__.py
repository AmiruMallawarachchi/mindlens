from app.routers.account import router as account_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.dashboard import router as dashboard_router
from app.routers.journal import router as journal_router
from app.routers.memory import router as memory_router
from app.routers.onboarding import router as onboarding_router
from app.routers.session import router as session_router
from app.routers.system import router as system_router

__all__ = [
    "auth_router",
    "chat_router",
    "dashboard_router",
    "account_router",
    "journal_router",
    "memory_router",
    "onboarding_router",
    "session_router",
    "system_router",
]

