"""Neon DB 스키마 점검 (일회성)."""
import asyncio
import sys

if sys.platform.startswith("win"):
    import asyncio as _asyncio

    _asyncio.set_event_loop_policy(_asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text

from soundbridge.infrastructure import database
from soundbridge.infrastructure.config import is_database_configured


async def main() -> None:
    if not is_database_configured():
        print("DATABASE_URL not set")
        return
    database._ensure_engine()
    assert database.engine is not None

    async with database.engine.connect() as conn:
        tables = await conn.execute(
            text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' ORDER BY table_name
            """)
        )
        print("=== tables ===")
        for row in tables:
            print(f"  {row[0]}")

        cols = await conn.execute(
            text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'gugak_tracks'
                ORDER BY ordinal_position
            """)
        )
        print("\n=== gugak_tracks columns ===")
        for row in cols:
            print(f"  {row[0]}: {row[1]}")

        jangdan = await conn.execute(text("SELECT COUNT(*) FROM jangdan"))
        tracks = await conn.execute(text("SELECT COUNT(*) FROM gugak_tracks"))
        print(f"\n=== row counts ===")
        print(f"  jangdan: {jangdan.scalar()}")
        print(f"  gugak_tracks: {tracks.scalar()}")

        version = await conn.execute(text("SELECT version_num FROM alembic_version"))
        print(f"\n=== alembic_version ===")
        for row in version:
            print(f"  {row[0]}")


if __name__ == "__main__":
    asyncio.run(main())
