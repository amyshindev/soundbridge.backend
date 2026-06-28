"""gugak_tracks 임베딩 배치 생성 스크립트.

국악음원(TM) 메타(장르, 장단, 감성, 음색, caption)를 합쳐
nomic-embed-text 로 벡터를 만들고 embedding 컬럼에 저장합니다.

레이트리밋: 기본 1초당 5건 (5건 처리 후 1초 대기).

Usage:
  cd backend
  pip install -r requirements.txt
  python scripts/embed_gugak_tracks.py --dry-run --limit 5
  python scripts/embed_gugak_tracks.py --force
  python scripts/embed_gugak_tracks.py --check

Docker(API 컨테이너)에서 실행:
  docker compose exec api python scripts/embed_gugak_tracks.py --force
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import psycopg
except ModuleNotFoundError as e:
    raise SystemExit(
        "psycopg 가 설치되어 있지 않습니다.\n"
        "  cd backend && pip install -r requirements.txt\n"
        "또는 API 컨테이너에서:\n"
        "  docker compose exec api python scripts/embed_gugak_tracks.py --check"
    ) from e

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from soundbridge.adapter.outbound.pg.tm_schema_ddl import apply_tm_schema_sync

EMBEDDING_DIMENSION = 768
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_EMBED_BASE_URL = "http://localhost:11434"

DEFAULT_BATCH_SIZE = 5
DEFAULT_BATCH_INTERVAL_SEC = 1.0


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


def load_config() -> str:
    load_env_files()

    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL 이 .env 에 없습니다.")
    return db_url


def default_embed_url() -> str:
    load_env_files()
    return os.getenv("EMBED_BASE_URL", DEFAULT_EMBED_BASE_URL).strip()


def normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    if url.startswith("postgresql+psycopg_async://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg_async://")
    return url


def build_embed_text(
    title: str,
    artist: str,
    genre_lclsf: str,
    genre_mclsf: str,
    genre_sclsf: str,
    jangdan_name: str,
    jangdan_raw: str,
    time_signature: str,
    tempo_label: str,
    emotion_tags: list[str],
    whole_emotions: list[dict],
    whole_tones: list[dict],
    description_ko: str,
) -> str:
    genre_parts = [g for g in (genre_lclsf, genre_mclsf, genre_sclsf) if g]
    genre_line = " / ".join(genre_parts) if genre_parts else "없음"

    jangdan_display = jangdan_raw or jangdan_name or "없음"
    tags = ", ".join(emotion_tags) if emotion_tags else "없음"

    raw_emotions = sorted(
        whole_emotions or [],
        key=lambda x: int(x.get("count") or 0),
        reverse=True,
    )
    emotion_detail = ", ".join(
        f"{item.get('emotion', '')}({item.get('count', 0)})"
        for item in raw_emotions[:6]
        if item.get("emotion")
    )

    raw_tones = sorted(
        whole_tones or [],
        key=lambda x: int(x.get("count") or 0),
        reverse=True,
    )
    tone_detail = ", ".join(
        f"{item.get('tone', '')}({item.get('count', 0)})"
        for item in raw_tones[:6]
        if item.get("tone")
    )

    tempo_display = tempo_label if tempo_label and tempo_label.upper() != "N/A" else "없음"
    time_sig_display = time_signature or "없음"

    lines = [
        f"제목: {title}",
        f"연주·가창: {artist}",
        f"장르: {genre_line}",
        f"장단: {jangdan_display}",
        f"박자: {time_sig_display}  템포: {tempo_display}",
        f"감성 태그: {tags}",
    ]
    if emotion_detail:
        lines.append(f"감성 상세: {emotion_detail}")
    if tone_detail:
        lines.append(f"음색: {tone_detail}")
    lines.append(f"설명: {description_ko or '없음'}")
    return "\n".join(lines)


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
        clauses.append("t.source_identifier IS NOT NULL")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = f"LIMIT {int(limit)}" if limit else ""

    query = f"""
        SELECT
            t.id,
            t.title,
            t.artist,
            t.genre_lclsf,
            t.genre_mclsf,
            t.genre_sclsf,
            t.jangdan_name,
            t.jangdan_raw,
            t.time_signature,
            t.tempo_label,
            t.description_ko,
            t.whole_emotions,
            t.whole_tones,
            COALESCE(
                array_agg(tet.emotion_tag ORDER BY tet.sort_order)
                FILTER (WHERE tet.emotion_tag IS NOT NULL),
                ARRAY[]::varchar[]
            ) AS emotion_tags
        FROM gugak_tracks t
        LEFT JOIN track_emotion_tags tet ON tet.track_id = t.id
        {where}
        GROUP BY t.id, t.title, t.artist, t.genre_lclsf, t.genre_mclsf, t.genre_sclsf,
                 t.jangdan_name, t.jangdan_raw, t.time_signature, t.tempo_label,
                 t.description_ko, t.whole_emotions, t.whole_tones,
                 t.cue_points, t.created_at
        ORDER BY
            CASE WHEN t.source_identifier IS NOT NULL THEN 0 ELSE 1 END,
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
            "genre_lclsf": row[3] or "",
            "genre_mclsf": row[4] or "",
            "genre_sclsf": row[5] or "",
            "jangdan_name": row[6] or "",
            "jangdan_raw": row[7] or "",
            "time_signature": row[8] or "",
            "tempo_label": row[9] or "",
            "description_ko": row[10] or "",
            "whole_emotions": row[11] or [],
            "whole_tones": row[12] or [],
            "emotion_tags": list(row[13] or []),
        }
        for row in rows
    ]


def embed_text(model: str, text: str, base_url: str) -> list[float]:
    url = f"{base_url.rstrip('/')}/api/embeddings"
    body = json.dumps({"model": model, "prompt": text}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"임베딩 요청 실패 ({url}). 임베딩 서버가 실행 중인지 확인하세요: {e}"
        ) from e

    embedding = payload.get("embedding")
    if not embedding:
        raise RuntimeError("임베딩 응답에 embedding 이 없습니다.")
    if len(embedding) != EMBEDDING_DIMENSION:
        raise RuntimeError(
            f"임베딩 차원 불일치: {len(embedding)} (기대 {EMBEDDING_DIMENSION})"
        )
    return embedding


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
    base_url: str,
) -> None:
    db_url = load_config()
    conn = psycopg.connect(normalize_db_url(db_url))

    try:
        apply_tm_schema_sync(conn)
        print("[schema] TM columns ready")

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
            f"targets: {total} (force={force}, cue_only={cue_only}, "
            f"embed={base_url}, model={model}, batch={batch_size}/sec)"
        )

        success = 0
        failed = 0
        started = time.time()

        for idx, track in enumerate(tracks, start=1):
            text = build_embed_text(
                title=track["title"],
                artist=track["artist"],
                genre_lclsf=track["genre_lclsf"],
                genre_mclsf=track["genre_mclsf"],
                genre_sclsf=track["genre_sclsf"],
                jangdan_name=track["jangdan_name"],
                jangdan_raw=track["jangdan_raw"],
                time_signature=track["time_signature"],
                tempo_label=track["tempo_label"],
                emotion_tags=track["emotion_tags"],
                whole_emotions=track["whole_emotions"],
                whole_tones=track["whole_tones"],
                description_ko=track["description_ko"],
            )

            if dry_run:
                print(f"[DRY {idx}/{total}] {track['id']} | {track['title']}")
                print(text[:120].replace("\n", " | ") + ("..." if len(text) > 120 else ""))
                success += 1
            else:
                try:
                    vector = embed_text(model, text, base_url)
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
    parser = argparse.ArgumentParser(description="Batch embed gugak_tracks via embedding API")
    parser.add_argument("--dry-run", action="store_true", help="API/DB 저장 없이 텍스트만 확인")
    parser.add_argument("--limit", type=int, default=0, help="처리 건수 제한 (0=전체)")
    parser.add_argument("--force", action="store_true", help="이미 embedding 있는 트랙도 재생성")
    parser.add_argument(
        "--all-tracks",
        action="store_true",
        help="전체 트랙 임베딩 (기본은 cue_points>=3 또는 TM source_identifier 있는 트랙)",
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
    parser.add_argument("--model", type=str, default=DEFAULT_EMBED_MODEL, help="Embedding model")
    parser.add_argument(
        "--embed-url",
        type=str,
        default=default_embed_url(),
        help="Embed base URL (기본: EMBED_BASE_URL 또는 http://localhost:11434)",
    )
    parser.add_argument("--check", action="store_true", help="embedding 통계만 출력")
    args = parser.parse_args()

    db_url = load_config()
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
        base_url=args.embed_url,
    )


if __name__ == "__main__":
    main()
