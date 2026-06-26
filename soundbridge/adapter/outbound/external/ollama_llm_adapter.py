# 레이어: Outbound — Ollama EXAONE 등 로컬 LLM (OllamaPort 구현)
from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

from soundbridge.app.dtos.track_discover_dto import EmotionAnalysisResult, MatchExplanation
from soundbridge.app.ports.output.ollama_port import OllamaPort
from soundbridge.infrastructure.exceptions import OllamaApiException
from soundbridge.infrastructure.settings import settings

logger = logging.getLogger(__name__)

DISCOVER_ENRICH_PROMPT_OLLAMA = """
당신은 국악 감성 큐레이터입니다.
아래 국악은 이미 사용자 입력과 **비슷하다고** 시스템이 골라 놓은 곡입니다.
각 곡이 입력 음악과 **무엇이 닮았는지**만 설명하세요.

규칙:
- 차이점·대비는 쓰지 마세요. "~인 반해", "~하지만", "~반면", "~와 달리" 금지.
- "더 ~하다", "덜 ~하다" 같은 비교급으로 차이를 드러내지 마세요.
- 공통 리듬감·분위기·감정선·텐션만 2~3문장으로 연결하세요.
- "장단 흐름, 감성이 닮습니다" 같은 한 줄 요약만 쓰지 마세요.
- '미분류'는 악기 미지정입니다. 기타(guitar)가 아닙니다. 악기가 미분류면 악기·기타를 언급하지 마세요.
- 반드시 유효한 JSON만 출력하세요.

사용자 입력: {user_input}

매칭 국악 (index 순서 유지):
{tracks_block}

출력 JSON 형식:
{{
  "input_summary": "입력과 매칭을 한 줄로 요약 (한국어)",
  "explanations": [
    {{"index": 1, "ko": "한국어 설명 2-3문장", "en": "English 2-3 sentences"}},
    {{"index": 2, "ko": "...", "en": "..."}}
  ]
}}
"""

MATCH_EXPLANATION_PROMPT_OLLAMA = """
사용자가 좋아하는 음악: {user_input}

매칭 국악곡: {track_title}
악기: {instrument}, 장단: {jangdan}, 감성: {emotion_tags}
곡 설명: {description}

이 국악은 입력 음악과 이미 비슷한 곡으로 선정되었습니다.
**닮은 점만** 한국어 2~3문장으로 설명하세요.

금지: 차이·대비 ("~인 반해", "~하지만", "~반면", "더/덜 ~하다").
악기가 '미분류'이면 기타(guitar) 등 악기를 추측해 쓰지 마세요.

JSON만 출력:
{{"ko": "한국어 설명", "en": "English explanation"}}
"""


def _raise_llm_error(exc: Exception, context: str) -> None:
    raise OllamaApiException(
        f"{context}: {exc}. Ollama가 실행 중이고 "
        f"'{settings.ollama_chat_model}' 모델이 pull 되었는지 확인하세요."
    ) from exc


def _extract_json_object(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise OllamaApiException("LLM JSON 파싱 실패")


def _parse_explanations_from_raw(raw: str, track_count: int) -> list[dict]:
    """EXAONE이 JSON을 깨뜨렸을 때 ko 필드만이라도 추출."""
    items: list[dict] = []
    for idx, ko in enumerate(
        re.findall(r'"ko"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL),
        start=1,
    ):
        text = ko.replace("\\n", "\n").replace('\\"', '"').strip()
        if text:
            items.append({"index": idx, "ko": text, "en": ""})
        if len(items) >= track_count:
            break
    return items


def _instrument_for_prompt(value: str) -> str:
    if value in ("기타", "미분류", ""):
        return "미분류 (악기 정보 없음 — guitar 아님)"
    return value


_CONTRAST_MARKERS = (
    "인 반해",
    "하지만",
    "반면",
    "와 달리",
    "다르지만",
    "보다 더",
    "보다 덜",
    "반대로",
    "차이가",
    "while ",
    "whereas ",
    "however ",
    "in contrast",
)


def _is_rich_explanation(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 35:
        return False
    generic = ("흐름, 감성이 닮아", "rhythm and", "pairs with")
    if any(phrase in stripped for phrase in generic):
        return False
    lower = stripped.lower()
    return not any(marker in stripped or marker in lower for marker in _CONTRAST_MARKERS)


class OllamaLlmAdapter(OllamaPort):

    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_chat_model
        self._timeout = settings.discover_llm_timeout_sec

    async def _chat(self, prompt: str, *, num_predict: int = 220) -> str:
        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.4, "num_predict": num_predict},
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")
                if not content:
                    raise OllamaApiException("Ollama 응답이 비어 있습니다.")
                return content
        except OllamaApiException:
            raise
        except httpx.HTTPError as e:
            _raise_llm_error(e, "Ollama LLM 요청 실패")
        except Exception as e:
            _raise_llm_error(e, "Ollama LLM 처리 실패")

    async def analyze_emotion(self, user_input: str, lang: str) -> EmotionAnalysisResult:
        raise OllamaApiException("Ollama 감성 분석은 DISCOVER에서 사용하지 않습니다.")

    async def explain_match(
        self, user_input: str, tracks: list, lang: str
    ) -> list[MatchExplanation]:
        if not tracks:
            return []

        async def explain_one(track) -> MatchExplanation:
            tags = ", ".join(e.value for e in track.emotion_tags)
            prompt = MATCH_EXPLANATION_PROMPT_OLLAMA.format(
                user_input=user_input,
                track_title=track.title,
                instrument=_instrument_for_prompt(track.instrument.value),
                jangdan=track.jangdan.type.value,
                emotion_tags=tags or "없음",
                description=(track.description_ko or "")[:300],
            )
            try:
                raw = await self._chat(prompt)
                data = _extract_json_object(raw)
                ko = (data.get("ko") or "").strip()
                en = (data.get("en") or "").strip()
                return MatchExplanation(
                    track_id=track.id,
                    score=0.0,
                    explanation_ko=ko,
                    explanation_en=en,
                )
            except Exception as e:
                logger.warning("per-track explain failed for %s: %s", track.title, e)
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
        for idx, track in enumerate(tracks, start=1):
            tags = ", ".join(e.value for e in track.emotion_tags)
            desc = (track.description_ko or "")[:200]
            lines.append(
                f"{idx}. {track.title} | 악기: {_instrument_for_prompt(track.instrument.value)} | "
                f"장단: {track.jangdan.type.value} | 감성: {tags or '없음'} | 설명: {desc}"
            )

        prompt = DISCOVER_ENRICH_PROMPT_OLLAMA.format(
            user_input=user_input,
            tracks_block="\n".join(lines),
        )

        raw = await self._chat(prompt, num_predict=512)
        try:
            data = _extract_json_object(raw)
            explanation_items = data.get("explanations", [])
            summary = (data.get("input_summary") or user_input)[:200]
        except OllamaApiException:
            explanation_items = _parse_explanations_from_raw(raw, len(tracks))
            if not explanation_items:
                raise
            summary = user_input[:200]

        by_index: dict[int, dict] = {}
        by_id: dict[str, dict] = {}
        for item in explanation_items:
            if "index" in item:
                by_index[int(item["index"])] = item
            if item.get("track_id"):
                by_id[str(item["track_id"])] = item

        explanations: list[MatchExplanation] = []
        for idx, track in enumerate(tracks, start=1):
            item = by_index.get(idx) or by_id.get(str(track.id), {})
            explanations.append(
                MatchExplanation(
                    track_id=track.id,
                    score=0.0,
                    explanation_ko=(item.get("ko") or "").strip(),
                    explanation_en=(item.get("en") or "").strip(),
                )
            )

        if not any(_is_rich_explanation(e.explanation_ko) for e in explanations):
            raise OllamaApiException("EXAONE 설명이 충분히 생성되지 않았습니다.")

        return summary, explanations

    async def extract_cue_points(self, audio_features: dict) -> dict:
        return {}
