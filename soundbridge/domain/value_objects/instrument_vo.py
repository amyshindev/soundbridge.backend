# 레이어: Domain — 악기 VO
from enum import Enum

# 국악 API 악기 코드 → enum 한글명 (구 DB 적재분 호환)
INSTRUMENT_CODE_MAP: dict[str, str] = {
    "PHINST0022": "장구",
    "PHINST0001": "가야금",
    "PHINST0002": "대금",
    "PHINST0003": "해금",
    "PHINST0004": "거문고",
    "PHINST0005": "피리",
    "PHINST0006": "아쟁",
    "PHINST0007": "소금",
    "소금": "소금",
}


class Instrument(str, Enum):
    GAYAGEUM = "가야금"
    GEOUMONGO = "거문고"
    DAEGEUM = "대금"
    PIRI = "피리"
    HAEGEUM = "해금"
    AJAENG = "아쟁"
    JANGGU = "장구"
    SOGO = "소고"
    SOGEUM = "소금"
    PANSORI = "판소리"
    VOCAL = "가창"
    OTHER = "미분류"

    @classmethod
    def from_db_value(cls, raw: str) -> "Instrument":
        name = INSTRUMENT_CODE_MAP.get((raw or "").strip(), (raw or "").strip())
        try:
            return cls(name)
        except ValueError:
            return cls.OTHER
