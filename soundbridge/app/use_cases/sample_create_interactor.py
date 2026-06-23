# 레이어: Application — CREATE 샘플 조회 유스케이스
from soundbridge.app.dtos.sample_create_dto import SampleFilterCommand, SampleListResult
from soundbridge.adapter.outbound.mappers.track_result_mapper import to_track_result
from soundbridge.app.ports.input.sample_create_use_case import SampleCreateUseCase
from soundbridge.app.ports.output.sample_repository import SampleRepository


class SampleCreateInteractor(SampleCreateUseCase):

    def __init__(self, sample_repo: SampleRepository) -> None:
        self._sample_repo = sample_repo

    async def list_samples(self, command: SampleFilterCommand) -> SampleListResult:
        tracks, total = await self._sample_repo.find_samples(command)
        return SampleListResult(
            tracks=[to_track_result(t) for t in tracks],
            total=total,
        )
