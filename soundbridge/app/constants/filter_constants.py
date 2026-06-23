# CREATE 샘플 필터·페이지네이션 기본값
SAMPLE_LIST_DEFAULT_LIMIT = 50
SAMPLE_LIST_MAX_LIMIT = 100
SAMPLE_BPM_MIN = 40
SAMPLE_BPM_MAX = 300
POPULAR_TRACKS_DEFAULT_LIMIT = 6

VALID_INSTRUMENTS: tuple[str, ...] = (
    "가야금",
    "거문고",
    "대금",
    "해금",
    "피리",
    "아쟁",
    "장구",
    "소고",
)

VALID_JANGDANS: tuple[str, ...] = (
    "자진모리",
    "중모리",
    "굿거리",
    "휘모리",
    "세마치",
    "엇모리",
)

VALID_EMOTIONS: tuple[str, ...] = (
    "신남",
    "서정",
    "웅장",
    "슬픔",
    "신비",
    "차분",
)
