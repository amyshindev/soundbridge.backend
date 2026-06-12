from uuid import UUID

from pydantic import BaseModel, Field


class DiscoverRequestSchema(BaseModel):
    input: str = Field(..., min_length=1, max_length=200)
    lang: str = Field(default="ko", pattern="^(ko|en)$")


class CuePointSchema(BaseModel):
    time_sec: float
    label: str
    emotion: str


class TrackResponseSchema(BaseModel):
    id: UUID
    title: str
    artist: str
    instrument: str
    jangdan: str
    emotion_tags: list[str]
    bpm: int
    loop_unit_beats: int
    cue_points: list[CuePointSchema]
    audio_url: str
    license_type: str
    license_label_en: str
    description_ko: str
    description_en: str
    score: float | None = None
    explanation: str | None = None
    preset_url: str | None = None


class DiscoverResponseSchema(BaseModel):
    tracks: list[TrackResponseSchema]
    input_summary: str


class SampleFilterSchema(BaseModel):
    instruments: list[str] | None = None
    jangdans: list[str] | None = None
    emotions: list[str] | None = None
    bpm_min: int | None = Field(None, ge=40, le=300)
    bpm_max: int | None = Field(None, ge=40, le=300)
    loop_unit: int | None = None
    license: str | None = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)


class SampleListResponseSchema(BaseModel):
    tracks: list[TrackResponseSchema]
    total: int
