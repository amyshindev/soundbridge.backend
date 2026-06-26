"""구 국악원 API 시대 행(source_identifier IS NULL) 삭제.

Usage:
  cd backend
  python scripts/purge_legacy_tracks.py --dry-run
  python scripts/purge_legacy_tracks.py

Docker:
  docker compose exec api python scripts/purge_legacy_tracks.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import psycopg
except ModuleNotFoundError as e:
    raise SystemExit("psycopg 가 필요합니다: pip install -r requirements.txt") from e

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent


def load_env_files() -> None:
    for path in (BACKEND_DIR / ".env", ROOT_DIR / ".env"):
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


def count_legacy(conn) -> tuple[int, int, int]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM gugak_tracks WHERE source_identifier IS NULL"
        )
        legacy_tracks = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FROM match_logs ml
            JOIN gugak_tracks t ON t.id = ml.matched_track_id
            WHERE t.source_identifier IS NULL
            """
        )
        legacy_logs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM gugak_tracks")
        total = cur.fetchone()[0]
    return legacy_tracks, legacy_logs, total


def purge(conn, *, dry_run: bool) -> None:
    legacy_tracks, legacy_logs, total = count_legacy(conn)
    tm_rows = total - legacy_tracks

    print(f"gugak_tracks total={total} tm={tm_rows} legacy={legacy_tracks}")
    print(f"match_logs referencing legacy tracks={legacy_logs}")

    if legacy_tracks == 0:
        print("삭제할 legacy 행이 없습니다.")
        return

    if dry_run:
        print("[DRY-RUN] legacy gugak_tracks 및 관련 match_logs 가 삭제됩니다.")
        return

    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM match_logs
            WHERE matched_track_id IN (
                SELECT id FROM gugak_tracks WHERE source_identifier IS NULL
            )
            """
        )
        deleted_logs = cur.rowcount
        cur.execute("DELETE FROM gugak_tracks WHERE source_identifier IS NULL")
        deleted_tracks = cur.rowcount
    conn.commit()

    print(f"deleted: gugak_tracks={deleted_tracks}, match_logs={deleted_logs}")

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM gugak_tracks WHERE source_identifier IS NULL")
        remaining = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM gugak_tracks WHERE embedding IS NOT NULL")
        embedded = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM gugak_tracks")
        new_total = cur.fetchone()[0]

    print(f"after: total={new_total}, embedded={embedded}, legacy_remaining={remaining}")


def main() -> None:
    load_env_files()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise SystemExit("DATABASE_URL 이 .env 에 없습니다.")

    parser = argparse.ArgumentParser(description="Purge legacy gugak_tracks (no source_identifier)")
    parser.add_argument("--dry-run", action="store_true", help="삭제 대상만 출력")
    args = parser.parse_args()

    conn = psycopg.connect(normalize_db_url(db_url))
    try:
        purge(conn, dry_run=args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
