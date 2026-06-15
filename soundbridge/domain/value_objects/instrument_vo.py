# 레이어: Domain — 악기 VO
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
