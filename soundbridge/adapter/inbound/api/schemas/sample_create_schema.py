from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

from soundbridge.adapter.inbound.api.schemas.track_response_schema import TrackResponseSchema


class SampleFilterSchema(BaseModel):
    """CREATE 샘플 목록 쿼리 — list 필드는 Query() 로 명시해야 GET 배열 파라미터가 바인딩됨."""

    instruments: Annotated[list[str] | None, Query()] = None
    genres: Annotated[list[str] | None, Query()] = None
    jangdans: Annotated[list[str] | None, Query()] = None
    emotions: Annotated[list[str] | None, Query()] = None
    bpm_min: int | None = Field(None, ge=0, le=300)
    bpm_max: int | None = Field(None, ge=0, le=300)
    loop_unit: int | None = None
    license: str | None = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)


class SampleListResponseSchema(BaseModel):
    tracks: list[TrackResponseSchema]
    total: int
