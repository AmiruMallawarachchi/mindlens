"""Application configuration loaded from environment variables."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings shared by the API and background services."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    groq_api_key: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = False
    pinecone_api_key: str = ""
    pinecone_index_name: str = ""
    pinecone_embedding_model: str = "llama-text-embed-v2"
    pinecone_top_k: int = 5
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
    admin_email: str = "admin@mindlens.app"
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
        if not self.pinecone_api_key or not self.pinecone_index_name:
            raise ValueError("PINECONE_API_KEY and PINECONE_INDEX_NAME are required in production")
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

    # Compatibility aliases retained while the codebase migrates to lowercase fields.
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


settings = Settings()
