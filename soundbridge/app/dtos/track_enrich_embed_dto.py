# 레이어: Application — TM enrich+embed 배치 DTO
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class TrackEnrichTarget:
    id: UUID
    title: str
    artist: str
    instrument: str
    genre_lclsf: str
    genre_mclsf: str
    genre_sclsf: str
    jangdan_name: str
    jangdan_raw: str
    time_signature: str
    tempo_label: str
    description_ko: str
    whole_emotions: list[dict]
    whole_tones: list[dict]
    emotion_tags: list[str]


@dataclass
class EnrichEmbedCommand:
    dry_run: bool = False
    limit: int | None = None
    force: bool = False
    tm_only: bool = True
    batch_size: int = 3
    batch_interval_sec: float = 2.0
    enrich_only: bool = False
    embed_only: bool = False


@dataclass
class EnrichEmbedRunResult:
    success: int = 0
    failed: int = 0
    elapsed_sec: float = 0.0
    errors: list[str] = field(default_factory=list)
