# 레이어: Inbound Mapper — CREATE 샘플 필터 변환 (확장용)
from soundbridge.adapter.inbound.api.schemas.sample_create_schema import SampleFilterSchema
from soundbridge.app.dtos.sample_create_dto import SampleFilterCommand


def to_sample_filter_command(filters: SampleFilterSchema) -> SampleFilterCommand:
    return SampleFilterCommand(
        instruments=filters.instruments,
        genres=filters.genres,
        jangdans=filters.jangdans,
        emotions=filters.emotions,
        bpm_min=filters.bpm_min,
        bpm_max=filters.bpm_max,
        loop_unit=filters.loop_unit,
        license_type=filters.license,
        limit=filters.limit,
        offset=filters.offset,
    )
