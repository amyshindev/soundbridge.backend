# 레이어: Infrastructure — 환경변수 SSOT
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Database [MVP]
    database_url: str
    redis_url: str = "redis://localhost:6379"

    # Gemini API [MVP] — v5.0 gemini_embed_model 별칭 호환
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "models/gemini-embedding-001"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    embedding_dimension: int = 1536

    # App [MVP]
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    # Auth [v1.1]
    secret_key: str = ""
    access_token_expire_minutes: int = 60 * 24
    email_verify_token_expire_hours: int = 24
    google_client_id: str = ""
    google_client_secret: str = ""

    # Resend [v1.1]
    resend_api_key: str = ""
    email_from: str = "noreply@soundbridge.site"

    # KOPIS [v1.1]
    kopis_api_key: str = ""
    kto_api_key: str = ""


settings = Settings()
