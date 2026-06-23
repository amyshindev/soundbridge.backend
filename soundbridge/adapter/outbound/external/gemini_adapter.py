# 레이어: Outbound — Gemini API GeminiPort 구현
import asyncio
import json
import re

from soundbridge.app.dtos.track_discover_dto import EmotionAnalysisResult, MatchExplanation
from soundbridge.app.ports.output.gemini_port import GeminiPort
from soundbridge.infrastructure.exceptions import GeminiApiException
from soundbridge.infrastructure.secret_manager import keymaker

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

DISCOVER_ENRICH_PROMPT = """
당신은 국악 감성 큐레이터입니다.
사용자 입력과 매칭된 국악 트랙 목록을 보고, 입력 요약과 트랙별 매칭 이유를 작성하세요.

사용자 입력: {user_input}

매칭 트랙:
{tracks_block}

다음 JSON만 응답하세요 (마크다운 없이):
{{
  "input_summary": "입력과 매칭을 한 줄로 요약 (한국어)",
  "explanations": [
    {{"track_id": "트랙 UUID", "ko": "한국어 설명 1-2문장", "en": "English 1-2 sentences"}}
  ]
}}
"""


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def _raise_gemini_error(exc: Exception, context: str) -> None:
    msg = str(exc)
    if "429" in msg or "quota" in msg.lower():
        raise GeminiApiException(
            "Gemini API 할당량을 초과했습니다. 잠시 후 다시 시도하거나 API 플랜을 확인해주세요."
        ) from exc
    raise GeminiApiException(f"{context}: {exc}") from exc


class GeminiAdapter(GeminiPort):

    def __init__(self) -> None:
        if not keymaker.has_gemini():
            keymaker.refresh()
        self._client = keymaker.get_gemini_model()
        if self._client is None:
            raise GeminiApiException("GEMINI_API_KEY is not configured")

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
            _raise_gemini_error(e, "감성 분석 실패")

    async def explain_match(
        self, user_input: str, tracks: list, lang: str
    ) -> list[MatchExplanation]:
        if not tracks:
            return []

        async def explain_one(track) -> MatchExplanation:
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
                return MatchExplanation(
                    track_id=track.id,
                    score=0.0,
                    explanation_ko=data["ko"],
                    explanation_en=data["en"],
                )
            except Exception:
                return MatchExplanation(
                    track_id=track.id,
                    score=0.0,
                    explanation_ko="",
                    explanation_en="",
                )

        return list(await asyncio.gather(*(explain_one(track) for track in tracks)))

    async def enrich_discover_matches(
        self, user_input: str, tracks: list, lang: str
    ) -> tuple[str, list[MatchExplanation]]:
        if not tracks:
            return user_input[:100], []

        lines = []
        for track in tracks:
            tags = ", ".join(e.value for e in track.emotion_tags)
            lines.append(
                f"- id: {track.id} | {track.title} | {track.instrument.value} | "
                f"{track.jangdan.type.value} | 감성: {tags}"
            )
        prompt = DISCOVER_ENRICH_PROMPT.format(
            user_input=user_input,
            tracks_block="\n".join(lines),
        )
        try:
            response = await self._client.generate_content_async(prompt)
            data = _parse_json(response.text)
            by_id = {str(item.get("track_id", "")): item for item in data.get("explanations", [])}
            explanations: list[MatchExplanation] = []
            for track in tracks:
                item = by_id.get(str(track.id), {})
                explanations.append(
                    MatchExplanation(
                        track_id=track.id,
                        score=0.0,
                        explanation_ko=item.get("ko", ""),
                        explanation_en=item.get("en", ""),
                    )
                )
            summary = (data.get("input_summary") or user_input)[:200]
            return summary, explanations
        except GeminiApiException:
            raise
        except Exception as e:
            _raise_gemini_error(e, "매칭 설명 생성 실패")

    async def extract_cue_points(self, audio_features: dict) -> dict:
        # TODO [v1.1]: 오디오 피처 기반 CUE 마커 자동 추출
        return {}
