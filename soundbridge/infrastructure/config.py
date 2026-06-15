"""환경 변수 헬퍼 — DB URL 등 인프라 설정 조회."""

from soundbridge.infrastructure.settings import settings


def is_database_configured() -> bool:
    return bool(settings.database_url.strip())


def get_database_url() -> str:
    """SQLAlchemy async URL (Neon PostgreSQL + psycopg3)."""
    url = settings.database_url.strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url
