# 레이어: Dependencies — DISCOVER DI 조립
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.adapter.outbound.external.gemini_adapter import GeminiAdapter
from soundbridge.adapter.outbound.pg.track_discover_pg_repository import TrackDiscoverPgRepository
from soundbridge.app.ports.input.track_discover_use_case import TrackDiscoverUseCase
from soundbridge.app.use_cases.track_discover_interactor import TrackDiscoverInteractor
from soundbridge.infrastructure.database import get_db
from soundbridge.infrastructure.redis_client import redis_client


def get_track_discover_use_case(
    db: AsyncSession = Depends(get_db),
) -> TrackDiscoverUseCase:
    repository = TrackDiscoverPgRepository(session=db)
    gemini = GeminiAdapter()
    return TrackDiscoverInteractor(
        track_repo=repository,
        claude=gemini,
        embedding=repository,
        redis=redis_client,
    )
