# 레이어: Dependencies — DISCOVER DI 조립 (v5.0 Task 7-1)
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.adapter.outbound.external.embedding_adapter import OllamaEmbeddingAdapter
from soundbridge.adapter.outbound.external.ollama_llm_adapter import OllamaLlmAdapter
from soundbridge.adapter.outbound.pg.track_discover_pg_repository import TrackDiscoverPgRepository
from soundbridge.app.ports.input.track_discover_use_case import TrackDiscoverUseCase
from soundbridge.app.use_cases.track_discover_interactor import TrackDiscoverInteractor
from soundbridge.infrastructure.database import get_db
from soundbridge.infrastructure.redis_client import redis_client


def get_track_discover_use_case(
    db: AsyncSession = Depends(get_db),
) -> TrackDiscoverUseCase:
    return TrackDiscoverInteractor(
        track_repo=TrackDiscoverPgRepository(session=db),
        ollama=OllamaLlmAdapter(),
        embedding=OllamaEmbeddingAdapter(session=db),
        redis=redis_client,
    )
