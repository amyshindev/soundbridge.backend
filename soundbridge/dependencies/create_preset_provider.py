# 레이어: Dependencies — CREATE 프리셋 DI 조립
from soundbridge.app.ports.input.create_preset_use_case import CreatePresetUseCase
from soundbridge.app.use_cases.create_preset_interactor import CreatePresetInteractor


def get_create_preset_use_case() -> CreatePresetUseCase:
    return CreatePresetInteractor()
