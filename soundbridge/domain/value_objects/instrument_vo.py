# 레이어: Domain — 악기 VO (TM genre_mclsf 기반 추론)
from enum import Enum


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
        name = (raw or "").strip()
        try:
            return cls(name)
        except ValueError:
            return cls.OTHER


def infer_instrument_from_tm_genre(genre_mclsf: str) -> str:
    """TM genre_mclsf → gugak_tracks.instrument 문자열."""
    genre_mclsf = (genre_mclsf or "").strip()
    if genre_mclsf == Instrument.PANSORI.value:
        return Instrument.PANSORI.value
    if genre_mclsf == "불교음악":
        return Instrument.VOCAL.value
    if genre_mclsf in ("민요", "풍류음악", "궁중음악"):
        return Instrument.VOCAL.value
    return Instrument.OTHER.value
