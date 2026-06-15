"""Neon PostgreSQL 비동기 연결 (SQLAlchemy 2.0)."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from soundbridge.infrastructure.base import Base
from soundbridge.infrastructure.config import get_database_url, is_database_configured
from soundbridge.infrastructure.settings import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

engine: AsyncEngine | None = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def _ensure_engine() -> None:
    global _engine, _session_factory, engine, AsyncSessionLocal
    if _engine is not None:
        return
    _engine = create_async_engine(
        get_database_url(),
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=settings.app_env == "development",
    )
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    engine = _engine
    AsyncSessionLocal = _session_factory


async def init_db() -> None:
    """ORM 메타데이터로 테이블 생성 (Neon PostgreSQL)."""
    if not is_database_configured():
        return
    from sqlalchemy import text

    _ensure_engine()
    assert engine is not None
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    global _engine, _session_factory, engine, AsyncSessionLocal
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    engine = None
    AsyncSessionLocal = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if not is_database_configured():
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL is not set.",
        )
    _ensure_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[AsyncSession, Depends(get_db)]

__all__ = [
    "AsyncSessionLocal",
    "Base",
    "DbSession",
    "_ensure_engine",
    "dispose_engine",
    "engine",
    "get_db",
    "init_db",
]
