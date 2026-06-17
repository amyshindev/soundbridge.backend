# 레이어: Outbound — TrackRepository + EmbeddingPort 구현
import uuid
from datetime import datetime, timezone

import google.generativeai as genai
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from soundbridge.adapter.outbound.mappers.track_orm_mapper import TrackOrmMapper
from soundbridge.adapter.outbound.orm.jangdan_orm import JangdanOrm
from soundbridge.adapter.outbound.orm.match_log_orm import MatchLogOrm
from soundbridge.adapter.outbound.orm.track_emotion_tag_orm import TrackEmotionTagOrm
from soundbridge.adapter.outbound.orm.track_orm import GugakTrackOrm
from soundbridge.app.ports.output.embedding_port import EmbeddingPort
from soundbridge.app.ports.output.track_repository import TrackRepository
from soundbridge.domain.entities.track_entity import GugakTrack
from soundbridge.infrastructure.exceptions import EmbeddingException
from soundbridge.infrastructure.secret_manager import keymaker


def _track_load_options() -> list:
    return [
        joinedload(GugakTrackOrm.emotion_tag_rows),
        joinedload(GugakTrackOrm.jangdan_rel),
    ]


class TrackDiscoverPgRepository(TrackRepository, EmbeddingPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        genai.configure(api_key=settings.gemini_api_key)
        self._mapper = TrackOrmMapper()

    async def find_by_id(self, track_id: uuid.UUID) -> GugakTrack | None:
        result = await self._session.execute(
            select(GugakTrackOrm)
            .options(*_track_load_options())
            .where(GugakTrackOrm.id == track_id)
        )
        row = result.unique().scalar_one_or_none()
        return self._mapper.to_entity(row) if row else None

    async def find_by_ids(self, track_ids: list[uuid.UUID]) -> list[GugakTrack]:
        if not track_ids:
            return []
        result = await self._session.execute(
            select(GugakTrackOrm)
            .options(*_track_load_options())
            .where(GugakTrackOrm.id.in_(track_ids))
        )
        rows = result.unique().scalars().all()
        id_order = {tid: i for i, tid in enumerate(track_ids)}
        return sorted(
            [self._mapper.to_entity(r) for r in rows],
            key=lambda t: id_order.get(t.id, 999),
        )

    async def find_popular(self, limit: int = 6) -> list[GugakTrack]:
        result = await self._session.execute(
            select(GugakTrackOrm).options(*_track_load_options()).limit(limit)
        )
        return [self._mapper.to_entity(r) for r in result.unique().scalars().all()]

    async def find_with_filters(
        self,
        instruments: list[str] | None,
        jangdans: list[str] | None,
        emotions: list[str] | None,
        bpm_min: int | None,
        bpm_max: int | None,
        loop_unit: int | None,
        license_type: str | None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[GugakTrack], int]:
        query = select(GugakTrackOrm).options(*_track_load_options())

        if instruments:
            query = query.where(GugakTrackOrm.instrument.in_(instruments))
        if jangdans:
            query = query.where(GugakTrackOrm.jangdan_name.in_(jangdans))
        if bpm_min is not None:
            query = query.where(GugakTrackOrm.bpm >= bpm_min)
        if bpm_max is not None:
            query = query.where(GugakTrackOrm.bpm <= bpm_max)
        if license_type:
            query = query.where(GugakTrackOrm.public_license_type == license_type)

        if emotions:
            query = (
                query.join(
                    TrackEmotionTagOrm,
                    TrackEmotionTagOrm.track_id == GugakTrackOrm.id,
                )
                .where(TrackEmotionTagOrm.emotion_tag.in_(emotions))
                .distinct()
            )

        if loop_unit is not None:
            query = (
                query.join(JangdanOrm, JangdanOrm.name == GugakTrackOrm.jangdan_name)
                .where(JangdanOrm.loop_unit_beats == loop_unit)
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar_one()

        result = await self._session.execute(query.limit(limit).offset(offset))
        rows = result.unique().scalars().all()
        return [self._mapper.to_entity(r) for r in rows], total

    async def save_match_log(
        self,
        input_text: str,
        lang: str,
        matched_track_id: uuid.UUID,
        similarity_score: float,
    ) -> None:
        log = MatchLogOrm(
            input_text=input_text,
            lang=lang,
            matched_track_id=matched_track_id,
            similarity_score=similarity_score,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(log)

    async def embed_text(self, text_content: str) -> list[float]:
        if not keymaker.has_gemini():
            raise EmbeddingException("GEMINI_API_KEY is not configured")
        try:
            result = genai.embed_content(
                model=keymaker.gemini_embedding_model,
                content=text_content,
                task_type="retrieval_query",
                output_dimensionality=1536,
            )
            embedding = result.get("embedding")
            if not embedding:
                raise EmbeddingException("Empty embedding response")
            return list(embedding)
        except Exception as e:
            raise EmbeddingException(f"Embedding failed: {e}") from e

    async def find_similar_tracks(
        self,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict | None = None,
    ) -> list[uuid.UUID]:
        vec_literal = "[" + ",".join(str(v) for v in query_vector) + "]"
        result = await self._session.execute(
            text("""
                SELECT id FROM gugak_tracks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :k
            """),
            {"vec": vec_literal, "k": top_k},
        )
        return [row[0] for row in result.fetchall()]
