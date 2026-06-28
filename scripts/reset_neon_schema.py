"""Neon PostgreSQL 스키마 제거 후 alembic 001_init 재적용."""
import asyncio
import subprocess
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text

from soundbridge.infrastructure import database
from soundbridge.infrastructure.config import is_database_configured

DROP_ORDER = [
    "match_logs",
    "track_emotion_tags",
    "gugak_tracks",
    "jangdan",
    "alembic_version",
]


async def reset_schema() -> None:
    if not is_database_configured():
        raise RuntimeError("DATABASE_URL is not set")
    database._ensure_engine()
    assert database.engine is not None

    async with database.engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        for table in DROP_ORDER:
            await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
    await database.dispose_engine()
    print("Dropped old tables.")


def run_upgrade() -> None:
    backend = Path(__file__).resolve().parent.parent
    venv_python = backend.parent / "venv" / "Scripts" / "python.exe"
    subprocess.run(
        [str(venv_python), "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=backend,
        check=True,
    )
    print("Alembic upgrade head complete.")


if __name__ == "__main__":
    asyncio.run(reset_schema())
    run_upgrade()
