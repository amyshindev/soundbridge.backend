# 레이어: Application — Gemini API 아웃바운드 포트
from abc import ABC, abstractmethod

from soundbridge.app.dtos.track_discover_dto import EmotionAnalysisResult, MatchExplanation


class GeminiPort(ABC):

    @abstractmethod
    async def analyze_emotion(
        self, user_input: str, lang: str
    ) -> EmotionAnalysisResult:
        ...

    @abstractmethod
    async def explain_match(
        self, user_input: str, tracks: list, lang: str
    ) -> list[MatchExplanation]:
        ...

    @abstractmethod
    async def enrich_discover_matches(
        self, user_input: str, tracks: list, lang: str
    ) -> tuple[str, list[MatchExplanation]]:
        """감성 요약 + 트랙별 설명을 Gemini 1회 호출로 생성."""
        ...

    @abstractmethod
    async def extract_cue_points(self, audio_features: dict) -> dict:
        # [v1.1] 자동 추출
        ...
