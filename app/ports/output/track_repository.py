from abc import ABC, abstractmethod
from uuid import UUID

from soundbridge.domain.entities.track_entity import GugakTrack


class TrackRepository(ABC):

    @abstractmethod
    async def find_by_id(self, track_id: UUID) -> GugakTrack | None:
        ...

    @abstractmethod
    async def find_by_ids(self, track_ids: list[UUID]) -> list[GugakTrack]:
        ...

    @abstractmethod
    async def find_popular(self, limit: int = 6) -> list[GugakTrack]:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    async def save_match_log(
        self,
        input_text: str,
        lang: str,
        matched_track_id: UUID,
        similarity_score: float,
    ) -> None:
        ...
