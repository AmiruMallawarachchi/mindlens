"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
import pathlib
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Two levels up from backend/app/config.py. Locally that's the repo root
# (mindlens/); in the Docker image (Dockerfile: COPY backend ./backend under
# WORKDIR /app) it's /app — which is exactly where `backend/data/...`
# resolves to on disk there too. Used to make the RAG paths below
# cwd-independent: they used to resolve relative to whatever directory
# uvicorn was launched from, and `cd backend && uvicorn ...` (the documented
# local command) made them resolve one level too deep, into a second,
# never-ingested `backend/backend/data/` that RAG silently always missed.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings shared by the API and background services."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    openai_api_key: str = ""
    groq_api_key: str = ""
    hf_token: str = ""
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "mindlens"

    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_refresh_secret_key: str = "dev-refresh-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    jwt_refresh_expire_minutes: int = 10080
    admin_jwt_secret: str = "admin-dev-secret-key-change-in-production"
    admin_jwt_expire_minutes: int = 60
    encryption_key: str = ""

    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    cookie_domain: str | None = None
    cookie_secure: bool | None = None
    cookie_samesite: Literal["lax", "strict", "none"] | None = None

    use_openai_stubs: bool = True
    # Read by music_agent.py's MCP client. USE_VOICE and USE_SPOTIFY were
    # removed from here — declared settings that nothing in app/ ever read,
    # not even to gate this URL; MusicAgent always attempts the MCP call and
    # falls back to LLM + static tracks on failure regardless of either flag.
    spotify_mcp_url: str = "http://localhost:8001"
    admin_email: str = "admin@mindlens.app"

    emotion_model_id: str = "SamLowe/roberta-base-go_emotions"
    crisis_model_id: str = "AmiruMallawarachchi/mindlens-crisis"
    mh_model_id: str = "AmiruMallawarachchi/mindlens-mh-classifier"
    distortion_model_id: str = "AmiruMallawarachchi/mindlens-distortion-classifier"
    rag_reranker_model_id: str = "AmiruMallawarachchi/mindlens-rag-reranker"

    # Which commit of each Hub repo to fetch. Without this, from_pretrained
    # takes whatever sits at the branch head when the download happens, so a
    # repo that is re-pushed — or compromised — silently swaps the weights the
    # app runs on.
    #
    # The emotion checkpoint is a third-party repo nobody here controls, so it
    # is pinned to an exact commit; that is where the supply-chain exposure
    # actually is. The other four are our own and track `main`, because they
    # are still being retrained and a stale pin would quietly keep serving the
    # superseded model after a push. Pin those too before anything that needs
    # reproducible inference — a dissertation result, or a release.
    emotion_model_revision: str = "d75048347613a25d77de8cf6412eaae9fa7b26be"
    crisis_model_revision: str = "main"
    mh_model_revision: str = "main"
    distortion_model_revision: str = "main"
    rag_reranker_model_revision: str = "main"

    def model_revision_for(self, name: str) -> str:
        """Revision to fetch for a registry entry, defaulting to `main` for
        any name the registry gains without a matching setting."""
        return {
            "emotion": self.emotion_model_revision,
            "crisis": self.crisis_model_revision,
            "mental_health": self.mh_model_revision,
            "distortion": self.distortion_model_revision,
            "rag_reranker": self.rag_reranker_model_revision,
        }.get(name, "main")
    preload_models: bool = False
    model_inference_timeout_seconds: float = 30.0
    preload_rag: bool = False
    render_git_commit: str = "local"

    rate_limit_per_ip_minute: int = 100
    rate_limit_per_user_hour: int = 60
    rate_limit_login_lockout_minutes: int = 15
    rate_limit_max_login_attempts: int = 5

    ws_heartbeat_interval_seconds: int = 30
    ws_message_timeout_seconds: int = 300
    ws_max_concurrent_per_user: int = 1
    ws_max_message_chars: int = 2000

    anonymizer_enabled: bool = True
    admin_role_name: str = "admin"
    user_role_name: str = "user"

    rag_collection_name: str = "mindlens_therapy_knowledge"
    rag_embed_model: str = "all-MiniLM-L6-v2"
    rag_k_results: int = 5
    rag_fetch_k: int = 20
    # Cross-encoder reranking of MMR candidates (app/rag/retriever.py). Off
    # means MMR order is served as-is — used by the retrieval-quality
    # evaluation to measure what the reranker actually contributes.
    rag_reranker_enabled: bool = True
    # Added to the cross-encoder's sigmoid score for chunks whose metadata
    # matches the user's age group. Deliberately a swept parameter, not a
    # magic number: T7c reports NDCG@3 / MRR / P@3 across 0.0, 0.05 and 0.10.
    # If the curve shows the heuristic hurts ranking, this goes to 0.0 and
    # that result is reported rather than hidden.
    rag_age_boost: float = 0.05
    rag_lambda_mult: float = 0.5
    rag_chunk_size: int = 400
    rag_chunk_overlap: int = 50
    rag_knowledge_path: str = "backend/data/therapy_knowledge.json"
    chromadb_persist_dir: str = "backend/data/chroma_db"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = [item.strip() for item in value.split(",") if item.strip()]
            return parsed
        return value

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod", "off"}:
                return False
            if normalized in {"development", "dev", "debug", "on"}:
                return True
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        if not self.is_production:
            return self

        insecure_values = {
            "JWT_SECRET_KEY": self.jwt_secret_key.startswith("dev-"),
            "JWT_REFRESH_SECRET_KEY": self.jwt_refresh_secret_key.startswith("dev-"),
            "ADMIN_JWT_SECRET": self.admin_jwt_secret.startswith("admin-dev-"),
            "ENCRYPTION_KEY": not self.encryption_key,
            "MONGODB_URL": self.mongodb_url == "mongodb://localhost:27017",
        }
        invalid = [name for name, insecure in insecure_values.items() if insecure]
        if invalid:
            raise ValueError(
                "Production configuration is missing secure values for: "
                + ", ".join(invalid)
            )
        if self.use_openai_stubs:
            raise ValueError("USE_OPENAI_STUBS must be false in production")
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY is required in production")
        if not self.cors_origins or "*" in self.cors_origins:
            raise ValueError("Production CORS_ORIGINS must contain explicit origins")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def effective_cookie_secure(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @property
    def effective_cookie_samesite(self) -> Literal["lax", "strict", "none"]:
        if self.cookie_samesite is not None:
            return self.cookie_samesite
        return "none" if self.is_production else "lax"

    @property
    def resolved_rag_knowledge_path(self) -> str:
        """`rag_knowledge_path`, made cwd-independent — see `_REPO_ROOT`.
        An absolute override (e.g. a deployment env var) passes through
        unchanged; only the relative default gets anchored."""
        path = pathlib.Path(self.rag_knowledge_path)
        return str(path if path.is_absolute() else _REPO_ROOT / path)

    @property
    def resolved_chromadb_persist_dir(self) -> str:
        """`chromadb_persist_dir`, made cwd-independent — see `_REPO_ROOT`."""
        path = pathlib.Path(self.chromadb_persist_dir)
        return str(path if path.is_absolute() else _REPO_ROOT / path)

    # Compatibility aliases retained while the codebase migrates to lowercase fields.
    DEBUG = property(lambda self: self.debug)
    CORS_ORIGINS = property(lambda self: self.cors_origins)
    EMOTION_MODEL_ID = property(lambda self: self.emotion_model_id)
    CRISIS_MODEL_ID = property(lambda self: self.crisis_model_id)
    MH_MODEL_ID = property(lambda self: self.mh_model_id)
    DISTORTION_MODEL_ID = property(lambda self: self.distortion_model_id)
    RAG_RERANKER_MODEL_ID = property(lambda self: self.rag_reranker_model_id)
    RATE_LIMIT_PER_IP_MINUTE = property(lambda self: self.rate_limit_per_ip_minute)
    RATE_LIMIT_PER_USER_HOUR = property(lambda self: self.rate_limit_per_user_hour)
    RATE_LIMIT_LOGIN_LOCKOUT_MINUTES = property(
        lambda self: self.rate_limit_login_lockout_minutes
    )
    RATE_LIMIT_MAX_LOGIN_ATTEMPTS = property(lambda self: self.rate_limit_max_login_attempts)
    WS_HEARTBEAT_INTERVAL_SECONDS = property(lambda self: self.ws_heartbeat_interval_seconds)
    WS_MESSAGE_TIMEOUT_SECONDS = property(lambda self: self.ws_message_timeout_seconds)
    WS_MAX_CONCURRENT_PER_USER = property(lambda self: self.ws_max_concurrent_per_user)
    ANONYMIZER_ENABLED = property(lambda self: self.anonymizer_enabled)
    ADMIN_ROLE_NAME = property(lambda self: self.admin_role_name)
    USER_ROLE_NAME = property(lambda self: self.user_role_name)
    RAG_COLLECTION_NAME = property(lambda self: self.rag_collection_name)
    RAG_EMBED_MODEL = property(lambda self: self.rag_embed_model)
    RAG_K_RESULTS = property(lambda self: self.rag_k_results)
    RAG_FETCH_K = property(lambda self: self.rag_fetch_k)
    RAG_LAMBDA_MULT = property(lambda self: self.rag_lambda_mult)
    RAG_CHUNK_SIZE = property(lambda self: self.rag_chunk_size)
    RAG_CHUNK_OVERLAP = property(lambda self: self.rag_chunk_overlap)
    RAG_KNOWLEDGE_PATH = property(lambda self: self.rag_knowledge_path)
    CHROMADB_PERSIST_DIR = property(lambda self: self.chromadb_persist_dir)


settings = Settings()
