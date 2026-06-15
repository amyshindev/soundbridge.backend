from abc import ABC, abstractmethod
from uuid import UUID


class EmbeddingPort(ABC):

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def find_similar_tracks(
        self,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict | None = None,
    ) -> list[UUID]:
        ...
