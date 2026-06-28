# 레이어: Outbound — TrackRepository SQLAlchemy 구현
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import text

from soundbridge.adapter.outbound.mappers.track_orm_mapper import TrackOrmMapper
from soundbridge.adapter.outbound.orm.jangdan_orm import JangdanOrm
from soundbridge.adapter.outbound.orm.match_log_orm import MatchLogOrm
from soundbridge.adapter.outbound.orm.track_emotion_tag_orm import TrackEmotionTagOrm
from soundbridge.adapter.outbound.orm.track_orm import GugakTrackOrm
from soundbridge.app.ports.output.track_repository import TrackRepository
from soundbridge.domain.entities.track_entity import GugakTrack


def _track_load_options() -> list:
    return [
        joinedload(GugakTrackOrm.emotion_tag_rows),
        joinedload(GugakTrackOrm.jangdan_rel),
    ]


class TrackDiscoverPgRepository(TrackRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
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
            text("""
                WITH eligible AS (
                    SELECT t.id, NULLIF(TRIM(t.genre_mclsf), '') AS genre_mclsf
                    FROM gugak_tracks t
                    WHERE t.embedding IS NOT NULL
                      AND t.source_identifier IS NOT NULL
                      AND NULLIF(TRIM(t.genre_mclsf), '') IS NOT NULL
                      AND t.id IN (
                          SELECT DISTINCT ON (title) id
                          FROM gugak_tracks
                          WHERE embedding IS NOT NULL
                            AND source_identifier IS NOT NULL
                          ORDER BY title, created_at DESC
                      )
                ),
                per_genre AS (
                    SELECT DISTINCT ON (genre_mclsf) id
                    FROM eligible
                    ORDER BY genre_mclsf, RANDOM()
                ),
                fill AS (
                    SELECT e.id
                    FROM eligible e
                    WHERE e.id NOT IN (SELECT id FROM per_genre)
                    ORDER BY RANDOM()
                    LIMIT GREATEST(0, :limit - (SELECT COUNT(*)::int FROM per_genre))
                ),
                picked AS (
                    SELECT id FROM per_genre
                    UNION ALL
                    SELECT id FROM fill
                )
                SELECT
                    t.*,
                    COALESCE(
                        array_agg(tet.emotion_tag ORDER BY tet.sort_order)
                        FILTER (WHERE tet.emotion_tag IS NOT NULL),
                        ARRAY[]::varchar[]
                    ) AS emotion_tag_rows
                FROM gugak_tracks t
                LEFT JOIN track_emotion_tags tet ON tet.track_id = t.id
                WHERE t.id IN (SELECT id FROM picked)
                GROUP BY t.id
                ORDER BY RANDOM()
                LIMIT :limit
            """),
            {"limit": limit},
        )
        tracks: list[GugakTrack] = []
        for row in result.mappings().all():
            orm = GugakTrackOrm(
                id=row["id"],
                title=row["title"],
                artist=row["artist"],
                instrument=row["instrument"],
                jangdan_name=row["jangdan_name"],
                bpm=row["bpm"],
                cue_points=row["cue_points"],
                audio_url=row["audio_url"],
                public_license_type=row["public_license_type"],
                description_ko=row["description_ko"],
                description_en=row["description_en"],
                embedding=row.get("embedding"),
                created_at=row["created_at"],
                genre_mclsf=row.get("genre_mclsf") or "",
            )
            tag_names = row.get("emotion_tag_rows") or []
            orm.emotion_tag_rows = [
                TrackEmotionTagOrm(emotion_tag=tag, sort_order=index)
                for index, tag in enumerate(tag_names)
            ]
            tracks.append(self._mapper.to_entity(orm))
        return tracks

    async def find_with_filters(
        self,
        instruments: list[str] | None,
        genres: list[str] | None,
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
        query = query.where(GugakTrackOrm.source_identifier.isnot(None))

        if instruments:
            query = query.where(GugakTrackOrm.instrument.in_(instruments))
        if genres:
            query = query.where(GugakTrackOrm.genre_mclsf.in_(genres))
        if jangdans:
            query = query.where(GugakTrackOrm.jangdan_name.in_(jangdans))
        if bpm_min is not None or bpm_max is not None:
            lo = bpm_min if bpm_min is not None else 0
            hi = bpm_max if bpm_max is not None else 300
            # TM 메타 tempo=N/A → bpm=0; 템포 미기재 곡은 필터에서 제외하지 않음
            query = query.where(
                or_(
                    GugakTrackOrm.bpm == 0,
                    (GugakTrackOrm.bpm >= lo) & (GugakTrackOrm.bpm <= hi),
                )
            )
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
