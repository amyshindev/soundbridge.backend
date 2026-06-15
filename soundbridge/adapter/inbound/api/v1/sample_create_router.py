# 레이어: Inbound — CREATE HTTP 엔드포인트
from fastapi import APIRouter, Depends

from soundbridge.adapter.inbound.api.schemas.track_discover_schema import (
    SampleFilterSchema,
    SampleListResponseSchema,
    TrackResponseSchema,
)
from soundbridge.adapter.inbound.mappers.track_discover_mapper import to_track_response
from soundbridge.app.dtos.sample_create_dto import SampleFilterCommand
from soundbridge.app.ports.input.sample_create_use_case import SampleCreateUseCase
from soundbridge.dependencies.sample_create_provider import get_sample_create_use_case

router = APIRouter()


@router.get("/samples", response_model=SampleListResponseSchema)
async def list_samples(
    filters: SampleFilterSchema = Depends(),
    use_case: SampleCreateUseCase = Depends(get_sample_create_use_case),
) -> SampleListResponseSchema:
    command = SampleFilterCommand(
        instruments=filters.instruments,
        jangdans=filters.jangdans,
        emotions=filters.emotions,
        bpm_min=filters.bpm_min,
        bpm_max=filters.bpm_max,
        loop_unit=filters.loop_unit,
        license_type=filters.license,
        limit=filters.limit,
        offset=filters.offset,
    )
    result = await use_case.list_samples(command)
    return SampleListResponseSchema(
        tracks=[to_track_response(t) for t in result.tracks],
        total=result.total,
    )
