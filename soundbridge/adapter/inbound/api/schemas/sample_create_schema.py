from pydantic import BaseModel, Field

from soundbridge.adapter.inbound.api.schemas.track_response_schema import TrackResponseSchema


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
