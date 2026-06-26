"""TM 라벨링에서 cue_points 만 DB에 반영 (임베딩 유지).

Usage:
  cd backend
  python scripts/backfill_tm_cue_points.py --dry-run --limit 5
  python scripts/backfill_tm_cue_points.py --force
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import psycopg
except ModuleNotFoundError as e:
    raise SystemExit("psycopg 가 필요합니다.") from e

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from load_tm_tracks import (  # noqa: E402
    iter_meta_files,
    labeling_path_for,
    load_env_files,
    normalize_db_url,
)
from tm_cue_points import build_cue_points_from_annotation  # noqa: E402


def parse_cue_points(meta_path: Path, data_root: Path) -> list[dict]:
    label_path = labeling_path_for(meta_path, data_root)
    if not label_path:
        return []
    label = json.loads(label_path.read_text(encoding="utf-8"))
    return build_cue_points_from_annotation(label.get("annotation") or {})


def run(data_root: Path, *, dry_run: bool, limit: int | None, force: bool) -> None:
    load_env_files()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url and not dry_run:
        raise RuntimeError("DATABASE_URL 이 .env 에 없습니다.")

    meta_files = iter_meta_files(data_root)
    if limit:
        meta_files = meta_files[:limit]

    updated = skipped = empty = failed = 0

    if dry_run:
        for path in meta_files:
            meta = json.loads(path.read_text(encoding="utf-8"))
            sid = meta.get("identifier") or path.stem
            cues = parse_cue_points(path, data_root)
            print(f"[DRY] {sid} cues={len(cues)} {cues}")
            if cues:
                updated += 1
            else:
                empty += 1
        print(f"done: with_cues={updated}, empty={empty}")
        return

    conn = psycopg.connect(normalize_db_url(db_url))
    try:
        for path in meta_files:
            try:
                meta = json.loads(path.read_text(encoding="utf-8"))
                sid = (meta.get("identifier") or path.stem).strip()
                cues = parse_cue_points(path, data_root)
                cues_json = json.dumps(cues, ensure_ascii=False)

                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, cue_points FROM gugak_tracks WHERE source_identifier = %s",
                        (sid,),
                    )
                    row = cur.fetchone()
                    if not row:
                        skipped += 1
                        continue
                    track_id, existing = row
                    if not force and existing and len(existing) >= 3:
                        skipped += 1
                        continue
                    if not cues:
                        empty += 1
                        continue
                    cur.execute(
                        "UPDATE gugak_tracks SET cue_points = %s::jsonb WHERE id = %s",
                        (cues_json, track_id),
                    )
                conn.commit()
                updated += 1
                print(f"[cue] {sid} ({len(cues)} markers)")
            except Exception as e:
                conn.rollback()
                failed += 1
                print(f"[FAIL] {path.name}: {e}", file=sys.stderr)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE cue_points IS NOT NULL AND jsonb_array_length(cue_points) >= 3
                    ) AS with_cue
                FROM gugak_tracks
                WHERE source_identifier IS NOT NULL
                """
            )
            total, with_cue = cur.fetchone()
    finally:
        conn.close()

    print(
        f"done: updated={updated}, skipped={skipped}, no_label_cues={empty}, "
        f"failed={failed}, db_with_cue>={total} tracks / {with_cue} have 3+ cues"
    )


def main() -> None:
    default_root = os.getenv(
        "TM_DATA_ROOT",
        str(Path.home() / "Desktop" / "국악음원_sample" / "test"),
    )
    parser = argparse.ArgumentParser(description="Backfill cue_points from TM labeling JSON")
    parser.add_argument("--data-root", type=Path, default=Path(default_root))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="기존 cue_points 도 덮어씀")
    args = parser.parse_args()

    run(
        args.data_root.resolve(),
        dry_run=args.dry_run,
        limit=args.limit or None,
        force=args.force,
    )


if __name__ == "__main__":
    main()
