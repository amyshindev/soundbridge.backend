# 레이어: Domain — GugakTrack 핵심 엔티티 (프레임워크 무관)
from dataclasses import dataclass
from uuid import UUID

from soundbridge.domain.value_objects.emotion_vo import EmotionTag
from soundbridge.domain.value_objects.instrument_vo import Instrument
from soundbridge.domain.value_objects.jangdan_vo import Jangdan
from soundbridge.domain.value_objects.license_vo import LICENSE_IS_COMMERCIAL, PublicLicense


@dataclass
class CuePoint:
    time_sec: float
    label: str
    emotion: str


@dataclass
class GugakTrack:
    id: UUID
    title: str
    artist: str
    instrument: Instrument
    jangdan: Jangdan
    emotion_tags: list[EmotionTag]
    bpm: int
    cue_points: list[CuePoint]
    audio_url: str
    public_license: PublicLicense
    description_ko: str
    description_en: str

    @property
    def loop_unit_beats(self) -> int:
        return self.jangdan.loop_unit_beats

    @property
    def is_commercial(self) -> bool:
        return LICENSE_IS_COMMERCIAL[self.public_license]

    @property
    def primary_emotion(self) -> EmotionTag | None:
        return self.emotion_tags[0] if self.emotion_tags else None
