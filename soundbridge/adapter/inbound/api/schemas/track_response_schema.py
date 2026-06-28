from uuid import UUID

from pydantic import BaseModel


class CuePointSchema(BaseModel):
    time_sec: float
    label: str
    emotion: str


class TrackResponseSchema(BaseModel):
    id: UUID
    title: str
    artist: str
    instrument: str
    jangdan: str
    emotion_tags: list[str]
    bpm: int
    loop_unit_beats: int
    cue_points: list[CuePointSchema]
    audio_url: str
    license_type: str
    license_label_en: str
    description_ko: str
    description_en: str
    genre: str = ""
    score: float | None = None
    explanation: str | None = None
    preset_url: str | None = None
