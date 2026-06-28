# 레이어: Inbound Mapper — DTO → API Schema 변환
from soundbridge.app.dtos.track_discover_dto import DiscoverResult, TrackResult
from soundbridge.adapter.inbound.api.schemas.track_discover_schema import DiscoverResponseSchema
from soundbridge.adapter.inbound.api.schemas.track_response_schema import (
    CuePointSchema,
    TrackResponseSchema,
)


def to_track_response(track: TrackResult) -> TrackResponseSchema:
    return TrackResponseSchema(
        id=track.track_id,
        title=track.title,
        artist=track.artist,
        instrument=track.instrument,
        jangdan=track.jangdan,
        emotion_tags=track.emotion_tags,
        bpm=track.bpm,
        loop_unit_beats=track.loop_unit_beats,
        cue_points=[CuePointSchema(**cp) for cp in track.cue_points],
        audio_url=track.audio_url,
        license_type=track.license_type,
        license_label_en=track.license_label_en,
        description_ko=track.description_ko,
        description_en=track.description_en,
        genre=track.genre,
        score=track.score,
        explanation=track.explanation,
        preset_url=track.preset_url,
    )


def to_discover_response(result: DiscoverResult) -> DiscoverResponseSchema:
    return DiscoverResponseSchema(
        tracks=[to_track_response(t) for t in result.tracks],
        input_summary=result.input_summary,
    )
