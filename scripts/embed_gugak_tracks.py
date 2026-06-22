"""gugak_tracks 임베딩 배치 생성 스크립트.

title, artist, instrument, jangdan_name, track_emotion_tags, description_ko 를
합쳐 Gemini Embedding API 로 벡터를 만들고 embedding 컬럼에 저장합니다.

레이트리밋: 기본 1초당 5건 (5건 처리 후 1초 대기).

Usage:
  cd backend
  ..\\venv\\Scripts\\python.exe scripts\\embed_gugak_tracks.py --dry-run --limit 5
  ..\\venv\\Scripts\\python.exe scripts\\embed_gugak_tracks.py
  ..\\venv\\Scripts\\python.exe scripts\\embed_gugak_tracks.py --clear-legacy-embeddings
  ..\\venv\\Scripts\\python.exe scripts\\embed_gugak_tracks.py --force
  ..\\venv\\Scripts\\python.exe scripts\\embed_gugak_tracks.py --check
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import google.generativeai as genai
import psycopg
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

EMBEDDING_DIM = 1536
DEFAULT_MODEL = "models/gemini-embedding-001"
DEFAULT_BATCH_SIZE = 5
DEFAULT_BATCH_INTERVAL_SEC = 1.0


def load_config() -> tuple[str, str]:
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(ROOT_DIR / ".env")

    db_url = os.getenv("DATABASE_URL", "").strip()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL 이 .env 에 없습니다.")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 가 .env 에 없습니다.")
    return db_url, api_key


def normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    if url.startswith("postgresql+psycopg_async://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg_async://")
    return url


def build_embed_text(
    title: str,
    artist: str,
    instrument: str,
    jangdan_name: str,
    emotion_tags: list[str],
    description_ko: str,
) -> str:
    tags = ", ".join(emotion_tags) if emotion_tags else "없음"
    return (
        f"제목: {title}\n"
        f"아티스트: {artist}\n"
        f"악기: {instrument}\n"
        f"장단: {jangdan_name}\n"
        f"감성: {tags}\n"
        f"설명: {description_ko}"
    )


def fetch_tracks(
    conn,
    only_missing: bool,
    limit: int | None,
    cue_only: bool,
) -> list[dict]:
    clauses: list[str] = []
    if only_missing:
        clauses.append("t.embedding IS NULL")
    if cue_only:
        clauses.append(
            "t.cue_points IS NOT NULL AND jsonb_array_length(t.cue_points) >= 3"
        )
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    query = f"""
        SELECT
            t.id,
            t.title,
            t.artist,
            t.instrument,
            t.jangdan_name,
            t.description_ko,
            COALESCE(
                array_agg(tet.emotion_tag ORDER BY tet.sort_order)
                FILTER (WHERE tet.emotion_tag IS NOT NULL),
                ARRAY[]::varchar[]
            ) AS emotion_tags
        FROM gugak_tracks t
        LEFT JOIN track_emotion_tags tet ON tet.track_id = t.id
        {where}
        GROUP BY t.id, t.title, t.artist, t.instrument, t.jangdan_name, t.description_ko,
                 t.cue_points, t.created_at
        ORDER BY
            CASE
                WHEN t.cue_points IS NOT NULL AND jsonb_array_length(t.cue_points) >= 3
                THEN 0 ELSE 1
            END,
            t.created_at DESC,
            t.title
        {limit_sql}
    """

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "title": row[1],
            "artist": row[2],
            "instrument": row[3],
            "jangdan_name": row[4],
            "description_ko": row[5] or "",
            "emotion_tags": list(row[6] or []),
        }
        for row in rows
    ]


def embed_text(api_key: str, model: str, text: str) -> list[float]:
    genai.configure(api_key=api_key)
    result = genai.embed_content(
        model=model,
        content=text,
        task_type="retrieval_document",
        output_dimensionality=EMBEDDING_DIM,
    )
    embedding = result.get("embedding")
    if not embedding:
        raise RuntimeError("Empty embedding response")
    if len(embedding) != EMBEDDING_DIM:
        raise RuntimeError(f"Unexpected embedding dim: {len(embedding)}")
    return list(embedding)


def save_embedding(conn, track_id, embedding: list[float]) -> None:
    vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE gugak_tracks SET embedding = %s::vector WHERE id = %s",
            (vec_literal, str(track_id)),
        )


def check_db(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM gugak_tracks")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM gugak_tracks WHERE embedding IS NOT NULL")
        embedded = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM gugak_tracks WHERE embedding IS NULL")
        missing = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FROM gugak_tracks
            WHERE cue_points IS NOT NULL AND jsonb_array_length(cue_points) >= 3
            """
        )
        with_cue = cur.fetchone()[0]
        cur.execute(
            """
            SELECT COUNT(*) FROM gugak_tracks
            WHERE cue_points IS NOT NULL AND jsonb_array_length(cue_points) >= 3
              AND embedding IS NULL
            """
        )
        cue_missing = cur.fetchone()[0]
    print(f"gugak_tracks total: {total}")
    print(f"with cue_points (>=3): {with_cue}")
    print(f"embedded: {embedded}")
    print(f"missing: {missing}")
    print(f"cue tracks still missing embedding: {cue_missing}")


def clear_legacy_embeddings(conn) -> int:
    """cue_points 없는 구 데이터의 embedding 을 비워 DISCOVER 풀에서 제외."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE gugak_tracks
            SET embedding = NULL
            WHERE embedding IS NOT NULL
              AND (cue_points IS NULL OR jsonb_array_length(cue_points) < 3)
            """
        )
        cleared = cur.rowcount
    conn.commit()
    return cleared


def run(
    dry_run: bool,
    limit: int | None,
    force: bool,
    cue_only: bool,
    clear_legacy: bool,
    batch_size: int,
    batch_interval_sec: float,
    model: str,
) -> None:
    db_url, api_key = load_config()
    conn = psycopg.connect(normalize_db_url(db_url))

    try:
        if clear_legacy and not dry_run:
            cleared = clear_legacy_embeddings(conn)
            print(f"[legacy] cleared embeddings on {cleared} rows (no cue_points)")

        tracks = fetch_tracks(
            conn,
            only_missing=not force,
            limit=limit,
            cue_only=cue_only,
        )
        total = len(tracks)
        if total == 0:
            print("처리할 트랙이 없습니다.")
            check_db(conn)
            return

        print(
            f"targets: {total} (force={force}, cue_only={cue_only}, batch={batch_size}/sec)"
        )

        success = 0
        failed = 0
        started = time.time()

        for idx, track in enumerate(tracks, start=1):
            text = build_embed_text(
                title=track["title"],
                artist=track["artist"],
                instrument=track["instrument"],
                jangdan_name=track["jangdan_name"],
                emotion_tags=track["emotion_tags"],
                description_ko=track["description_ko"],
            )

            if dry_run:
                print(f"[DRY {idx}/{total}] {track['id']} | {track['title']}")
                print(text[:120].replace("\n", " | ") + ("..." if len(text) > 120 else ""))
                success += 1
            else:
                try:
                    vector = embed_text(api_key, model, text)
                    save_embedding(conn, track["id"], vector)
                    conn.commit()
                    success += 1
                    print(f"[{idx}/{total}] embedded {track['title']}")
                except Exception as e:
                    conn.rollback()
                    failed += 1
                    print(f"[{idx}/{total}] FAILED {track['id']}: {e}", file=sys.stderr)

            if not dry_run and idx % batch_size == 0 and idx < total:
                time.sleep(batch_interval_sec)

        elapsed = time.time() - started
        print(f"done: success={success}, failed={failed}, elapsed={elapsed:.1f}s")
        if not dry_run:
            check_db(conn)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch embed gugak_tracks via Gemini")
    parser.add_argument("--dry-run", action="store_true", help="API/DB 저장 없이 텍스트만 확인")
    parser.add_argument("--limit", type=int, default=0, help="처리 건수 제한 (0=전체)")
    parser.add_argument("--force", action="store_true", help="이미 embedding 있는 트랙도 재생성")
    parser.add_argument(
        "--all-tracks",
        action="store_true",
        help="cue_points 없는 구 데이터 포함 전체 임베딩 (기본은 cue_points>=3 만)",
    )
    parser.add_argument(
        "--clear-legacy-embeddings",
        action="store_true",
        help="cue_points 없는 구 트랙 embedding 제거 후 cue 트랙만 임베딩",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="초당 처리 건수 (기본 5)")
    parser.add_argument(
        "--batch-interval",
        type=float,
        default=DEFAULT_BATCH_INTERVAL_SEC,
        help="batch-size 건 처리 후 대기 초 (기본 1.0)",
    )
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Gemini embedding model")
    parser.add_argument("--check", action="store_true", help="embedding 통계만 출력")
    args = parser.parse_args()

    db_url, _ = load_config()
    conn = psycopg.connect(normalize_db_url(db_url))
    try:
        if args.check:
            check_db(conn)
            return
    finally:
        conn.close()

    run(
        dry_run=args.dry_run,
        limit=args.limit or None,
        force=args.force,
        cue_only=not args.all_tracks,
        clear_legacy=args.clear_legacy_embeddings,
        batch_size=max(1, args.batch_size),
        batch_interval_sec=max(0.0, args.batch_interval),
        model=args.model,
    )


if __name__ == "__main__":
    main()
