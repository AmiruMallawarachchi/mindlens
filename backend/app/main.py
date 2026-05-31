from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.db import connect_db, close_db
from app.models.loader import model_manager
from app.routers import auth, session, dashboard

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    model_manager.load_all()  # Load all HF models at startup
    yield
    await close_db()

app = FastAPI(
    title="MindLens API",
    description="Multi-Agent AI Mental Health Companion",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(session.router, prefix="/ws", tags=["session"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "models_loaded": list(model_manager.models.keys()),
        "device": model_manager.device
    }