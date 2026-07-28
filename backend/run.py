"""Local development entry point."""

import os

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=settings.app_env == "development",
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
