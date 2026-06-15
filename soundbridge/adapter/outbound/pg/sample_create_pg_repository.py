# 레이어: Outbound — SampleRepository 구현
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.adapter.outbound.pg.track_discover_pg_repository import TrackDiscoverPgRepository
from soundbridge.app.dtos.sample_create_dto import SampleFilterCommand
from soundbridge.app.ports.output.sample_repository import SampleRepository
from soundbridge.domain.entities.track_entity import GugakTrack


class SampleCreatePgRepository(SampleRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._track_repo = TrackDiscoverPgRepository(session)

    async def find_samples(
        self, command: SampleFilterCommand
    ) -> tuple[list[GugakTrack], int]:
        return await self._track_repo.find_with_filters(
            instruments=command.instruments,
            jangdans=command.jangdans,
            emotions=command.emotions,
            bpm_min=command.bpm_min,
            bpm_max=command.bpm_max,
            loop_unit=command.loop_unit,
            license_type=command.license_type,
            limit=command.limit,
            offset=command.offset,
        )
