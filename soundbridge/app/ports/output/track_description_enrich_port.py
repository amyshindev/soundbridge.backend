# 레이어: Application — TM description_ko 풍부화 포트 (배치)
from abc import ABC, abstractmethod


class TrackDescriptionEnrichPort(ABC):

    @abstractmethod
    def enrich_description(self, prompt: str) -> str:
        """EXAONE으로 3-4문장 한국어 설명 생성."""
