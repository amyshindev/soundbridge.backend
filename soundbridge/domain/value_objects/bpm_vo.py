# 레이어: Domain — BPM 검증·TM tempo 파싱
import re
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


def parse_tm_bpm(tempo: str) -> int:
    """TM tempo 필드 → 정수 BPM (없으면 0)."""
    tempo = (tempo or "").strip()
    if not tempo or tempo.upper() == "N/A":
        return 0
    match = re.search(r"\d+", tempo)
    return int(match.group()) if match else 0
