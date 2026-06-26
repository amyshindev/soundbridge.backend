# 레이어: Application — DISCOVER 유스케이스 오케스트레이션
import asyncio
import hashlib
import json
import logging
from dataclasses import asdict
from uuid import UUID

from soundbridge.adapter.outbound.mappers.track_result_mapper import to_track_result
from soundbridge.app.constants.filter_constants import POPULAR_TRACKS_DEFAULT_LIMIT
from soundbridge.app.constants.preset_constants import DISCOVER_CACHE_TTL_SEC, DISCOVER_TOP_K
from soundbridge.app.dtos.track_discover_dto import (
    DiscoverCommand,
    DiscoverResult,
    MatchExplanation,
    TrackResult,
)
from soundbridge.app.ports.input.track_discover_use_case import TrackDiscoverUseCase
from soundbridge.app.ports.output.embedding_port import EmbeddingPort
from soundbridge.app.ports.output.gemini_port import GeminiPort
from soundbridge.app.ports.output.track_repository import TrackRepository
from soundbridge.domain.entities.track_entity import GugakTrack
from soundbridge.infrastructure.exceptions import (
    EmbeddingException,
    GeminiApiException,
    TrackNotFoundException,
)
from soundbridge.infrastructure.settings import settings

logger = logging.getLogger(__name__)


class TrackDiscoverInteractor(TrackDiscoverUseCase):

    def __init__(
        self,
        track_repo: TrackRepository,
        gemini: GeminiPort,
        embedding: EmbeddingPort,
        redis=None,
    ) -> None:
        self._track_repo = track_repo
        self._gemini = gemini
        self._embedding = embedding
        self._redis = redis

    async def discover(self, command: DiscoverCommand) -> DiscoverResult:
        cache_key = self._make_cache_key(command)
        if self._redis:
            cached = await self._redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                tracks = [TrackResult(**t) for t in data["tracks"]]
                return DiscoverResult(tracks=tracks, input_summary=data["input_summary"])

        try:
            query_vec = await asyncio.wait_for(
                self._embedding.embed_text(command.input_text),
                timeout=settings.discover_embed_timeout_sec,
            )
        except asyncio.TimeoutError as e:
            raise GeminiApiException("임베딩 생성 시간이 초과되었습니다.") from e
        except EmbeddingException as e:
            raise GeminiApiException(str(e)) from e

        try:
            track_ids = await self._embedding.find_similar_tracks(query_vec, top_k=DISCOVER_TOP_K)
        except EmbeddingException as e:
            raise GeminiApiException(str(e)) from e
        tracks = await self._track_repo.find_by_ids(track_ids)

        return await self._finalize_discover(command, tracks, cache_key)

    async def _finalize_discover(
        self,
        command: DiscoverCommand,
        tracks: list[GugakTrack],
        cache_key: str,
    ) -> DiscoverResult:
        if command.lang == "en":
            input_summary = f'Gugak tracks with a similar mood to "{command.input_text[:60]}"'
        else:
            input_summary = f'"{command.input_text[:60]}" 와 감성이 닮은 국악'
        explanations: list[MatchExplanation] = []
        if tracks:
            if self._should_gemini_enrich(command):
                explanations, input_summary = await self._resolve_explanations(
                    command, tracks, input_summary
                )
            else:
                explanations = self._template_explanations(
                    command.input_text, tracks, command.lang
                )

        for track, exp in zip(tracks, explanations, strict=False):
            try:
                await self._track_repo.save_match_log(
                    command.input_text, command.lang, track.id, exp.score
                )
            except Exception:
                pass

        result = self._build_result(tracks, explanations, input_summary, command.lang)

        if self._redis:
            payload = {
                "tracks": [asdict(t) for t in result.tracks],
                "input_summary": result.input_summary,
            }
            await self._redis.setex(cache_key, DISCOVER_CACHE_TTL_SEC, json.dumps(payload, default=str))

        return result

    async def get_popular_tracks(self, limit: int = POPULAR_TRACKS_DEFAULT_LIMIT) -> list[TrackResult]:
        tracks = await self._track_repo.find_popular(limit)
        return [to_track_result(t) for t in tracks]

    async def get_track_detail(self, track_id: str) -> DiscoverResult:
        track = await self._track_repo.find_by_id(UUID(track_id))
        if not track:
            raise TrackNotFoundException(track_id)
        return self._build_result([track], [], track.title, "ko")

    def _should_gemini_enrich(self, command: DiscoverCommand) -> bool:
        return command.enrich or settings.discover_gemini_enrich

    def _make_cache_key(self, command: DiscoverCommand) -> str:
        enrich_flag = "1" if self._should_gemini_enrich(command) else "0"
        digest = hashlib.md5(
            f"{command.input_text}:{command.lang}:{enrich_flag}".encode()
        ).hexdigest()
        return f"sb:discover:v5:{digest}"

    async def _resolve_explanations(
        self,
        command: DiscoverCommand,
        tracks: list[GugakTrack],
        input_summary: str,
    ) -> tuple[list[MatchExplanation], str]:
        """EXAONE 배치 → 곡별 병렬 순으로 시도. 전체 예산 discover_total_timeout_sec."""

        async def _run() -> tuple[list[MatchExplanation], str]:
            try:
                summary, explanations = await self._gemini.enrich_discover_matches(
                    command.input_text, tracks, command.lang
                )
                if self._has_rich_explanations(explanations):
                    return explanations, summary
            except GeminiApiException as e:
                logger.warning("Discover batch enrich failed: %s", e)

            explanations = await self._gemini.explain_match(
                command.input_text, tracks, command.lang
            )
            if self._has_rich_explanations(explanations):
                return explanations, input_summary
            raise GeminiApiException("EXAONE explanations too thin")

        try:
            return await asyncio.wait_for(_run(), timeout=settings.discover_total_timeout_sec)
        except (asyncio.TimeoutError, GeminiApiException) as e:
            logger.warning("Discover LLM phase failed: %s", e)

        return (
            self._template_explanations(command.input_text, tracks, command.lang),
            input_summary,
        )

    @staticmethod
    def _has_rich_explanations(explanations: list[MatchExplanation]) -> bool:
        contrast = (
            "인 반해",
            "하지만",
            "반면",
            "와 달리",
            "다르지만",
            "보다 더",
            "차이가",
        )
        for exp in explanations:
            text = (exp.explanation_ko or exp.explanation_en or "").strip()
            if len(text) < 35:
                continue
            if any(marker in text for marker in contrast):
                continue
            if "흐름, 감성이 닮아" in text:
                continue
            return True
        return False

    def _template_explanations(
        self,
        user_input: str,
        tracks: list[GugakTrack],
        lang: str,
    ) -> list[MatchExplanation]:
        short_input = user_input[:40]
        explanations: list[MatchExplanation] = []
        for track in tracks:
            tags = ", ".join(e.value for e in track.emotion_tags)
            if lang == "en":
                ko = ""
                en = (
                    f"{short_input} pairs with {track.title}'s {track.jangdan.type.value} "
                    f"rhythm and {tags} mood."
                )
            else:
                ko = (
                    f"{short_input}과(와) {track.title}의 {track.jangdan.type.value} 흐름, "
                    f"{tags} 감성이 닮아 있습니다."
                )
                en = ""
            explanations.append(
                MatchExplanation(
                    track_id=track.id,
                    score=0.0,
                    explanation_ko=ko,
                    explanation_en=en,
                )
            )
        return explanations

    def _build_result(
        self,
        tracks: list[GugakTrack],
        explanations: list[MatchExplanation],
        input_summary: str,
        lang: str,
    ) -> DiscoverResult:
        exp_map = {e.track_id: e for e in explanations}
        track_results: list[TrackResult] = []
        for track in tracks:
            tr = to_track_result(track)
            exp = exp_map.get(track.id)
            if exp:
                tr.score = exp.score
                tr.explanation = exp.explanation_ko if lang == "ko" else exp.explanation_en
            track_results.append(tr)
        return DiscoverResult(tracks=track_results, input_summary=input_summary)
