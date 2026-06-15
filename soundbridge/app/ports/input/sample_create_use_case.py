# 레이어: Application — CREATE 샘플 조회 포트
from abc import ABC, abstractmethod

from soundbridge.app.dtos.sample_create_dto import SampleFilterCommand, SampleListResult


class SampleCreateUseCase(ABC):

    @abstractmethod
    async def list_samples(self, command: SampleFilterCommand) -> SampleListResult:
        ...
