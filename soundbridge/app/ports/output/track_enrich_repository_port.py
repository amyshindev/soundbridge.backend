# 레이어: Application — TM enrich+embed 배치 리포지토리 포트
from abc import ABC, abstractmethod
from uuid import UUID

from soundbridge.app.dtos.track_enrich_embed_dto import TrackEnrichTarget


class TrackEnrichRepositoryPort(ABC):

    @abstractmethod
    def prepare_schema(self) -> None:
        ...

    @abstractmethod
    def fetch_targets(
        self,
        *,
        only_missing_embedding: bool,
        limit: int | None,
        tm_only: bool,
    ) -> list[TrackEnrichTarget]:
        ...

    @abstractmethod
    def save_description(self, track_id: UUID, description_ko: str) -> None:
        ...

    @abstractmethod
    def save_embedding(self, track_id: UUID, embedding: list[float]) -> None:
        ...

    @abstractmethod
    def commit(self) -> None:
        ...

    @abstractmethod
    def rollback(self) -> None:
        ...

    @abstractmethod
    def print_embedding_stats(self) -> None:
        ...
