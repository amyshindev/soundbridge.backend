# 레이어: Outbound — Gemini API GeminiPort 구현
import json
import re

import google.generativeai as genai

from soundbridge.app.dtos.track_discover_dto import EmotionAnalysisResult, MatchExplanation
from soundbridge.app.ports.output.gemini_port import GeminiPort
from soundbridge.infrastructure.exceptions import GeminiApiException
from soundbridge.infrastructure.settings import settings

EMOTION_ANALYSIS_PROMPT = """
당신은 음악 감성 분석 전문가입니다.
사용자가 좋아하는 음악 정보를 분석해 국악 매칭에 필요한 감성 키워드를 추출하세요.

입력: {user_input}

다음 JSON 형식으로만 응답하세요 (마크다운 없이):
{{
  "emotions": ["감성1", "감성2"],
  "mood": "전반적 분위기",
  "instrument_hints": ["악기1"],
  "embed_text": "임베딩 생성용 정제 텍스트 (한국어, 2-3문장)"
}}
"""

MATCH_EXPLANATION_PROMPT = """
사용자가 '{user_input}'을(를) 좋아한다고 했습니다.
아래 국악 트랙이 왜 감성적으로 비슷한지 한국어와 영어로 각각 1-2문장 설명하세요.

트랙: {track_title} ({instrument}, {jangdan})
감성: {emotion_tags}

JSON 형식으로만 응답 (마크다운 없이):
{{"ko": "한국어 설명", "en": "English explanation"}}
"""


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


class GeminiAdapter(GeminiPort):

    def __init__(self) -> None:
        genai.configure(api_key=settings.gemini_api_key)
        self._client = genai.GenerativeModel(settings.gemini_model)

    async def analyze_emotion(self, user_input: str, lang: str) -> EmotionAnalysisResult:
        try:
            prompt = EMOTION_ANALYSIS_PROMPT.format(user_input=user_input)
            response = await self._client.generate_content_async(prompt)
            data = _parse_json(response.text)
            return EmotionAnalysisResult(
                emotions=data["emotions"],
                mood=data["mood"],
                instrument_hints=data["instrument_hints"],
                embed_text=data["embed_text"],
            )
        except Exception as e:
            raise GeminiApiException(f"감성 분석 실패: {e}") from e

    async def explain_match(
        self, user_input: str, tracks: list, lang: str
    ) -> list[MatchExplanation]:
        explanations: list[MatchExplanation] = []
        for track in tracks:
            try:
                prompt = MATCH_EXPLANATION_PROMPT.format(
                    user_input=user_input,
                    track_title=track.title,
                    instrument=track.instrument.value,
                    jangdan=track.jangdan.type.value,
                    emotion_tags=", ".join(e.value for e in track.emotion_tags),
                )
                response = await self._client.generate_content_async(prompt)
                data = _parse_json(response.text)
                explanations.append(
                    MatchExplanation(
                        track_id=track.id,
                        score=0.0,
                        explanation_ko=data["ko"],
                        explanation_en=data["en"],
                    )
                )
            except Exception:
                explanations.append(
                    MatchExplanation(
                        track_id=track.id,
                        score=0.0,
                        explanation_ko="",
                        explanation_en="",
                    )
                )
        return explanations

    async def extract_cue_points(self, audio_features: dict) -> dict:
        # TODO [v1.1]: 오디오 피처 기반 CUE 마커 자동 추출
        return {}
