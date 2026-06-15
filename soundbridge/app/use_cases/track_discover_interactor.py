# 레이어: Application — DISCOVER 유스케이스 오케스트레이션
import hashlib
import json
from dataclasses import asdict
from uuid import UUID

from soundbridge.app.mappers.track_result_mapper import to_track_result
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
from soundbridge.infrastructure.exceptions import TrackNotFoundException


class TrackDiscoverInteractor(TrackDiscoverUseCase):

    def __init__(
        self,
        track_repo: TrackRepository,
        claude: GeminiPort,
        embedding: EmbeddingPort,
        redis=None,
    ) -> None:
        self._track_repo = track_repo
        self._claude = claude
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

        emotion = await self._claude.analyze_emotion(command.input_text, command.lang)
        query_vec = await self._embedding.embed_text(emotion.embed_text)
        track_ids = await self._embedding.find_similar_tracks(query_vec, top_k=3)
        tracks = await self._track_repo.find_by_ids(track_ids)
        explanations = await self._claude.explain_match(
            command.input_text, tracks, command.lang
        )

        for track, exp in zip(tracks, explanations, strict=False):
            try:
                await self._track_repo.save_match_log(
                    command.input_text, command.lang, track.id, exp.score
                )
            except Exception:
                pass

        result = self._build_result(tracks, explanations, command.input_text, command.lang)

        if self._redis:
            payload = {
                "tracks": [asdict(t) for t in result.tracks],
                "input_summary": result.input_summary,
            }
            await self._redis.setex(cache_key, 3600, json.dumps(payload, default=str))

        return result

    async def get_popular_tracks(self, limit: int = 6) -> list[TrackResult]:
        tracks = await self._track_repo.find_popular(limit)
        return [to_track_result(t) for t in tracks]

    async def get_track_detail(self, track_id: str) -> DiscoverResult:
        track = await self._track_repo.find_by_id(UUID(track_id))
        if not track:
            raise TrackNotFoundException(track_id)
        return self._build_result([track], [], "", "ko")

    def _make_cache_key(self, command: DiscoverCommand) -> str:
        digest = hashlib.md5(f"{command.input_text}:{command.lang}".encode()).hexdigest()
        return f"sb:discover:{digest}"

    def _build_result(
        self,
        tracks: list[GugakTrack],
        explanations: list[MatchExplanation],
        input_text: str,
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
        summary = input_text[:100] if input_text else ""
        return DiscoverResult(tracks=track_results, input_summary=summary)
