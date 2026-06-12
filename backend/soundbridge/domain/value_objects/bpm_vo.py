# 레이어: Domain — BPM 범위 검증 VO
from dataclasses import dataclass


@dataclass(frozen=True)
class BpmRange:
    min_bpm: int
    max_bpm: int

    def __post_init__(self) -> None:
        if self.min_bpm < 40 or self.max_bpm > 300:
            raise ValueError("BPM must be between 40 and 300")
        if self.min_bpm > self.max_bpm:
            raise ValueError("min_bpm cannot exceed max_bpm")
