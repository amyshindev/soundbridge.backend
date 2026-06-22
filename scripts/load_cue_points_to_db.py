"""cue_points_500_v2.csv -> NeonDB 적재 스크립트.

INSERT 순서 (FK 의존성):
  1. jangdan
  2. gugak_tracks
  3. track_emotion_tags

메타데이터는 gugak_500_normalized.csv 를 phrase_cd 기준으로 조인하고,
없으면 cue CSV note 필드(악기/장단/태그)를 fallback 으로 사용합니다.

Usage:
  cd backend
  ..\\venv\\Scripts\\python.exe scripts\\load_cue_points_to_db.py --dry-run
  ..\\venv\\Scripts\\python.exe scripts\\load_cue_points_to_db.py
  ..\\venv\\Scripts\\python.exe scripts\\load_cue_points_to_db.py --check
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

DEFAULT_CUE_CSV = SCRIPT_DIR / "cue_points_500_v2.csv"
DEFAULT_NORMALIZED_CSV = SCRIPT_DIR / "gugak_500_normalized.csv"

VALID_JANGDAN = {"자진모리", "중모리", "굿거리", "휘모리", "세마치", "엇모리"}
VALID_EMOTIONS = {"신남", "서정", "웅장", "슬픔", "신비", "차분"}
VALID_INSTRUMENTS = {"가야금", "거문고", "대금", "해금", "피리", "아쟁", "장구", "소고"}

JANGDAN_LOOP_UNITS: dict[str, int] = {
    "자진모리": 12,
    "중모리": 12,
    "굿거리": 12,
    "휘모리": 4,
    "세마치": 6,
    "엇모리": 10,
}

INSTRUMENT_ALIASES = {
    "소금": "대금",
}

NOTE_META_RE = re.compile(
    r"악기=(?P<instrument>[^;]+);\s*장단=(?P<jangdan>[^;]+);\s*태그=(?P<tags>[^;]+)"
)


def load_env() -> str:
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(ROOT_DIR / ".env")
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL 이 .env 에 없습니다.")
    return db_url


def normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    if url.startswith("postgresql+psycopg_async://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg_async://")
    return url


def stable_track_id(phrase_cd: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"soundbridge:phrase:{phrase_cd}")


def parse_float(value: str) -> float:
    return round(float(value.strip()), 2)


def parse_note_meta(note: str) -> dict[str, str]:
    match = NOTE_META_RE.search(note or "")
    if not match:
        return {}
    return {
        "instrument": match.group("instrument").strip(),
        "jangdan": match.group("jangdan").strip(),
        "emotion_tags": match.group("tags").strip(),
    }


def parse_emotion_tags(raw: str) -> list[str]:
    tags = [t.strip() for t in (raw or "").split("|") if t.strip()]
    valid = [t for t in tags if t in VALID_EMOTIONS]
    if valid:
        return valid
    return ["차분"]


def normalize_instrument(name: str) -> str:
    value = INSTRUMENT_ALIASES.get(name.strip(), name.strip())
    if value not in VALID_INSTRUMENTS:
        raise ValueError(f"지원하지 않는 악기: {name}")
    return value


def normalize_jangdan(name: str) -> str:
    value = name.strip()
    if value not in VALID_JANGDAN:
        raise ValueError(f"지원하지 않는 장단: {name}")
    return value


def infer_bpm(meta: dict[str, str]) -> int:
    for key in ("rhythm", "beat"):
        raw = meta.get(key, "")
        m = re.search(r"\d+", raw)
        if m:
            n = int(m.group())
            if 40 <= n <= 200:
                return n
            if 1 <= n <= 20:
                return max(60, min(180, n * 18))
    return 90


def build_cue_points(row: dict[str, str]) -> list[dict[str, object]]:
    return [
        {"time_sec": parse_float(row["A_sec"]), "label": "A", "emotion": "에너지 피크"},
        {"time_sec": parse_float(row["B_sec"]), "label": "B", "emotion": "감성 해소"},
        {"time_sec": parse_float(row["C_sec"]), "label": "C", "emotion": "루프 시작"},
    ]


def load_normalized_index(path: Path) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            phrase_cd = (row.get("phrase_cd") or "").strip()
            if phrase_cd:
                index[phrase_cd] = row
    return index


def map_record(cue_row: dict[str, str], meta_row: dict[str, str] | None) -> dict:
    phrase_cd = cue_row["phrase_cd"].strip()
    note_meta = parse_note_meta(cue_row.get("note", ""))
    meta = meta_row or {}

    instrument = normalize_instrument(
        meta.get("instrument_name") or note_meta.get("instrument") or "가야금"
    )
    jangdan = normalize_jangdan(
        meta.get("jangdan_name") or note_meta.get("jangdan") or "중모리"
    )
    emotion_tags = parse_emotion_tags(
        meta.get("emotion_tags") or note_meta.get("emotion_tags") or ""
    )

    title = (cue_row.get("title") or meta.get("phrs_nm_kor") or phrase_cd).strip()
    artist = (meta.get("singer") or "국립국악원").strip()
    audio_url = (cue_row.get("audio_url") or meta.get("wav_file_path") or "").strip()
    if not audio_url:
        raise ValueError(f"audio_url 없음: {phrase_cd}")

    description_ko = (meta.get("phrs_desc_kor") or title).strip()
    description_en = (meta.get("phrs_desc_eng") or meta.get("phrs_nm_eng") or title).strip()

    return {
        "id": stable_track_id(phrase_cd),
        "phrase_cd": phrase_cd,
        "title": title,
        "artist": artist,
        "instrument": instrument,
        "jangdan_name": jangdan,
        "bpm": infer_bpm(meta),
        "cue_points": build_cue_points(cue_row),
        "audio_url": audio_url,
        "public_license_type": "KOGL_1",
        "description_ko": description_ko,
        "description_en": description_en,
        "created_at": datetime.now(timezone.utc),
        "emotion_tags": emotion_tags,
    }


def load_records(
    cue_csv: Path,
    normalized_csv: Path,
    limit: int | None = None,
) -> list[dict]:
    meta_index = load_normalized_index(normalized_csv) if normalized_csv.exists() else {}
    records: list[dict] = []

    with cue_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phrase_cd = (row.get("phrase_cd") or "").strip()
            if not phrase_cd:
                continue
            records.append(map_record(row, meta_index.get(phrase_cd)))
            if limit and len(records) >= limit:
                break
    return records


def get_existing_audio_urls(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT audio_url FROM gugak_tracks")
        return {row[0] for row in cur.fetchall()}


def ensure_jangdan(conn, jangdan_names: set[str], dry_run: bool) -> int:
    rows = [(name, JANGDAN_LOOP_UNITS[name]) for name in sorted(jangdan_names)]
    if dry_run:
        print(f"[DRY] jangdan upsert: {len(rows)}")
        return len(rows)

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO jangdan (name, loop_unit_beats)
            VALUES (%s, %s)
            ON CONFLICT (name) DO NOTHING
            """,
            rows,
        )
    conn.commit()
    print(f"[jangdan] ensured {len(rows)} rows")
    return len(rows)


def insert_tracks_and_tags(conn, tracks: list[dict], dry_run: bool) -> tuple[int, int]:
    if not tracks:
        return 0, 0

    if dry_run:
        print(f"[DRY] gugak_tracks insert: {len(tracks)}")
        tag_count = sum(len(t["emotion_tags"]) for t in tracks)
        print(f"[DRY] track_emotion_tags insert: {tag_count}")
        return len(tracks), tag_count

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO gugak_tracks (
                id, title, artist, instrument, jangdan_name, bpm,
                cue_points, audio_url, public_license_type,
                description_ko, description_en, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
            """,
            [
                (
                    str(t["id"]),
                    t["title"],
                    t["artist"],
                    t["instrument"],
                    t["jangdan_name"],
                    t["bpm"],
                    json.dumps(t["cue_points"], ensure_ascii=False),
                    t["audio_url"],
                    t["public_license_type"],
                    t["description_ko"],
                    t["description_en"],
                    t["created_at"],
                )
                for t in tracks
            ],
        )

        tag_rows = []
        for track in tracks:
            for order, tag in enumerate(track["emotion_tags"]):
                tag_rows.append((str(uuid.uuid4()), str(track["id"]), tag, order))

        if tag_rows:
            cur.executemany(
                """
                INSERT INTO track_emotion_tags (id, track_id, emotion_tag, sort_order)
                VALUES (%s, %s, %s, %s)
                """,
                tag_rows,
            )

    conn.commit()
    return len(tracks), len(tag_rows)


def check_db(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM jangdan")
        jangdan_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM gugak_tracks")
        track_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM track_emotion_tags")
        tag_count = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FROM gugak_tracks
            WHERE cue_points IS NOT NULL
              AND jsonb_array_length(cue_points) >= 3
            """
        )
        cue_count = cur.fetchone()[0]
    print(f"jangdan: {jangdan_count}")
    print(f"gugak_tracks: {track_count}")
    print(f"track_emotion_tags: {tag_count}")
    print(f"tracks with cue_points>=3: {cue_count}")


def run(
    cue_csv: Path,
    normalized_csv: Path,
    dry_run: bool,
    limit: int | None,
) -> None:
    db_url = load_env()
    records = load_records(cue_csv, normalized_csv, limit=limit)
    if not records:
        print("적재할 레코드가 없습니다.")
        return

    jangdan_names = {r["jangdan_name"] for r in records}
    inst_counter = Counter(r["instrument"] for r in records)
    jangdan_counter = Counter(r["jangdan_name"] for r in records)

    print(f"mapped records: {len(records)}")
    print(f"instruments: {dict(inst_counter)}")
    print(f"jangdans: {dict(jangdan_counter)}")

    if dry_run:
        ensure_jangdan(None, jangdan_names, dry_run=True)
        insert_tracks_and_tags(None, records, dry_run=True)
        sample = records[0]
        print("\n[sample]")
        print(json.dumps({k: v for k, v in sample.items() if k != "created_at"}, ensure_ascii=False, indent=2, default=str))
        return

    conn = psycopg.connect(normalize_db_url(db_url))
    try:
        existing_urls = get_existing_audio_urls(conn)
        to_insert = [r for r in records if r["audio_url"] not in existing_urls]
        skipped = len(records) - len(to_insert)

        ensure_jangdan(conn, jangdan_names, dry_run=False)
        inserted, tags = insert_tracks_and_tags(conn, to_insert, dry_run=False)
        print(f"[done] inserted_tracks={inserted}, inserted_tags={tags}, skipped={skipped}")
        check_db(conn)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="cue_points CSV -> NeonDB loader")
    parser.add_argument("--cue-csv", type=Path, default=DEFAULT_CUE_CSV)
    parser.add_argument("--normalized-csv", type=Path, default=DEFAULT_NORMALIZED_CSV)
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 매핑만 확인")
    parser.add_argument("--limit", type=int, default=0, help="적재 건수 제한 (0=전체)")
    parser.add_argument("--check", action="store_true", help="DB 통계만 출력")
    args = parser.parse_args()

    if args.check:
        conn = psycopg.connect(normalize_db_url(load_env()))
        try:
            check_db(conn)
        finally:
            conn.close()
        return

    if not args.cue_csv.exists():
        raise FileNotFoundError(f"cue CSV not found: {args.cue_csv}")

    run(
        cue_csv=args.cue_csv.resolve(),
        normalized_csv=args.normalized_csv.resolve(),
        dry_run=args.dry_run,
        limit=args.limit or None,
    )


if __name__ == "__main__":
    main()
