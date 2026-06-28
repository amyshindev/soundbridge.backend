# 레이어: Application — CREATE 샘플 목록·필터 정책
SAMPLE_LIST_DEFAULT_LIMIT = 50
SAMPLE_LIST_MAX_LIMIT = 100
SAMPLE_BPM_MIN = 40
SAMPLE_BPM_MAX = 300

# CREATE UI 필터에 노출하는 악기 (전체 Instrument enum의 부분집합)
CREATE_FILTER_INSTRUMENTS: tuple[str, ...] = (
    "가야금",
    "거문고",
    "대금",
    "해금",
    "피리",
    "아쟁",
    "장구",
    "소고",
)
