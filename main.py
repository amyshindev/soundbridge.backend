from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from soundbridge.adapter.inbound.api import soundbridge_router
from soundbridge.adapter.outbound.pg.db_init import create_soundbridge_tables
from soundbridge.infrastructure.database import dispose_engine
from soundbridge.infrastructure.secret_manager import keymaker
from soundbridge.infrastructure.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    keymaker.bootstrap()
    await create_soundbridge_tables()
    yield
    await dispose_engine()


app = FastAPI(
    title="SoundBridge API",
    version="5.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(soundbridge_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/db")
async def health_db() -> dict[str, str]:
    from sqlalchemy import text

    from soundbridge.infrastructure.config import is_database_configured
    from soundbridge.infrastructure.database import _ensure_engine, engine

    if not is_database_configured():
        return {"status": "error", "detail": "DATABASE_URL is not set"}
    try:
        _ensure_engine()
        assert engine is not None
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "db connected"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
