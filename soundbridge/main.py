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
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(soundbridge_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
