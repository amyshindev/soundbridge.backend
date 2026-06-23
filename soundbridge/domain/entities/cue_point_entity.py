# 레이어: Domain — CUE 포인트 엔티티
from dataclasses import dataclass


@dataclass
class CuePoint:
    time_sec: float
    label: str
    emotion: str
