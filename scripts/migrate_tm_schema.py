"""gugak_tracks TM 스키마 컬럼 추가 (API 없이 단독 실행 가능).

Usage:
  cd backend
  python scripts/migrate_tm_schema.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import psycopg
except ModuleNotFoundError as e:
    raise SystemExit("psycopg 가 필요합니다: pip install -r requirements.txt") from e

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from soundbridge.adapter.outbound.pg.tm_schema_ddl import TM_COLUMN_DDLS, apply_tm_schema_sync


def load_env_files() -> None:
    root = BACKEND_DIR.parent
    for path in (BACKEND_DIR / ".env", root / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    if url.startswith("postgresql+psycopg_async://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg_async://")
    return url


def main() -> None:
    load_env_files()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise SystemExit("DATABASE_URL 이 .env 에 없습니다.")

    conn = psycopg.connect(normalize_db_url(db_url))
    try:
        apply_tm_schema_sync(conn)
        print(f"OK: applied {len(TM_COLUMN_DDLS)} DDL statements")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
