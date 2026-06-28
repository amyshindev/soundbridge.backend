"""국악음원(TM) 학습데이터 → gugak_tracks 적재 스크립트.

원천데이터(*_M*.json) + 라벨링데이터(*_P*.json) 쌍을 읽어 DB에 upsert 합니다.

Usage:
  cd backend
  python scripts/load_tm_tracks.py --dry-run --limit 5
  python scripts/load_tm_tracks.py --data-root "C:/Users/hi/Desktop/국악음원_sample/test"
  python scripts/load_tm_tracks.py --force

Docker:
  docker compose exec api python scripts/load_tm_tracks.py --data-root /data/audio/..
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg
except ModuleNotFoundError as e:
    raise SystemExit(
        "psycopg 가 설치되어 있지 않습니다.\n"
        "  cd backend && pip install -r requirements.txt"
    ) from e

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPT_DIR))

from soundbridge.adapter.outbound.pg.tm_schema_ddl import apply_tm_schema_sync
from soundbridge.domain.value_objects.bpm_vo import parse_tm_bpm
from soundbridge.domain.value_objects.emotion_vo import map_tm_emotion_tags
from soundbridge.domain.value_objects.instrument_vo import infer_instrument_from_tm_genre
from soundbridge.domain.value_objects.jangdan_vo import extract_jangdan_from_caption
from soundbridge.domain.value_objects.license_vo import parse_tm_license_rights
from tm_cue_points import build_cue_points_from_annotation


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


def labeling_path_for(meta_path: Path, data_root: Path) -> Path | None:
    label_root = data_root / "라벨링데이터"
    p_name = meta_path.name.replace("_M", "_P")

    try:
        rel = meta_path.relative_to(data_root / "원천데이터")
        candidate = label_root / rel.parent / p_name
        if candidate.is_file():
            return candidate
    except ValueError:
        pass

    stem = meta_path.stem
    if "_M" in stem:
        prefix, serial = stem.rsplit("_M", 1)
        p_stem = f"{prefix}_P{serial}"
        matches = sorted(label_root.rglob(f"{p_stem}.json"))
        if matches:
            return matches[0]

    return None


def iter_meta_files(data_root: Path) -> list[Path]:
    source_root = data_root / "원천데이터"
    if not source_root.is_dir():
        raise FileNotFoundError(f"원천데이터 폴더가 없습니다: {source_root}")
    return sorted(source_root.rglob("*_M*.json"))


def parse_track_record(meta_path: Path, data_root: Path) -> dict | None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    contents = meta.get("contents") or {}
    identifier = (meta.get("identifier") or meta_path.stem).strip()
    if not identifier:
        return None

    label_path = labeling_path_for(meta_path, data_root)
    caption_ko = ""
    caption_en = ""
    cue_points: list[dict] = []
    if label_path:
        label = json.loads(label_path.read_text(encoding="utf-8"))
        annotation = label.get("annotation") or {}
        caption_ko = (annotation.get("caption_ko") or "").strip()
        caption_en = (annotation.get("caption_en") or "").strip()
        cue_points = build_cue_points_from_annotation(annotation)

    jangdan_name, jangdan_raw = extract_jangdan_from_caption(caption_ko)
    whole_emotions = contents.get("whole_emotions") or []
    whole_tones = contents.get("whole_tones") or []

    return {
        "source_identifier": identifier,
        "title": (meta.get("title") or identifier).strip()[:200],
        "artist": (contents.get("performer") or "미상").strip()[:100],
        "instrument": infer_instrument_from_tm_genre(contents.get("genre_mclsf") or ""),
        "jangdan_name": jangdan_name,
        "jangdan_raw": jangdan_raw,
        "bpm": parse_tm_bpm(contents.get("tempo") or ""),
        "audio_url": (contents.get("file_name") or "").strip(),
        "public_license_type": parse_tm_license_rights(meta.get("rights") or "").value,
        "description_ko": caption_ko,
        "description_en": caption_en,
        "classification_code": (meta.get("classification_code") or "").strip()[:20],
        "genre_lclsf": (contents.get("genre_lclsf") or "").strip()[:50],
        "genre_mclsf": (contents.get("genre_mclsf") or "").strip()[:50],
        "genre_sclsf": (contents.get("genre_sclsf") or "").strip()[:50],
        "time_signature": (contents.get("timeSignature") or "").strip()[:20],
        "tempo_label": (contents.get("tempo") or "").strip()[:20],
        "original_track_code": (contents.get("original_track_code") or "").strip()[:50],
        "whole_emotions": whole_emotions,
        "whole_tones": whole_tones,
        "emotion_tags": map_tm_emotion_tags(whole_emotions),
        "cue_points": cue_points,
    }


def upsert_track(conn, record: dict, *, force: bool, clear_embeddings: bool) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM gugak_tracks WHERE source_identifier = %s",
            (record["source_identifier"],),
        )
        existing = cur.fetchone()

        now = datetime.now(timezone.utc)
        emotions_json = json.dumps(record["whole_emotions"], ensure_ascii=False)
        tones_json = json.dumps(record["whole_tones"], ensure_ascii=False)
        cues_json = json.dumps(record.get("cue_points") or [], ensure_ascii=False)

        if existing:
            track_id = existing[0]
            if not force:
                return "skip"
            embed_clause = ", embedding = NULL" if clear_embeddings else ""
            cur.execute(
                f"""
                UPDATE gugak_tracks SET
                    title = %s, artist = %s, instrument = %s,
                    jangdan_name = %s, jangdan_raw = %s, bpm = %s,
                    cue_points = %s::jsonb,
                    audio_url = %s, public_license_type = %s,
                    description_ko = %s, description_en = %s,
                    classification_code = %s,
                    genre_lclsf = %s, genre_mclsf = %s, genre_sclsf = %s,
                    time_signature = %s, tempo_label = %s,
                    original_track_code = %s,
                    whole_emotions = %s::jsonb, whole_tones = %s::jsonb
                    {embed_clause}
                WHERE id = %s
                """,
                (
                    record["title"],
                    record["artist"],
                    record["instrument"],
                    record["jangdan_name"],
                    record["jangdan_raw"],
                    record["bpm"],
                    cues_json,
                    record["audio_url"],
                    record["public_license_type"],
                    record["description_ko"],
                    record["description_en"],
                    record["classification_code"],
                    record["genre_lclsf"],
                    record["genre_mclsf"],
                    record["genre_sclsf"],
                    record["time_signature"],
                    record["tempo_label"],
                    record["original_track_code"],
                    emotions_json,
                    tones_json,
                    track_id,
                ),
            )
            cur.execute("DELETE FROM track_emotion_tags WHERE track_id = %s", (track_id,))
            action = "update"
        else:
            track_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO gugak_tracks (
                    id, title, artist, instrument, jangdan_name, jangdan_raw,
                    bpm, cue_points, audio_url, public_license_type,
                    description_ko, description_en, embedding, created_at,
                    source_identifier, classification_code,
                    genre_lclsf, genre_mclsf, genre_sclsf,
                    time_signature, tempo_label, original_track_code,
                    whole_emotions, whole_tones
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s::jsonb, %s, %s,
                    %s, %s, NULL, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s::jsonb, %s::jsonb
                )
                """,
                (
                    track_id,
                    record["title"],
                    record["artist"],
                    record["instrument"],
                    record["jangdan_name"],
                    record["jangdan_raw"],
                    record["bpm"],
                    cues_json,
                    record["audio_url"],
                    record["public_license_type"],
                    record["description_ko"],
                    record["description_en"],
                    now,
                    record["source_identifier"],
                    record["classification_code"],
                    record["genre_lclsf"],
                    record["genre_mclsf"],
                    record["genre_sclsf"],
                    record["time_signature"],
                    record["tempo_label"],
                    record["original_track_code"],
                    emotions_json,
                    tones_json,
                ),
            )
            action = "insert"

        for order, tag in enumerate(record["emotion_tags"]):
            cur.execute(
                """
                INSERT INTO track_emotion_tags (id, track_id, emotion_tag, sort_order)
                VALUES (%s, %s, %s, %s)
                """,
                (uuid.uuid4(), track_id, tag, order),
            )

    return action


def run(data_root: Path, *, dry_run: bool, limit: int | None, force: bool, clear_embeddings: bool) -> None:
    load_env_files()
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url and not dry_run:
        raise RuntimeError("DATABASE_URL 이 .env 에 없습니다.")

    meta_files = iter_meta_files(data_root)
    if limit:
        meta_files = meta_files[:limit]

    print(f"data_root={data_root} targets={len(meta_files)} dry_run={dry_run} force={force}")

    inserted = updated = skipped = failed = 0

    if dry_run:
        for path in meta_files:
            try:
                record = parse_track_record(path, data_root)
                if not record:
                    failed += 1
                    continue
                print(
                    f"[DRY] {record['source_identifier']} | {record['title']} | "
                    f"{record['genre_lclsf']}/{record['genre_mclsf']} | "
                    f"장단={record['jangdan_raw'] or record['jangdan_name']} | "
                    f"cues={len(record.get('cue_points') or [])}"
                )
                inserted += 1
            except Exception as e:
                failed += 1
                print(f"[DRY FAIL] {path.name}: {e}", file=sys.stderr)
        print(f"done: preview={inserted}, failed={failed}")
        return

    conn = psycopg.connect(normalize_db_url(db_url))
    try:
        apply_tm_schema_sync(conn)
        print("[schema] TM columns ready")

        for path in meta_files:
            try:
                record = parse_track_record(path, data_root)
                if not record:
                    failed += 1
                    continue
                action = upsert_track(
                    conn, record, force=force, clear_embeddings=clear_embeddings
                )
                conn.commit()
                if action == "insert":
                    inserted += 1
                    print(f"[+] {record['source_identifier']} {record['title']}")
                elif action == "update":
                    updated += 1
                    print(f"[~] {record['source_identifier']} {record['title']}")
                else:
                    skipped += 1
            except Exception as e:
                conn.rollback()
                failed += 1
                print(f"[FAIL] {path.name}: {e}", file=sys.stderr)
    finally:
        conn.close()

    print(f"done: inserted={inserted}, updated={updated}, skipped={skipped}, failed={failed}")


def main() -> None:
    load_env_files()
    default_root = os.getenv(
        "TM_DATA_ROOT",
        str(Path.home() / "Desktop" / "국악음원_sample" / "test"),
    )

    parser = argparse.ArgumentParser(description="Load 국악음원(TM) JSON into gugak_tracks")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(default_root),
        help="test/ 폴더 (원천데이터 + 라벨링데이터 상위)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true", help="기존 source_identifier 행도 갱신")
    args = parser.parse_args()

    run(
        args.data_root.resolve(),
        dry_run=args.dry_run,
        limit=args.limit or None,
        force=args.force,
    )


if __name__ == "__main__":
    main()
