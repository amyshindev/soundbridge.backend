# 레이어: Application — CREATE 샘플 필터 DTO
from dataclasses import dataclass

from soundbridge.app.dtos.track_discover_dto import TrackResult
from soundbridge.app.policies.sample_list_policy import SAMPLE_LIST_DEFAULT_LIMIT


@dataclass
class SampleFilterCommand:
    instruments: list[str] | None = None
    genres: list[str] | None = None
    jangdans: list[str] | None = None
    emotions: list[str] | None = None
    bpm_min: int | None = None
    bpm_max: int | None = None
    loop_unit: int | None = None
    license_type: str | None = None
    limit: int = SAMPLE_LIST_DEFAULT_LIMIT
    offset: int = 0


@dataclass
class SampleListResult:
    tracks: list[TrackResult]
    total: int
