# 레이어: Infrastructure — 환경변수 SSOT
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from soundbridge.infrastructure.embedding_config import (
    DEFAULT_EMBED_MODEL,
    EMBEDDING_DIMENSION,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Database [MVP]
    database_url: str
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # EXAONE LLM (Friendli AI) [MVP] — DISCOVER 매칭 설명
    exaone_base_url: str = "https://api.friendli.ai/serverless/v1"
    exaone_model: str = "LGAI-EXAONE/K-EXAONE-236B-A23B"

    # Cohere 임베딩 [MVP] — pgvector 검색 (embed-v4.0)
    embed_model: str = DEFAULT_EMBED_MODEL
    embedding_dimension: int = EMBEDDING_DIMENSION

    # DISCOVER 타임아웃·enrich
    discover_exaone_enrich: bool = True
    discover_embed_timeout_sec: float = 30.0
    discover_llm_timeout_sec: float = 60.0
    discover_total_timeout_sec: float = 90.0

    # App [MVP]
    app_env: str = "development"
    frontend_url: str = "https://soundbridge.site"
    cors_origins: str = ""  # 쉼표 구분 추가 허용 origin
    audio_files_root: str = ""

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
