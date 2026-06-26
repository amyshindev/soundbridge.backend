from pydantic import BaseModel, Field

from soundbridge.adapter.inbound.api.schemas.track_response_schema import TrackResponseSchema


class DiscoverRequestSchema(BaseModel):
    input: str = Field(..., min_length=1, max_length=200)
    lang: str = Field(default="ko", pattern="^(ko|en)$")
    enrich: bool = Field(
        default=False,
        description="true면 Ollama(EXAONE)로 매칭 설명 생성(느림). 기본은 템플릿 설명",
    )


class DiscoverResponseSchema(BaseModel):
    tracks: list[TrackResponseSchema]
    input_summary: str
