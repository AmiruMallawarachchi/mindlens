from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os

class Settings(BaseSettings):
    # LLM
    OPENAI_API_KEY: str = "sk-placeholder"
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Database
    MONGODB_URL: str = "mongodb://localhost:27017/mindlens"
    MONGODB_DB_NAME: str = "mindlens"
    
    # Redis
    UPSTASH_REDIS_URL: str = "redis://localhost:6379"
    
    # Auth
    JWT_SECRET_KEY: str = "secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080
    
    # Encryption
    ENCRYPTION_KEY: str = "encryption_key"
    
    # Feature Flags
    USE_OPENAI_STUBS: bool = True
    USE_VOICE: bool = False
    USE_SPOTIFY: bool = False
    
    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Admin
    ADMIN_EMAIL: str = "admin@mindlens.app"
    ADMIN_PASSWORD_HASH: str = "hash"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
