from abc import ABC, abstractmethod

from soundbridge.app.dtos.track_discover_dto import DiscoverCommand, DiscoverResult, TrackResult


class TrackDiscoverUseCase(ABC):

    @abstractmethod
    async def discover(self, command: DiscoverCommand) -> DiscoverResult:
        ...

    @abstractmethod
    async def get_track_detail(self, track_id: str) -> DiscoverResult:
        ...

    @abstractmethod
    async def get_popular_tracks(self, limit: int = 6) -> list[TrackResult]:
        ...
