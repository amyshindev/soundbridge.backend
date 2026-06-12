# 레이어: Domain — 장단 VO (loop_unit_beats 매핑 포함)
from dataclasses import dataclass
from enum import Enum


class JangdanType(str, Enum):
    JAJINMORI = "자진모리"
    JUNGMORI = "중모리"
    GUTGEORI = "굿거리"
    HWIMORI = "휘모리"
    SEMACHI = "세마치"
    EOTMORI = "엇모리"


JANGDAN_LOOP_UNITS: dict[JangdanType, int] = {
    JangdanType.JAJINMORI: 12,
    JangdanType.JUNGMORI: 12,
    JangdanType.GUTGEORI: 12,
    JangdanType.HWIMORI: 4,
    JangdanType.SEMACHI: 6,
    JangdanType.EOTMORI: 10,
}


@dataclass(frozen=True)
class Jangdan:
    type: JangdanType

    @property
    def loop_unit_beats(self) -> int:
        return JANGDAN_LOOP_UNITS[self.type]
