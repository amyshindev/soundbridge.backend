# 레이어: Application — DISCOVER→CREATE 프리셋 변환 DTO
from dataclasses import dataclass
from uuid import UUID


@dataclass
class CreatePresetCommand:
    track_id: UUID
    instrument: str
    emotion: str
    bpm: int


@dataclass
class CreatePresetResult:
    instrument: str
    emotion: str
    bpm_min: int
    bpm_max: int
    query_string: str
    full_url: str
