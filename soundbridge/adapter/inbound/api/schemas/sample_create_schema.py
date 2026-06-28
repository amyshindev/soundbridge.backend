from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

from soundbridge.app.policies.sample_list_policy import (
    SAMPLE_BPM_MAX,
    SAMPLE_BPM_MIN,
    SAMPLE_LIST_DEFAULT_LIMIT,
    SAMPLE_LIST_MAX_LIMIT,
)

from soundbridge.adapter.inbound.api.schemas.track_response_schema import TrackResponseSchema


class SampleFilterSchema(BaseModel):
    """CREATE 샘플 목록 쿼리 — list 필드는 Query() 로 명시해야 GET 배열 파라미터가 바인딩됨."""

    instruments: Annotated[list[str] | None, Query()] = None
    genres: Annotated[list[str] | None, Query()] = None
    jangdans: Annotated[list[str] | None, Query()] = None
    emotions: Annotated[list[str] | None, Query()] = None
    bpm_min: int | None = Field(None, ge=SAMPLE_BPM_MIN, le=SAMPLE_BPM_MAX)
    bpm_max: int | None = Field(None, ge=SAMPLE_BPM_MIN, le=SAMPLE_BPM_MAX)
    loop_unit: int | None = None
    license: str | None = None
    limit: int = Field(default=SAMPLE_LIST_DEFAULT_LIMIT, le=SAMPLE_LIST_MAX_LIMIT)
    offset: int = Field(default=0, ge=0)


class SampleListResponseSchema(BaseModel):
    tracks: list[TrackResponseSchema]
    total: int
