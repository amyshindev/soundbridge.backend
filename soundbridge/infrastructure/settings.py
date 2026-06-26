# 레이어: Infrastructure — 환경변수 SSOT
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Database [MVP]
    database_url: str
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Gemini API [v1.1] — 선택. Ollama EXAONE 사용 시 비워도 됨
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embed_model: str = "models/gemini-embedding-001"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    embedding_dimension: int = 768

    # Ollama [MVP] — DISCOVER 임베딩 + EXAONE 매칭 설명
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_chat_model: str = "exaone3.5:2.4b"

    # App [MVP]
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"
    cors_origins: str = ""
    # 국악 원천데이터 루트 (test/원천데이터). 비우면 /audio 엔드포인트 503
    audio_files_root: str = ""
    # DISCOVER: enrich=true 시 Ollama LLM(EXAONE)으로 매칭 설명. false면 템플릿
    discover_gemini_enrich: bool = False
    discover_llm_timeout_sec: float = 45.0
    discover_embed_timeout_sec: float = 30.0
    discover_total_timeout_sec: float = 75.0

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
