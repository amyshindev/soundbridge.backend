# 레이어: Inbound — DISCOVER HTTP 엔드포인트
import json

from fastapi import APIRouter, Depends, HTTPException

from soundbridge.adapter.inbound.api.schemas.track_discover_schema import (
    DiscoverRequestSchema,
    DiscoverResponseSchema,
)
from soundbridge.adapter.inbound.api.schemas.track_suggest_schema import (
    TrackSuggestResponseSchema,
    TrackSuggestionSchema,
)
from soundbridge.adapter.outbound.external.itunes_search_adapter import ItunesSearchAdapter
from soundbridge.adapter.inbound.api.schemas.track_response_schema import TrackResponseSchema
from soundbridge.adapter.inbound.mappers.track_discover_mapper import (
    to_discover_response,
    to_track_response,
)
from soundbridge.app.dtos.create_preset_dto import CreatePresetCommand
from soundbridge.app.dtos.track_discover_dto import DiscoverCommand
from soundbridge.app.ports.input.create_preset_use_case import CreatePresetUseCase
from soundbridge.app.ports.input.track_discover_use_case import TrackDiscoverUseCase
from soundbridge.dependencies.create_preset_provider import get_create_preset_use_case
from soundbridge.dependencies.track_discover_provider import get_track_discover_use_case
from soundbridge.infrastructure.exceptions import GeminiApiException, TrackNotFoundException

router = APIRouter()


@router.post("", response_model=DiscoverResponseSchema)
async def discover_gugak(
    body: DiscoverRequestSchema,
    use_case: TrackDiscoverUseCase = Depends(get_track_discover_use_case),
    preset_use_case: CreatePresetUseCase = Depends(get_create_preset_use_case),
) -> DiscoverResponseSchema:
    try:
        command = DiscoverCommand(input_text=body.input, lang=body.lang, enrich=body.enrich)
        result = await use_case.discover(command=command)
        for track in result.tracks:
            if track.emotion_tags:
                preset = preset_use_case.build_preset_url(
                    CreatePresetCommand(
                        track_id=track.track_id,
                        instrument=track.instrument,
                        emotion=track.emotion_tags[0],
                        bpm=track.bpm,
                    )
                )
                track.preset_url = preset.full_url
        return to_discover_response(result)
    except GeminiApiException as e:
        raise HTTPException(status_code=503, detail=str(e) or "AI 서비스 일시 오류") from None
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=503,
            detail="매칭 설명 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/suggest", response_model=TrackSuggestResponseSchema)
async def suggest_released_tracks(
    q: str = "",
    limit: int = 8,
) -> TrackSuggestResponseSchema:
    """정식 발매 곡 자동완성 (iTunes Search API)."""
    adapter = ItunesSearchAdapter()
    items = await adapter.search_songs(q, limit=min(max(limit, 1), 15))
    return TrackSuggestResponseSchema(
        suggestions=[TrackSuggestionSchema(**item) for item in items]
    )


@router.get("/popular", response_model=list[TrackResponseSchema])
async def get_popular_tracks(
    limit: int = 6,
    use_case: TrackDiscoverUseCase = Depends(get_track_discover_use_case),
) -> list[TrackResponseSchema]:
    tracks = await use_case.get_popular_tracks(limit)
    return [to_track_response(t) for t in tracks]


@router.get("/{track_id}", response_model=DiscoverResponseSchema)
async def get_track_detail(
    track_id: str,
    use_case: TrackDiscoverUseCase = Depends(get_track_discover_use_case),
) -> DiscoverResponseSchema:
    try:
        result = await use_case.get_track_detail(track_id)
        return to_discover_response(result)
    except TrackNotFoundException:
        raise HTTPException(status_code=404, detail="트랙을 찾을 수 없습니다") from None
