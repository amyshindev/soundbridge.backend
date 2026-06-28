"""국악 트랙 메타데이터 EXAONE 풍부화 → Cohere embed-v4.0 임베딩 파이프라인.

Usage:
  cd backend
  python scripts/enrich_and_embed.py --dry-run --limit 3
  python scripts/enrich_and_embed.py --force
  python scripts/enrich_and_embed.py --check
  python scripts/enrich_and_embed.py --enrich-only --limit 10
  python scripts/enrich_and_embed.py --embed-only --force
"""

from __future__ import annotations

import argparse
import sys
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
sys.path.insert(0, str(BACKEND_DIR))

from soundbridge.adapter.outbound.external.cohere_batch_embedding_adapter import (
    CohereBatchEmbeddingAdapter,
)
from soundbridge.adapter.outbound.external.exaone_track_description_enrich_adapter import (
    ExaoneTrackDescriptionEnrichAdapter,
)
from soundbridge.adapter.outbound.pg.track_enrich_pg_repository import TrackEnrichPgRepository
from soundbridge.app.dtos.track_enrich_embed_dto import EnrichEmbedCommand
from soundbridge.app.policies.track_enrich_policy import (
    DEFAULT_BATCH_INTERVAL_SEC,
    DEFAULT_BATCH_SIZE,
)
from soundbridge.app.use_cases.track_enrich_embed_interactor import TrackEnrichEmbedInteractor
from soundbridge.infrastructure.pg_script_util import load_database_url, normalize_psycopg_url
from soundbridge.infrastructure.secret_manager import secretmanager


def _build_interactor(conn) -> TrackEnrichEmbedInteractor:
    return TrackEnrichEmbedInteractor(
        repository=TrackEnrichPgRepository(conn),
        description_enricher=ExaoneTrackDescriptionEnrichAdapter(),
        batch_embedding=CohereBatchEmbeddingAdapter(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EXAONE 메타 풍부화 후 Cohere embed-v4.0 임베딩"
    )
    parser.add_argument("--dry-run", action="store_true", help="API/DB 저장 없이 확인")
    parser.add_argument("--limit", type=int, default=0, help="처리 건수 제한 (0=전체)")
    parser.add_argument("--force", action="store_true", help="이미 embedding 있는 트랙도 재처리")
    parser.add_argument(
        "--all-tracks",
        action="store_true",
        help="TM source_identifier 없는 트랙도 포함",
    )
    parser.add_argument("--enrich-only", action="store_true", help="EXAONE 풍부화만 (임베딩 생략)")
    parser.add_argument(
        "--embed-only",
        action="store_true",
        help="현재 description_ko 기준 임베딩만 (EXAONE 생략)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="배치 크기 (기본 3)",
    )
    parser.add_argument(
        "--batch-interval",
        type=float,
        default=DEFAULT_BATCH_INTERVAL_SEC,
        help="배치 간 대기 초 (기본 2.0)",
    )
    parser.add_argument("--check", action="store_true", help="embedding 통계만 출력")
    args = parser.parse_args()

    secretmanager.bootstrap()
    conn = psycopg.connect(normalize_psycopg_url(load_database_url()))
    try:
        interactor = _build_interactor(conn)
        if args.check:
            interactor.print_stats()
            return

        command = EnrichEmbedCommand(
            dry_run=args.dry_run,
            limit=args.limit or None,
            force=args.force,
            tm_only=not args.all_tracks,
            batch_size=max(1, args.batch_size),
            batch_interval_sec=max(0.0, args.batch_interval),
            enrich_only=args.enrich_only,
            embed_only=args.embed_only,
        )
        interactor.run(command)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
