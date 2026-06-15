# 레이어: Inbound — CREATE 프리셋 URL 스키마
from pydantic import BaseModel


class CreatePresetResponseSchema(BaseModel):
    instrument: str
    emotion: str
    bpm_min: int
    bpm_max: int
    full_url: str
