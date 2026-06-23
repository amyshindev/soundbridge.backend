from pydantic import BaseModel, Field

from soundbridge.adapter.inbound.api.schemas.track_response_schema import TrackResponseSchema


class DiscoverRequestSchema(BaseModel):
    input: str = Field(..., min_length=1, max_length=200)
    lang: str = Field(default="ko", pattern="^(ko|en)$")


class DiscoverResponseSchema(BaseModel):
    tracks: list[TrackResponseSchema]
    input_summary: str
