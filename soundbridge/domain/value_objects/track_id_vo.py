# 레이어: Domain — TrackId UUID 래퍼
from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TrackId:
    value: UUID
