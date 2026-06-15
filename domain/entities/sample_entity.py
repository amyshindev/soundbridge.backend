# 레이어: Domain — Sample 엔티티 (CREATE 필터 결과)
from dataclasses import dataclass

from soundbridge.domain.entities.track_entity import GugakTrack


@dataclass
class Sample:
    track: GugakTrack
