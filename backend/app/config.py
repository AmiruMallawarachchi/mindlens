from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List
import json

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # <-- ADD THIS: ignores extra fields in .env
    )
    
    openai_api_key: str = ""
    groq_api_key: str = ""
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "mindlens"
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080
    encryption_key: str = ""
    app_env: str = "development"
    cors_origins: List[str] = ["http://localhost:3000"]
    use_openai_stubs: bool = True
    use_voice: bool = False
    use_spotify: bool = False
    admin_email: str = "admin@mindlens.app"
    
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