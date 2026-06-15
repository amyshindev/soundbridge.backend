# 레이어: Application — DISCOVER→CREATE 프리셋 URL 변환 포트
from abc import ABC, abstractmethod

from soundbridge.app.dtos.create_preset_dto import CreatePresetCommand, CreatePresetResult


class CreatePresetUseCase(ABC):

    @abstractmethod
    def build_preset_url(self, command: CreatePresetCommand) -> CreatePresetResult:
        ...
