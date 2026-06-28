# 레이어: Application — 배치 문서 임베딩 포트 (Cohere search_document)
from abc import ABC, abstractmethod


class BatchEmbeddingPort(ABC):

    @abstractmethod
    def embed_document(self, text: str) -> list[float]:
        ...
