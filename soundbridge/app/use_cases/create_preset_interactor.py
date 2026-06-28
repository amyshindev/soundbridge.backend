# 레이어: Application — DISCOVER→CREATE 프리셋 URL 변환 유스케이스
from soundbridge.app.policies.create_preset_policy import (
    PRESET_BPM_MARGIN,
    PRESET_BPM_MAX_CEIL,
    PRESET_BPM_MIN_FLOOR,
)
from soundbridge.app.dtos.create_preset_dto import CreatePresetCommand, CreatePresetResult
from soundbridge.app.ports.input.create_preset_use_case import CreatePresetUseCase


class CreatePresetInteractor(CreatePresetUseCase):
    def build_preset_url(self, command: CreatePresetCommand) -> CreatePresetResult:
        bpm_min = max(PRESET_BPM_MIN_FLOOR, command.bpm - PRESET_BPM_MARGIN)
        bpm_max = min(PRESET_BPM_MAX_CEIL, command.bpm + PRESET_BPM_MARGIN)

        params: dict[str, str] = {}
        if command.instrument:
            params["instrument"] = command.instrument
        if command.emotion:
            params["emotion"] = command.emotion
        params["bpm_min"] = str(bpm_min)
        params["bpm_max"] = str(bpm_max)

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"/create?{query_string}"

        return CreatePresetResult(
            instrument=command.instrument,
            emotion=command.emotion,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            query_string=query_string,
            full_url=full_url,
        )
