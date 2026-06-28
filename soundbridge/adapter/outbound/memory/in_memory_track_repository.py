# In-memory TrackRepository (dev/test fallback — DB 없이 빈 응답)
import uuid

from soundbridge.app.ports.output.track_repository import TrackRepository
from soundbridge.domain.entities.track_entity import GugakTrack


class InMemoryTrackRepository(TrackRepository):
    """로컬 스모크·단위 테스트용. 프로덕션 DI 에서는 PG repository 사용."""

    def __init__(self, tracks: list[GugakTrack] | None = None) -> None:
        self._tracks = {t.id: t for t in (tracks or [])}

    async def find_by_id(self, track_id: uuid.UUID) -> GugakTrack | None:
        return self._tracks.get(track_id)

    async def find_by_ids(self, track_ids: list[uuid.UUID]) -> list[GugakTrack]:
        return [t for tid in track_ids if (t := self._tracks.get(tid))]

    async def find_popular(self, limit: int = 6) -> list[GugakTrack]:
        rows = list(self._tracks.values())
        by_genre: dict[str, GugakTrack] = {}
        for track in rows:
            key = (track.genre_mclsf or track.instrument.value).strip()
            if key and key not in by_genre:
                by_genre[key] = track
        diverse = list(by_genre.values())
        if len(diverse) >= limit:
            return diverse[:limit]
        used = {t.id for t in diverse}
        for track in rows:
            if len(diverse) >= limit:
                break
            if track.id not in used:
                diverse.append(track)
                used.add(track.id)
        return diverse

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
        rows = list(self._tracks.values())
        return rows[offset : offset + limit], len(rows)

    async def save_match_log(
        self,
        input_text: str,
        lang: str,
        matched_track_id: uuid.UUID,
        similarity_score: float,
    ) -> None:
        return None
