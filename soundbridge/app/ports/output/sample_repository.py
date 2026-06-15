# 레이어: Application — Sample 조회 포트
from abc import ABC, abstractmethod

from soundbridge.app.dtos.sample_create_dto import SampleFilterCommand
from soundbridge.domain.entities.track_entity import GugakTrack


class SampleRepository(ABC):

    @abstractmethod
    async def find_samples(
        self, command: SampleFilterCommand
    ) -> tuple[list[GugakTrack], int]:
        ...
