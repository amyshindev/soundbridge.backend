# 레이어: Inbound — CREATE HTTP 엔드포인트
from fastapi import APIRouter, Depends, Query

from soundbridge.adapter.inbound.api.schemas.sample_create_schema import SampleListResponseSchema
from soundbridge.adapter.inbound.mappers.track_discover_mapper import to_track_response
from soundbridge.app.dtos.sample_create_dto import SampleFilterCommand
from soundbridge.app.ports.input.sample_create_use_case import SampleCreateUseCase
from soundbridge.dependencies.sample_create_provider import get_sample_create_use_case

router = APIRouter()


@router.get("/samples", response_model=SampleListResponseSchema)
async def list_samples(
    instruments: list[str] = Query(default=[]),
    genres: list[str] = Query(default=[]),
    jangdans: list[str] = Query(default=[]),
    emotions: list[str] = Query(default=[]),
    bpm_min: int | None = Query(None, ge=0, le=300),
    bpm_max: int | None = Query(None, ge=0, le=300),
    loop_unit: int | None = Query(None),
    license: str | None = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    use_case: SampleCreateUseCase = Depends(get_sample_create_use_case),
) -> SampleListResponseSchema:
    command = SampleFilterCommand(
        instruments=instruments or None,
        genres=genres or None,
        jangdans=jangdans or None,
        emotions=emotions or None,
        bpm_min=bpm_min,
        bpm_max=bpm_max,
        loop_unit=loop_unit,
        license_type=license,
        limit=limit,
        offset=offset,
    )
    result = await use_case.list_samples(command)
    return SampleListResponseSchema(
        tracks=[to_track_response(t) for t in result.tracks],
        total=result.total,
    )
