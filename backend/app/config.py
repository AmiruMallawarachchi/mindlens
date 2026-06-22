import json
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    openai_api_key: str = ""
    groq_api_key: str = ""
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "mindlens"
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 15
    jwt_refresh_expire_minutes: int = 10080  # 7 days
    admin_jwt_secret: str = "admin-dev-secret-key-change-in-production"
    admin_jwt_expire_minutes: int = 60
    encryption_key: str = ""
    app_env: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]
    use_openai_stubs: bool = True
    use_voice: bool = False
    use_spotify: bool = False
    admin_email: str = "admin@mindlens.app"

    # --- Debug --------------------------------------------------------------
    DEBUG: bool = False

    # --- Model IDs ----------------------------------------------------------
    EMOTION_MODEL_ID: str = "SamLowe/roberta-base-go_emotions"
    CRISIS_MODEL_ID: str = "AmiruMallawarachchi/mindlens-crisis"
    MH_MODEL_ID: str = "AmiruMallawarachchi/mindlens-mh-classifier"

    # --- CORS ---------------------------------------------------------------
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    


    # --- Rate Limiting (in-memory) ----------------------------------------

    RATE_LIMIT_PER_IP_MINUTE: int = 100
    RATE_LIMIT_PER_USER_HOUR: int = 60
    RATE_LIMIT_LOGIN_LOCKOUT_MINUTES: int = 15
    RATE_LIMIT_MAX_LOGIN_ATTEMPTS: int = 5
    
    # --- WebSocket ----------------------------------------------------------
    WS_HEARTBEAT_INTERVAL_SECONDS: int = 30
    WS_MESSAGE_TIMEOUT_SECONDS: int = 300
    WS_MAX_CONCURRENT_PER_USER: int = 1
    
    # --- Anonymization ------------------------------------------------------
    ANONYMIZER_ENABLED: bool = True
    
    # --- Admin --------------------------------------------------------------
    ADMIN_ROLE_NAME: str = "admin"
    USER_ROLE_NAME: str = "user"
    

    # --- RAG / ChromaDB -----------------------------------------------------
    RAG_COLLECTION_NAME: str = "mindlens_therapy_knowledge"
    RAG_EMBED_MODEL: str = "all-MiniLM-L6-v2"
    RAG_K_RESULTS: int = 5
    RAG_FETCH_K: int = 20
    RAG_LAMBDA_MULT: float = 0.5
    RAG_CHUNK_SIZE: int = 400
    RAG_CHUNK_OVERLAP: int = 50
    RAG_KNOWLEDGE_PATH: str = "data/therapy_knowledge.json"
    CHROMADB_PERSIST_DIR: str = "chroma_db"
    

    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [item.strip() for item in v.split(',')]
        return v

settings = Settings()
