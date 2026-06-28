# 레이어: Domain — 장단 VO (loop_unit_beats 매핑 + TM 캡션 추출)
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

JANGDAN_KEYWORDS: tuple[str, ...] = (
    "엇모리",
    "휘모리",
    "세마치",
    "굿거리",
    "중모리",
    "자진모리",
    "도드리",
)

VALID_JANGDAN_NAMES: frozenset[str] = frozenset(member.value for member in JangdanType)
DISCOVER_JANGDAN_VALUES: tuple[str, ...] = tuple(member.value for member in JangdanType)


@dataclass(frozen=True)
class Jangdan:
    type: JangdanType

    @property
    def loop_unit_beats(self) -> int:
        return JANGDAN_LOOP_UNITS[self.type]

    @classmethod
    def from_name(cls, name: str, *, default: JangdanType = JangdanType.JAJINMORI) -> "Jangdan":
        try:
            return cls(type=JangdanType(name))
        except ValueError:
            return cls(type=default)


def extract_jangdan_from_caption(caption_ko: str) -> tuple[str, str]:
    """TM 라벨링 캡션에서 (jangdan_name FK, jangdan_raw) 추출."""
    for keyword in JANGDAN_KEYWORDS:
        if keyword in caption_ko:
            fk = keyword if keyword in VALID_JANGDAN_NAMES else JangdanType.JUNGMORI.value
            return fk, keyword
    return JangdanType.JAJINMORI.value, ""
