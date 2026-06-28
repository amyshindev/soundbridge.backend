# 레이어: Application — TM 트랙 EXAONE 풍부화 정책
MIN_ENRICHED_LEN = 80
DEFAULT_BATCH_SIZE = 3
DEFAULT_BATCH_INTERVAL_SEC = 2.0

TRACK_ENRICH_PROMPT = """당신은 국악 전문가입니다.
아래 국악 트랙 정보를 바탕으로, 이 곡의 감성·분위기·문화적 맥락을 
풍부하게 설명하는 3-4문장의 한국어 텍스트를 작성하세요.

다음 내용을 포함하세요:
- 이 곡의 음악적 특성과 감성
- 장단이 주는 리듬감과 분위기
- 한국 문화적 맥락에서의 의미
- 어떤 감정 상태의 사람에게 어울릴지

트랙 정보:
제목: {title}
연주자: {artist}
악기: {instrument}
장단: {jangdan}
감성 태그: {emotions}
기존 설명: {description}

풍부한 설명 (3-4문장, 한국어만):"""
