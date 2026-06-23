from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class DiscoverCommand:
    input_text: str
    lang: str = "ko"
    enrich: bool = False


@dataclass
class EmotionAnalysisResult:
    emotions: list[str]
    mood: str
    instrument_hints: list[str]
    embed_text: str


@dataclass
class MatchExplanation:
    track_id: UUID
    score: float
    explanation_ko: str
    explanation_en: str


@dataclass
class TrackResult:
    track_id: UUID
    title: str
    artist: str
    instrument: str
    jangdan: str
    emotion_tags: list[str]
    bpm: int
    loop_unit_beats: int
    cue_points: list[dict]
    audio_url: str
    license_type: str
    license_label_en: str
    description_ko: str
    description_en: str
    score: float | None = None
    explanation: str | None = None
    preset_url: str | None = None


@dataclass
class DiscoverResult:
    tracks: list[TrackResult]
    input_summary: str
