# SoundBridge — 백엔드 개발 명세서

> 버전: v4.0
> 작성일: 2026.06.12
> 목적: Cursor / Claude / Antigravity AI 작업 지시용
> 아키텍처: Hexagonal + Clean Architecture + DDD (Titanic 패턴 준용)
> 런타임: Python 3.13 / FastAPI / AsyncIO
> DB: NeonDB (PostgreSQL + pgvector) / Redis
> 변경 이력: v1.0 대비 마일스톤 분리, CREATE 프리셋 유스케이스 추가, 인증 관련 MVP 제외 명시 / v3.1 Claude API → Gemini API 교체 (MVP AI 엔진 변경) / v4.0 emotion_tags 1NF 정규화 분리 (track_emotion_tags 테이블 신규), jangdan 3NF 정규화 분리 (jangdan 마스터 테이블 신규), ORM 프랙탈 네이밍 파일 분리 (track_emotion_tag_orm.py · jangdan_orm.py), match_logs.similarity_score String→Float 타입 수정

---

## 0. AI 작업 원칙

```
1. 이 문서는 작업 단위(Task)로 구성된다.
   각 Task는 독립적으로 실행 가능하며, 순서대로 진행한다.

2. Titanic 패턴을 그대로 따른다:
   - 프랙탈 네이밍: {domain}_{character}_{layer_suffix}
   - 레이어 의존 방향: Router → UseCase(Port) → Interactor → Repository(Port) → PgRepository
   - Domain은 FastAPI·SQLAlchemy·외부 API를 절대 import하지 않는다
   - Router는 PgRepository를 직접 import하지 않는다
   - Interactor는 ORM·HTTPException을 import하지 않는다

3. 코드 생성 규칙:
   - Python type hint 100% 적용
   - async/await 일관 사용 (sync 함수 금지)
   - Pydantic v2 사용
   - SQLAlchemy 2.0 async 스타일
   - 모든 ID는 UUID (str 아님)
   - 에러는 도메인 예외(DomainException) → HTTPException 변환은 Router에서만

4. 파일 생성 시:
   - 경로를 정확히 명시한다
   - TODO 주석으로 미구현 부분 명시
   - 각 파일 상단에 레이어·책임 주석 1줄 필수
   - 마일스톤 주석 표시: # [MVP] / # [v1.1] / # [v1.2]

5. 금지 사항:
   - Domain 레이어에서 외부 패키지 import
   - Router에서 직접 DB 쿼리
   - Interactor에서 HTTP 상태코드 처리
   - any 타입 사용 (Dict[str, Any] 최소화)
   - MVP에서 v1.1 이후 기능 구현 (TODO 주석으로 위치만 표시)

6. [v4.0 추가] 정규화 원칙:
   - emotion_tags는 ARRAY 컬럼 금지 → track_emotion_tags 테이블 사용 (1NF)
   - loop_unit_beats는 gugak_tracks에 직접 저장 금지 → jangdan FK로 참조 (3NF)
   - ORM 파일은 테이블 1개당 1파일 원칙 (프랙탈 네이밍)
   - joinedload 전략은 Repository 내부에서만 결정 (포트 인터페이스 노출 금지)
   - cue_points JSONB는 의도적 비정규화 — WaveSurfer.js 전달 전용, 단독 쿼리 없음
```

---

## 1. 프로젝트 구조

### Task 1-1. 디렉터리 생성

[MVP] / [v1.1] 표시가 없는 파일은 해당 마일스톤 도달 시 추가한다.

```
soundbridge/
├── domain/
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── track_entity.py          GugakTrack 엔티티              [MVP]
│   │   ├── sample_entity.py         Sample 엔티티                  [MVP]
│   │   ├── user_entity.py           User 엔티티                    [v1.1]
│   │   ├── saved_track_entity.py    SavedTrack 엔티티              [v1.1]
│   │   ├── cue_point_entity.py      CuePoint 엔티티                [MVP]
│   │   ├── match_log_entity.py      MatchLog 엔티티                [MVP]
│   │   └── download_log_entity.py   DownloadLog 엔티티             [v1.1]
│   └── value_objects/
│       ├── __init__.py
│       ├── track_id_vo.py           TrackId (UUID 래퍼)            [MVP]
│       ├── user_id_vo.py            UserId                         [v1.1]
│       ├── emotion_vo.py            EmotionTag (enum)              [MVP]
│       ├── jangdan_vo.py            Jangdan (enum + loop_unit 매핑)[MVP]
│       ├── instrument_vo.py         Instrument (enum)              [MVP]
│       ├── license_vo.py            PublicLicense (enum)           [MVP]
│       ├── bpm_vo.py                BpmRange (min/max 검증)        [MVP]
│       └── auth_provider_vo.py      AuthProvider (enum)            [v1.1]
│
├── app/
│   ├── ports/
│   │   ├── input/
│   │   │   ├── __init__.py
│   │   │   ├── track_discover_use_case.py                          [MVP]
│   │   │   ├── sample_create_use_case.py                           [MVP]
│   │   │   ├── create_preset_use_case.py   DISCOVER→CREATE 변환   [MVP]
│   │   │   ├── user_auth_use_case.py                               [v1.1]
│   │   │   ├── cue_extractor_use_case.py                           [v1.1]
│   │   │   ├── playlist_saved_use_case.py                          [v1.1]
│   │   │   └── event_kopis_use_case.py                             [v1.1]
│   │   └── output/
│   │       ├── __init__.py
│   │       ├── track_repository.py                                 [MVP]
│   │       ├── sample_repository.py                                [MVP]
│   │       ├── user_repository.py                                  [v1.1]
│   │       ├── saved_track_repository.py                           [v1.1]
│   │       ├── download_log_repository.py                          [v1.1]
│   │       ├── gemini_port.py                                      [MVP]
│   │       ├── embedding_port.py                                   [MVP]
│   │       ├── email_port.py                                       [v1.1]
│   │       └── kopis_port.py                                       [v1.1]
│   ├── use_cases/
│   │   ├── __init__.py
│   │   ├── track_discover_interactor.py                            [MVP]
│   │   ├── sample_create_interactor.py                             [MVP]
│   │   ├── create_preset_interactor.py  DISCOVER→CREATE 변환      [MVP]
│   │   ├── user_auth_interactor.py                                 [v1.1]
│   │   ├── cue_extractor_interactor.py                             [v1.1]
│   │   ├── playlist_saved_interactor.py                            [v1.1]
│   │   └── event_kopis_interactor.py                               [v1.1]
│   └── dtos/
│       ├── __init__.py
│       ├── track_discover_dto.py                                   [MVP]
│       ├── sample_create_dto.py                                    [MVP]
│       ├── create_preset_dto.py         프리셋 URL 변환 DTO        [MVP]
│       ├── user_auth_dto.py                                        [v1.1]
│       ├── cue_extractor_dto.py                                    [v1.1]
│       ├── playlist_saved_dto.py                                   [v1.1]
│       └── event_kopis_dto.py                                      [v1.1]
│
├── adapter/
│   ├── inbound/
│   │   ├── api/
│   │   │   ├── __init__.py          soundbridge_router 집계        [MVP]
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── track_discover_router.py                        [MVP]
│   │   │   │   ├── sample_create_router.py                         [MVP]
│   │   │   │   ├── user_auth_router.py                             [v1.1]
│   │   │   │   ├── cue_extractor_router.py                         [v1.1]
│   │   │   │   ├── playlist_saved_router.py                        [v1.1]
│   │   │   │   └── event_kopis_router.py                           [v1.1]
│   │   │   └── schemas/
│   │   │       ├── track_discover_schema.py                        [MVP]
│   │   │       ├── sample_create_schema.py                         [MVP]
│   │   │       ├── create_preset_schema.py  프리셋 스키마          [MVP]
│   │   │       ├── user_auth_schema.py                             [v1.1]
│   │   │       ├── cue_extractor_schema.py                         [v1.1]
│   │   │       ├── playlist_saved_schema.py                        [v1.1]
│   │   │       └── event_kopis_schema.py                           [v1.1]
│   │   └── mappers/
│   │       ├── track_discover_mapper.py                            [MVP]
│   │       ├── sample_create_mapper.py                             [MVP]
│   │       └── user_auth_mapper.py                                 [v1.1]
│   └── outbound/
│       ├── orm/
│       │   ├── base_orm.py                                         [MVP]
│       │   ├── track_orm.py             gugak_tracks               [MVP] ← v4.0 변경
│       │   ├── track_emotion_tag_orm.py track_emotion_tags         [MVP] ← v4.0 신규
│       │   ├── jangdan_orm.py           jangdan                    [MVP] ← v4.0 신규
│       │   ├── match_log_orm.py         match_logs                 [MVP] ← v4.0 변경
│       │   ├── user_orm.py              users                      [v1.1]
│       │   ├── saved_track_orm.py       saved_tracks               [v1.1]
│       │   ├── download_log_orm.py      download_logs              [v1.1]
│       │   └── email_verification_orm.py                           [v1.1]
│       ├── pg/
│       │   ├── db_init.py                                          [MVP] ← v4.0 변경
│       │   ├── track_discover_pg_repository.py                     [MVP] ← v4.0 변경
│       │   ├── sample_create_pg_repository.py                      [MVP]
│       │   ├── user_auth_pg_repository.py                          [v1.1]
│       │   ├── cue_extractor_pg_repository.py                      [v1.1]
│       │   ├── playlist_saved_pg_repository.py                     [v1.1]
│       │   └── download_log_pg_repository.py                       [v1.1]
│       ├── external/
│       │   ├── gemini_adapter.py                                   [MVP]
│       │   ├── embedding_adapter.py                                [MVP]
│       │   ├── email_adapter.py                                    [v1.1]
│       │   └── kopis_adapter.py                                    [v1.1]
│       ├── memory/
│       │   └── in_memory_track_repository.py                       [MVP]
│       └── mappers/
│           ├── track_orm_mapper.py                                 [MVP] ← v4.0 변경
│           ├── user_orm_mapper.py                                  [v1.1]
│           └── saved_track_orm_mapper.py                           [v1.1]
│
├── dependencies/
│   ├── track_discover_provider.py                                  [MVP]
│   ├── sample_create_provider.py                                   [MVP]
│   ├── user_auth_provider.py                                       [v1.1]
│   ├── cue_extractor_provider.py                                   [v1.1]
│   ├── playlist_saved_provider.py                                  [v1.1]
│   └── event_kopis_provider.py                                     [v1.1]
│
└── infrastructure/
    ├── database.py                                                  [MVP]
    ├── redis_client.py                                              [MVP]
    ├── settings.py                                                  [MVP]
    └── exceptions.py                                               [MVP]
```

**진입점:** `main.py`에서 `soundbridge_router`를 `/api/soundbridge` prefix로 등록,
startup 시 `create_soundbridge_tables()` 호출.

---

## 2. 공유 인프라

### Task 2-1. 환경변수 설정 [MVP]

**`soundbridge/infrastructure/settings.py`**

```python
# 레이어: Infrastructure — 환경변수 SSOT
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database [MVP]
    database_url: str
    redis_url: str = "redis://localhost:6379"

    # Gemini API [MVP]
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash"

    # App [MVP]
    app_env: str = "development"
    frontend_url: str = "http://localhost:3000"

    # Auth [v1.1]
    secret_key: str = ""
    access_token_expire_minutes: int = 60 * 24
    email_verify_token_expire_hours: int = 24
    google_client_id: str = ""
    google_client_secret: str = ""

    # Resend [v1.1]
    resend_api_key: str = ""
    email_from: str = "noreply@soundbridge.site"

    # KOPIS [v1.1]
    kopis_api_key: str = ""
    kto_api_key: str = ""

settings = Settings()
```

### Task 2-2. DB 연결 [MVP]

**`soundbridge/infrastructure/database.py`**

```python
# 레이어: Infrastructure — AsyncSession 팩토리
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from soundbridge.infrastructure.settings import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # NeonDB 슬립 대응
    echo=settings.app_env == "development",
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

> DATABASE_URL 형식 (SQLAlchemy async + psycopg3 드라이버):
> `postgresql+psycopg://user:password@ep-xxx.neon.tech/soundbridge?sslmode=require`

### Task 2-3. Redis 연결 [MVP]

**`soundbridge/infrastructure/redis_client.py`**

```python
# 레이어: Infrastructure — Redis 캐시 클라이언트
import redis.asyncio as aioredis
from soundbridge.infrastructure.settings import settings

redis_client: aioredis.Redis = aioredis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
)

CACHE_KEYS = {
    "discover_result": "sb:discover:{input_hash}",   # TTL 1시간
    "popular_tracks":  "sb:popular",                  # TTL 10분
    "track_detail":    "sb:track:{track_id}",         # TTL 1시간
    "kopis_events":    "sb:kopis:{track_id}",         # TTL 6시간 [v1.1]
}
CACHE_TTL = {
    "discover_result": 3600,
    "popular_tracks":  600,
    "track_detail":    3600,
    "kopis_events":    21600,
}
```

### Task 2-4. 공통 예외 [MVP]

**`soundbridge/infrastructure/exceptions.py`**

```python
# 레이어: Infrastructure — 도메인 공통 예외 (HTTP 무관)

class SoundBridgeException(Exception):
    """SoundBridge 도메인 기본 예외"""

# [MVP]
class TrackNotFoundException(SoundBridgeException): ...
class GeminiApiException(SoundBridgeException): ...
class EmbeddingException(SoundBridgeException): ...

# [v1.1]
class UserNotFoundException(SoundBridgeException): ...
class UserAlreadyExistsException(SoundBridgeException): ...
class InvalidCredentialsException(SoundBridgeException): ...
class EmailNotVerifiedException(SoundBridgeException): ...
class TokenExpiredException(SoundBridgeException): ...
class TokenInvalidException(SoundBridgeException): ...
class SavedTrackNotFoundException(SoundBridgeException): ...
class EmailSendException(SoundBridgeException): ...
```

### Task 2-5. ORM Base + db_init [MVP]

**`soundbridge/adapter/outbound/orm/base_orm.py`**

```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

**`soundbridge/adapter/outbound/pg/db_init.py`** ← v4.0 변경

```python
# 레이어: Outbound — startup 테이블 생성 + 장단 마스터 초기 데이터
from sqlalchemy import text
from soundbridge.adapter.outbound.orm.base_orm import Base
from soundbridge.infrastructure.database import engine, AsyncSessionLocal

# [MVP] ORM import — FK 참조 순서: jangdan → track → emotion_tag → match_log
from soundbridge.adapter.outbound.orm import jangdan_orm           # [v4.0 신규]
from soundbridge.adapter.outbound.orm import track_orm
from soundbridge.adapter.outbound.orm import track_emotion_tag_orm # [v4.0 신규]
from soundbridge.adapter.outbound.orm import match_log_orm
# [v1.1] user_orm, saved_track_orm, download_log_orm, email_verification_orm

from soundbridge.adapter.outbound.orm.jangdan_orm import JangdanOrm

# 장단 마스터 시드 데이터 — jangdan_vo.py의 JANGDAN_LOOP_UNITS와 일치해야 함
JANGDAN_SEED = [
    ("자진모리", 12),
    ("중모리",   12),
    ("굿거리",   12),
    ("휘모리",    4),
    ("세마치",    6),
    ("엇모리",   10),
]

async def create_soundbridge_tables() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    # 장단 마스터 데이터 시드 (없으면 insert, 있으면 skip)
    async with AsyncSessionLocal() as session:
        for name, beats in JANGDAN_SEED:
            exists = await session.get(JangdanOrm, name)
            if not exists:
                session.add(JangdanOrm(name=name, loop_unit_beats=beats))
        await session.commit()
```

---

## 3. Domain 레이어

### Task 3-1. Value Objects [MVP]

**`soundbridge/domain/value_objects/jangdan_vo.py`**

```python
# 레이어: Domain — 장단 VO (loop_unit_beats 매핑 포함)
# DB의 jangdan 테이블은 이 VO의 영속화. 도메인은 DB 구조를 모른다.
from enum import Enum
from dataclasses import dataclass

class JangdanType(str, Enum):
    JAJINMORI = "자진모리"   # 12박
    JUNGMORI  = "중모리"     # 12박
    GUTGEORI  = "굿거리"     # 12박
    HWIMORI   = "휘모리"     # 4박
    SEMACHI   = "세마치"     # 6박
    EOTMORI   = "엇모리"     # 10박

JANGDAN_LOOP_UNITS: dict[JangdanType, int] = {
    JangdanType.JAJINMORI: 12,
    JangdanType.JUNGMORI:  12,
    JangdanType.GUTGEORI:  12,
    JangdanType.HWIMORI:    4,
    JangdanType.SEMACHI:    6,
    JangdanType.EOTMORI:   10,
}

@dataclass(frozen=True)
class Jangdan:
    type: JangdanType

    @property
    def loop_unit_beats(self) -> int:
        return JANGDAN_LOOP_UNITS[self.type]
```

**`soundbridge/domain/value_objects/emotion_vo.py`**

```python
from enum import Enum

class EmotionTag(str, Enum):
    JOYFUL   = "신남"
    LYRICAL  = "서정"
    GRAND    = "웅장"
    SAD      = "슬픔"
    MYSTICAL = "신비"
    CALM     = "차분"

EMOTION_TAG_EN: dict[EmotionTag, str] = {
    EmotionTag.JOYFUL:   "Joyful",
    EmotionTag.LYRICAL:  "Lyrical",
    EmotionTag.GRAND:    "Grand",
    EmotionTag.SAD:      "Melancholic",
    EmotionTag.MYSTICAL: "Mystical",
    EmotionTag.CALM:     "Calm",
}
```

**`soundbridge/domain/value_objects/license_vo.py`**

```python
from enum import Enum

class PublicLicense(str, Enum):
    KOGL_1 = "KOGL_1"   # 출처표시 (상업 가능)
    KOGL_2 = "KOGL_2"   # 출처표시+상업금지

LICENSE_EN_LABEL: dict[PublicLicense, str] = {
    PublicLicense.KOGL_1: "CC-BY (Commercial OK)",
    PublicLicense.KOGL_2: "CC-BY-NC (Attribution Only)",
}
LICENSE_IS_COMMERCIAL: dict[PublicLicense, bool] = {
    PublicLicense.KOGL_1: True,
    PublicLicense.KOGL_2: False,
}
```

### Task 3-2. Entities [MVP]

**`soundbridge/domain/entities/track_entity.py`** ← v4.0 주석 추가

```python
# 레이어: Domain — GugakTrack 핵심 엔티티 (프레임워크 무관)
from dataclasses import dataclass
from uuid import UUID
from soundbridge.domain.value_objects.emotion_vo import EmotionTag
from soundbridge.domain.value_objects.jangdan_vo import Jangdan
from soundbridge.domain.value_objects.instrument_vo import Instrument
from soundbridge.domain.value_objects.license_vo import PublicLicense, LICENSE_IS_COMMERCIAL

@dataclass
class CuePoint:
    time_sec: float
    label: str       # "A" | "B" | "C"
    emotion: str

@dataclass
class GugakTrack:
    id: UUID
    title: str
    artist: str
    instrument: Instrument
    jangdan: Jangdan
    # [v4.0] DB상 track_emotion_tags 테이블에서 JOIN → 매퍼가 sort_order 순으로 주입
    emotion_tags: list[EmotionTag]
    bpm: int
    # [v4.0] 의도적 비정규화 — WaveSurfer.js 전달 전용 JSONB, 단독 쿼리 없음
    cue_points: list[CuePoint]
    audio_url: str
    public_license: PublicLicense
    description_ko: str
    description_en: str

    @property
    def loop_unit_beats(self) -> int:
        # jangdan VO의 JANGDAN_LOOP_UNITS 딕셔너리에서 자동 계산 (DB 직접 참조 없음)
        return self.jangdan.loop_unit_beats

    @property
    def is_commercial(self) -> bool:
        return LICENSE_IS_COMMERCIAL[self.public_license]

    @property
    def primary_emotion(self) -> EmotionTag | None:
        return self.emotion_tags[0] if self.emotion_tags else None
```

---

## 4. Application 레이어

### Task 4-1. Output Ports

**`soundbridge/app/ports/output/gemini_port.py`** [MVP]

```python
# 레이어: Application — Gemini API 아웃바운드 포트
from abc import ABC, abstractmethod
from soundbridge.app.dtos.track_discover_dto import EmotionAnalysisResult, MatchExplanation

class GeminiPort(ABC):

    @abstractmethod
    async def analyze_emotion(
        self, user_input: str, lang: str
    ) -> EmotionAnalysisResult:
        """사용자 입력 → 감성·분위기·악기 구조 분석"""
        ...

    @abstractmethod
    async def explain_match(
        self, user_input: str, tracks: list, lang: str
    ) -> list[MatchExplanation]:
        """매칭 결과 → 왜 비슷한가 설명 생성 (KO+EN 동시)"""
        ...

    @abstractmethod
    async def extract_cue_points(
        self, audio_features: dict
    ) -> "CueExtractionResult":  # [v1.1] 자동 추출
        ...
```

**`soundbridge/app/ports/output/embedding_port.py`** [MVP]

```python
from abc import ABC, abstractmethod
from uuid import UUID

class EmbeddingPort(ABC):

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """텍스트 → 1536차원 임베딩 벡터"""
        ...

    @abstractmethod
    async def find_similar_tracks(
        self,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict | None = None,
    ) -> list[UUID]:
        """pgvector 코사인 유사도 검색 → Track ID 목록"""
        ...
```

**`soundbridge/app/ports/output/track_repository.py`** [MVP]

```python
from abc import ABC, abstractmethod
from uuid import UUID
from soundbridge.domain.entities.track_entity import GugakTrack

class TrackRepository(ABC):

    @abstractmethod
    async def find_by_id(self, track_id: UUID) -> GugakTrack | None: ...

    @abstractmethod
    async def find_by_ids(self, track_ids: list[UUID]) -> list[GugakTrack]: ...

    @abstractmethod
    async def find_popular(self, limit: int = 6) -> list[GugakTrack]: ...

    @abstractmethod
    async def find_with_filters(
        self,
        instruments: list[str] | None,
        jangdans: list[str] | None,
        emotions: list[str] | None,
        bpm_min: int | None,
        bpm_max: int | None,
        loop_unit: int | None,
        license_type: str | None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[GugakTrack], int]: ...

    @abstractmethod
    async def save_match_log(
        self, input_text: str, lang: str,
        matched_track_id: UUID, similarity_score: float
    ) -> None: ...
```

**`soundbridge/app/ports/output/email_port.py`** [v1.1]

```python
from abc import ABC, abstractmethod

class EmailPort(ABC):

    @abstractmethod
    async def send_verification_email(
        self, to_email: str, name: str, token: str, lang: str
    ) -> bool: ...

    @abstractmethod
    async def send_password_reset_email(
        self, to_email: str, name: str, token: str, lang: str
    ) -> bool: ...
```

### Task 4-2. Input Ports

**`soundbridge/app/ports/input/track_discover_use_case.py`** [MVP]

```python
from abc import ABC, abstractmethod
from soundbridge.app.dtos.track_discover_dto import DiscoverCommand, DiscoverResult

class TrackDiscoverUseCase(ABC):

    @abstractmethod
    async def discover(self, command: DiscoverCommand) -> DiscoverResult: ...

    @abstractmethod
    async def get_track_detail(self, track_id: str) -> DiscoverResult: ...  # [v1.2]

    @abstractmethod
    async def get_popular_tracks(self, limit: int = 6) -> list: ...
```

**`soundbridge/app/ports/input/create_preset_use_case.py`** [MVP]

```python
# 레이어: Application — DISCOVER→CREATE 프리셋 URL 변환 포트
from abc import ABC, abstractmethod
from soundbridge.app.dtos.create_preset_dto import CreatePresetCommand, CreatePresetResult

class CreatePresetUseCase(ABC):

    @abstractmethod
    def build_preset_url(self, command: CreatePresetCommand) -> CreatePresetResult:
        """매칭된 트랙 정보 → CREATE 쿼리 파라미터 URL 생성"""
        ...
```

**`soundbridge/app/ports/input/user_auth_use_case.py`** [v1.1]

```python
from abc import ABC, abstractmethod
from soundbridge.app.dtos.user_auth_dto import (
    RegisterCommand, LoginCommand, AuthResult,
    VerifyEmailCommand, ResetPasswordCommand,
    UserProfileResult, UpdateProfileCommand,
)

class UserAuthUseCase(ABC):

    @abstractmethod
    async def register(self, command: RegisterCommand) -> AuthResult: ...

    @abstractmethod
    async def login(self, command: LoginCommand) -> AuthResult: ...

    @abstractmethod
    async def login_google(self, google_token: str) -> AuthResult: ...

    @abstractmethod
    async def verify_email(self, command: VerifyEmailCommand) -> bool: ...

    @abstractmethod
    async def resend_verification(self, email: str) -> bool: ...

    @abstractmethod
    async def request_password_reset(self, email: str) -> bool: ...

    @abstractmethod
    async def reset_password(self, command: ResetPasswordCommand) -> bool: ...

    @abstractmethod
    async def get_profile(self, user_id: str) -> UserProfileResult: ...

    @abstractmethod
    async def update_profile(self, command: UpdateProfileCommand) -> UserProfileResult: ...

    @abstractmethod
    async def delete_account(self, user_id: str) -> bool: ...
```

### Task 4-3. DTOs

**`soundbridge/app/dtos/track_discover_dto.py`** [MVP]

```python
from dataclasses import dataclass
from uuid import UUID

@dataclass
class DiscoverCommand:
    input_text: str
    lang: str = "ko"

@dataclass
class EmotionAnalysisResult:
    emotions: list[str]
    mood: str
    instrument_hints: list[str]
    embed_text: str

@dataclass
class MatchExplanation:
    track_id: UUID
    score: float
    explanation_ko: str
    explanation_en: str

@dataclass
class TrackResult:
    track_id: UUID
    title: str
    artist: str
    instrument: str
    jangdan: str
    emotion_tags: list[str]
    bpm: int
    loop_unit_beats: int
    cue_points: list[dict]
    audio_url: str
    license_type: str
    license_label_en: str
    description_ko: str
    description_en: str
    score: float | None = None
    explanation: str | None = None

@dataclass
class DiscoverResult:
    tracks: list[TrackResult]
    input_summary: str
```

**`soundbridge/app/dtos/create_preset_dto.py`** [MVP]

```python
# 레이어: Application — DISCOVER→CREATE 프리셋 변환 DTO
from dataclasses import dataclass
from uuid import UUID

@dataclass
class CreatePresetCommand:
    """DISCOVER 매칭 트랙으로부터 CREATE 필터 프리셋 생성 명령"""
    track_id: UUID
    instrument: str
    emotion: str           # emotion_tags[0]
    bpm: int

@dataclass
class CreatePresetResult:
    """CREATE 페이지 URL 쿼리 파라미터"""
    instrument: str
    emotion: str
    bpm_min: int           # max(60, bpm - 20)
    bpm_max: int           # min(200, bpm + 20)
    query_string: str      # "instrument=가야금&emotion=서정&bpm_min=80&bpm_max=110"
    full_url: str          # "/create?instrument=가야금&emotion=서정&..."
```

**`soundbridge/app/dtos/user_auth_dto.py`** [v1.1]

```python
from dataclasses import dataclass
from uuid import UUID

@dataclass
class RegisterCommand:
    name: str
    email: str
    password: str
    marketing_agreed: bool = False
    lang: str = "ko"

@dataclass
class LoginCommand:
    email: str
    password: str

@dataclass
class AuthResult:
    user_id: UUID
    name: str
    email: str
    auth_provider: str
    access_token: str
    is_email_verified: bool

@dataclass
class VerifyEmailCommand:
    token: str

@dataclass
class ResetPasswordCommand:
    token: str
    new_password: str

@dataclass
class UserProfileResult:
    user_id: UUID
    name: str
    email: str
    auth_provider: str
    profile_image_url: str | None
    created_at: str

@dataclass
class UpdateProfileCommand:
    user_id: UUID
    name: str | None = None
```

### Task 4-4. Interactors

**`soundbridge/app/use_cases/track_discover_interactor.py`** [MVP]

```python
# 레이어: Application — DISCOVER 유스케이스 오케스트레이션
import hashlib, json
from soundbridge.app.ports.input.track_discover_use_case import TrackDiscoverUseCase
from soundbridge.app.ports.output.track_repository import TrackRepository
from soundbridge.app.ports.output.gemini_port import GeminiPort
from soundbridge.app.ports.output.embedding_port import EmbeddingPort
from soundbridge.app.dtos.track_discover_dto import DiscoverCommand, DiscoverResult, TrackResult
from soundbridge.infrastructure.exceptions import TrackNotFoundException

class TrackDiscoverInteractor(TrackDiscoverUseCase):

    def __init__(
        self,
        track_repo: TrackRepository,
        claude: GeminiPort,
        embedding: EmbeddingPort,
        redis=None,
    ):
        self._track_repo = track_repo
        self._claude = claude
        self._embedding = embedding
        self._redis = redis

    async def discover(self, command: DiscoverCommand) -> DiscoverResult:
        # 1. 캐시 확인
        cache_key = self._make_cache_key(command)
        if self._redis:
            cached = await self._redis.get(cache_key)
            if cached:
                return DiscoverResult(**json.loads(cached))

        # 2. Gemini 감성 분석
        emotion = await self._claude.analyze_emotion(command.input_text, command.lang)

        # 3. 임베딩 생성 → pgvector 유사도 검색
        query_vec = await self._embedding.embed_text(emotion.embed_text)
        track_ids = await self._embedding.find_similar_tracks(query_vec, top_k=3)

        # 4. 트랙 상세 조회
        tracks = await self._track_repo.find_by_ids(track_ids)

        # 5. Gemini 매칭 설명 생성 (KO + EN 동시)
        explanations = await self._claude.explain_match(
            command.input_text, tracks, command.lang
        )

        # 6. 매칭 로그 저장 (실패해도 무시)
        for track, exp in zip(tracks, explanations):
            try:
                await self._track_repo.save_match_log(
                    command.input_text, command.lang, track.id, exp.score
                )
            except Exception:
                pass

        # 7. 결과 조립
        result = self._build_result(tracks, explanations, command.input_text)

        # 8. 캐시 저장 (1시간)
        if self._redis:
            await self._redis.setex(cache_key, 3600, json.dumps(result.__dict__))

        return result

    async def get_popular_tracks(self, limit: int = 6) -> list:
        tracks = await self._track_repo.find_popular(limit)
        return [self._to_track_result(t) for t in tracks]

    async def get_track_detail(self, track_id: str) -> DiscoverResult:
        # [v1.2] 트랙 상세 페이지용
        from uuid import UUID
        track = await self._track_repo.find_by_id(UUID(track_id))
        if not track:
            raise TrackNotFoundException(track_id)
        return self._build_result([track], [], "")

    def _make_cache_key(self, command: DiscoverCommand) -> str:
        h = hashlib.md5(f"{command.input_text}:{command.lang}".encode()).hexdigest()
        return f"sb:discover:{h}"

    def _build_result(self, tracks, explanations, input_text) -> DiscoverResult:
        # TODO: 조립 로직 구현
        ...

    def _to_track_result(self, track) -> TrackResult:
        # TODO: Domain → DTO 변환
        ...
```

**`soundbridge/app/use_cases/create_preset_interactor.py`** [MVP]

```python
# 레이어: Application — DISCOVER→CREATE 프리셋 URL 변환 유스케이스
from soundbridge.app.ports.input.create_preset_use_case import CreatePresetUseCase
from soundbridge.app.dtos.create_preset_dto import CreatePresetCommand, CreatePresetResult

class CreatePresetInteractor(CreatePresetUseCase):
    """
    DISCOVER 매칭 결과(악기·감성·BPM)를 CREATE 페이지
    쿼리 파라미터 URL로 변환한다.
    외부 IO 없음 — 순수 도메인 로직.
    """

    BPM_MARGIN = 20
    BPM_MIN_FLOOR = 60
    BPM_MAX_CEIL = 200

    def build_preset_url(self, command: CreatePresetCommand) -> CreatePresetResult:
        bpm_min = max(self.BPM_MIN_FLOOR, command.bpm - self.BPM_MARGIN)
        bpm_max = min(self.BPM_MAX_CEIL, command.bpm + self.BPM_MARGIN)

        params: dict[str, str] = {}
        if command.instrument:
            params["instrument"] = command.instrument
        if command.emotion:
            params["emotion"] = command.emotion
        params["bpm_min"] = str(bpm_min)
        params["bpm_max"] = str(bpm_max)

        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        full_url = f"/create?{query_string}"

        return CreatePresetResult(
            instrument=command.instrument,
            emotion=command.emotion,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            query_string=query_string,
            full_url=full_url,
        )
```

**`soundbridge/app/use_cases/user_auth_interactor.py`** [v1.1]

```python
# 레이어: Application — 인증 유스케이스 오케스트레이션
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import bcrypt, jwt

from soundbridge.app.ports.input.user_auth_use_case import UserAuthUseCase
from soundbridge.app.ports.output.user_repository import UserRepository
from soundbridge.app.ports.output.email_port import EmailPort
from soundbridge.app.dtos.user_auth_dto import *
from soundbridge.domain.entities.user_entity import User
from soundbridge.domain.value_objects.auth_provider_vo import AuthProvider
from soundbridge.infrastructure.settings import settings
from soundbridge.infrastructure.exceptions import (
    UserAlreadyExistsException, InvalidCredentialsException,
    EmailNotVerifiedException, TokenExpiredException, TokenInvalidException,
)

class UserAuthInteractor(UserAuthUseCase):

    def __init__(self, user_repo: UserRepository, email_port: EmailPort):
        self._user_repo = user_repo
        self._email_port = email_port

    async def register(self, command: RegisterCommand) -> AuthResult:
        existing = await self._user_repo.find_by_email(command.email)
        if existing:
            raise UserAlreadyExistsException(command.email)

        hashed = bcrypt.hashpw(command.password.encode(), bcrypt.gensalt()).decode()
        user = User(
            id=uuid4(), name=command.name, email=command.email,
            auth_provider=AuthProvider.EMAIL, hashed_password=hashed,
            is_email_verified=False, created_at=datetime.now(timezone.utc),
        )
        await self._user_repo.save(user)

        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(
            hours=settings.email_verify_token_expire_hours
        )
        await self._user_repo.save_email_verification_token(user.id, token, expires)
        await self._email_port.send_verification_email(user.email, user.name, token, command.lang)

        return AuthResult(
            user_id=user.id, name=user.name, email=user.email,
            auth_provider=AuthProvider.EMAIL,
            access_token=self._create_token(str(user.id)),
            is_email_verified=False,
        )

    async def login(self, command: LoginCommand) -> AuthResult:
        user = await self._user_repo.find_by_email(command.email)
        if not user or not user.hashed_password:
            raise InvalidCredentialsException()
        if not bcrypt.checkpw(command.password.encode(), user.hashed_password.encode()):
            raise InvalidCredentialsException()
        if not user.is_email_verified:
            raise EmailNotVerifiedException()

        return AuthResult(
            user_id=user.id, name=user.name, email=user.email,
            auth_provider=user.auth_provider,
            access_token=self._create_token(str(user.id)),
            is_email_verified=True,
        )

    async def verify_email(self, command: VerifyEmailCommand) -> bool:
        record = await self._user_repo.find_email_verification_token(command.token)
        if not record:
            raise TokenInvalidException()
        if record["expires_at"] < datetime.now(timezone.utc):
            raise TokenExpiredException()
        await self._user_repo.activate_user(record["user_id"])
        await self._user_repo.mark_token_used(command.token)
        return True

    def _create_token(self, user_id: str) -> str:
        payload = {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(
                minutes=settings.access_token_expire_minutes
            ),
        }
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")

    # TODO [v1.1]: login_google, resend_verification, request_password_reset,
    #              reset_password, get_profile, update_profile, delete_account
```

---

## 5. Inbound Adapter

### Task 5-1. soundbridge_router 집계 [MVP]

**`soundbridge/adapter/inbound/api/__init__.py`**

```python
# 레이어: Inbound — 라우터 집계
from fastapi import APIRouter
from soundbridge.adapter.inbound.api.v1 import (
    track_discover_router,
    sample_create_router,
    # [v1.1] user_auth_router, cue_extractor_router,
    #        playlist_saved_router, event_kopis_router,
)

soundbridge_router = APIRouter()

soundbridge_router.include_router(
    track_discover_router.router,
    prefix="/soundbridge/discover",
    tags=["DISCOVER"],
)
soundbridge_router.include_router(
    sample_create_router.router,
    prefix="/soundbridge/create",
    tags=["CREATE"],
)
# [v1.1] auth, cue, saved, events 라우터 추가
```

### Task 5-2. Schemas

**`soundbridge/adapter/inbound/api/schemas/track_discover_schema.py`** [MVP]

```python
from pydantic import BaseModel, Field
from uuid import UUID

class DiscoverRequestSchema(BaseModel):
    input: str = Field(..., min_length=1, max_length=200)
    lang: str = Field(default="ko", pattern="^(ko|en)$")

class CuePointSchema(BaseModel):
    time_sec: float
    label: str
    emotion: str

class TrackResponseSchema(BaseModel):
    id: UUID
    title: str
    artist: str
    instrument: str
    jangdan: str
    emotion_tags: list[str]
    bpm: int
    loop_unit_beats: int
    cue_points: list[CuePointSchema]
    audio_url: str
    license_type: str
    license_label_en: str
    description_ko: str
    description_en: str
    score: float | None = None
    explanation: str | None = None

    # [MVP] DISCOVER→CREATE 프리셋 URL 포함
    preset_url: str | None = None

class DiscoverResponseSchema(BaseModel):
    tracks: list[TrackResponseSchema]
    input_summary: str

class SampleFilterSchema(BaseModel):
    instruments: list[str] | None = None
    jangdans: list[str] | None = None
    emotions: list[str] | None = None
    bpm_min: int | None = Field(None, ge=40, le=300)
    bpm_max: int | None = Field(None, ge=40, le=300)
    loop_unit: int | None = None
    license: str | None = None
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)
```

**`soundbridge/adapter/inbound/api/schemas/create_preset_schema.py`** [MVP]

```python
# 레이어: Inbound — CREATE 프리셋 URL 스키마
from pydantic import BaseModel

class CreatePresetResponseSchema(BaseModel):
    """TrackResponseSchema 내 preset_url 필드로도 제공되지만,
    단독 엔드포인트 없음 — DISCOVER 응답에 포함해 반환."""
    instrument: str
    emotion: str
    bpm_min: int
    bpm_max: int
    full_url: str   # "/create?instrument=가야금&emotion=서정&bpm_min=80&bpm_max=110"
```

**`soundbridge/adapter/inbound/api/schemas/user_auth_schema.py`** [v1.1]

```python
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID

class RegisterRequestSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    marketing_agreed: bool = False
    lang: str = Field(default="ko", pattern="^(ko|en)$")

class LoginRequestSchema(BaseModel):
    email: EmailStr
    password: str

class GoogleLoginRequestSchema(BaseModel):
    google_token: str

class AuthResponseSchema(BaseModel):
    user_id: UUID
    name: str
    email: str
    auth_provider: str
    access_token: str
    is_email_verified: bool

class VerifyEmailRequestSchema(BaseModel):
    token: str

class ResendVerificationRequestSchema(BaseModel):
    email: EmailStr

class ForgotPasswordRequestSchema(BaseModel):
    email: EmailStr

class ResetPasswordRequestSchema(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)

class UpdateProfileRequestSchema(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)

class UserProfileResponseSchema(BaseModel):
    user_id: UUID
    name: str
    email: str
    auth_provider: str
    profile_image_url: str | None
    created_at: str
```

### Task 5-3. Routers

**`soundbridge/adapter/inbound/api/v1/track_discover_router.py`** [MVP]

```python
# 레이어: Inbound — DISCOVER HTTP 엔드포인트
from fastapi import APIRouter, Depends, HTTPException
from soundbridge.adapter.inbound.api.schemas.track_discover_schema import (
    DiscoverRequestSchema, DiscoverResponseSchema, TrackResponseSchema,
)
from soundbridge.app.ports.input.track_discover_use_case import TrackDiscoverUseCase
from soundbridge.app.ports.input.create_preset_use_case import CreatePresetUseCase
from soundbridge.app.dtos.create_preset_dto import CreatePresetCommand
from soundbridge.dependencies.track_discover_provider import get_track_discover_use_case
from soundbridge.dependencies.sample_create_provider import get_create_preset_use_case
from soundbridge.infrastructure.exceptions import TrackNotFoundException, GeminiApiException

router = APIRouter()

@router.post("", response_model=DiscoverResponseSchema)
async def discover_gugak(
    body: DiscoverRequestSchema,
    use_case: TrackDiscoverUseCase = Depends(get_track_discover_use_case),
    preset_use_case: CreatePresetUseCase = Depends(get_create_preset_use_case),
) -> DiscoverResponseSchema:
    try:
        result = await use_case.discover(command=...)
        # 각 트랙에 preset_url 추가 [MVP 핵심]
        for track in result.tracks:
            if track.emotion_tags:
                preset = preset_use_case.build_preset_url(
                    CreatePresetCommand(
                        track_id=track.track_id,
                        instrument=track.instrument,
                        emotion=track.emotion_tags[0],
                        bpm=track.bpm,
                    )
                )
                track.preset_url = preset.full_url
        return DiscoverResponseSchema(...)
    except GeminiApiException:
        raise HTTPException(status_code=503, detail="AI 서비스 일시 오류")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/popular", response_model=list[TrackResponseSchema])
async def get_popular_tracks(
    limit: int = 6,
    use_case: TrackDiscoverUseCase = Depends(get_track_discover_use_case),
):
    return await use_case.get_popular_tracks(limit)

@router.get("/{track_id}", response_model=DiscoverResponseSchema)
async def get_track_detail(
    track_id: str,
    use_case: TrackDiscoverUseCase = Depends(get_track_discover_use_case),
):
    # [v1.2] 트랙 상세 페이지용
    try:
        return await use_case.get_track_detail(track_id)
    except TrackNotFoundException:
        raise HTTPException(status_code=404, detail="트랙을 찾을 수 없습니다")
```

**`soundbridge/adapter/inbound/api/v1/user_auth_router.py`** [v1.1]

```python
# 레이어: Inbound — AUTH HTTP 엔드포인트
from fastapi import APIRouter, Depends, HTTPException, status
from soundbridge.adapter.inbound.api.schemas.user_auth_schema import *
from soundbridge.app.ports.input.user_auth_use_case import UserAuthUseCase
from soundbridge.dependencies.user_auth_provider import (
    get_user_auth_use_case, get_current_user_id
)
from soundbridge.infrastructure.exceptions import (
    UserAlreadyExistsException, InvalidCredentialsException,
    EmailNotVerifiedException, TokenExpiredException, TokenInvalidException,
)

router = APIRouter()

@router.post("/register", response_model=AuthResponseSchema, status_code=201)
async def register(body: RegisterRequestSchema, use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    try:
        result = await use_case.register(...)
        return AuthResponseSchema(...)
    except UserAlreadyExistsException:
        raise HTTPException(status_code=409, detail="이미 사용 중인 이메일입니다")

@router.post("/login", response_model=AuthResponseSchema)
async def login(body: LoginRequestSchema, use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    try:
        result = await use_case.login(...)
        return AuthResponseSchema(...)
    except InvalidCredentialsException:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다")
    except EmailNotVerifiedException:
        raise HTTPException(status_code=403, detail="이메일 인증이 필요합니다",
                            headers={"X-Error-Code": "EMAIL_NOT_VERIFIED"})

@router.post("/login/google", response_model=AuthResponseSchema)
async def login_google(body: GoogleLoginRequestSchema, use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    result = await use_case.login_google(body.google_token)
    return AuthResponseSchema(...)

@router.post("/verify-email")
async def verify_email(body: VerifyEmailRequestSchema, use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    try:
        await use_case.verify_email(...)
        return {"message": "이메일 인증이 완료되었습니다"}
    except TokenExpiredException:
        raise HTTPException(status_code=410, detail="인증 링크가 만료되었습니다")
    except TokenInvalidException:
        raise HTTPException(status_code=400, detail="유효하지 않은 인증 링크입니다")

@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationRequestSchema, use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    await use_case.resend_verification(body.email)
    return {"message": "인증 메일을 다시 보냈습니다"}

@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequestSchema, use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    await use_case.request_password_reset(body.email)
    return {"message": "재설정 링크를 보냈습니다"}  # 이메일 존재 여부 노출 금지

@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequestSchema, use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    try:
        await use_case.reset_password(...)
        return {"message": "비밀번호가 변경되었습니다"}
    except (TokenExpiredException, TokenInvalidException) as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me", response_model=UserProfileResponseSchema)
async def get_profile(
    user_id: str = Depends(get_current_user_id),
    use_case: UserAuthUseCase = Depends(get_user_auth_use_case),
):
    result = await use_case.get_profile(user_id)
    return UserProfileResponseSchema(...)

@router.patch("/me", response_model=UserProfileResponseSchema)
async def update_profile(body: UpdateProfileRequestSchema,
    user_id: str = Depends(get_current_user_id),
    use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    result = await use_case.update_profile(...)
    return UserProfileResponseSchema(...)

@router.delete("/me", status_code=204)
async def delete_account(user_id: str = Depends(get_current_user_id),
    use_case: UserAuthUseCase = Depends(get_user_auth_use_case)):
    await use_case.delete_account(user_id)
```

---

## 6. Outbound Adapter

### Task 6-1. ORM 모델

**`soundbridge/adapter/outbound/orm/jangdan_orm.py`** [MVP] ← v4.0 신규

```python
# 레이어: Outbound ORM — jangdan 마스터 테이블 (3NF 분리, loop_unit_beats 정규화)
# 프랙탈 네이밍: jangdan_orm.py — jangdan 테이블 전담
from sqlalchemy import Column, String, Integer
from sqlalchemy.orm import relationship
from soundbridge.adapter.outbound.orm.base_orm import Base

class JangdanOrm(Base):
    __tablename__ = "jangdan"

    name            = Column(String(50), primary_key=True)
    loop_unit_beats = Column(Integer, nullable=False)

    # gugak_tracks 와의 역방향 관계
    tracks = relationship("GugakTrackOrm", back_populates="jangdan_rel")
```

**`soundbridge/adapter/outbound/orm/track_emotion_tag_orm.py`** [MVP] ← v4.0 신규

```python
# 레이어: Outbound ORM — track_emotion_tags 테이블 (1NF 분리, emotion_tags ARRAY 대체)
# 프랙탈 네이밍: track_emotion_tag_orm.py — track_emotion_tags 테이블 전담
import uuid
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from soundbridge.adapter.outbound.orm.base_orm import Base

class TrackEmotionTagOrm(Base):
    __tablename__ = "track_emotion_tags"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id    = Column(
        UUID(as_uuid=True),
        ForeignKey("gugak_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    emotion_tag = Column(String(20), nullable=False)
    sort_order  = Column(Integer, nullable=False, default=0)

    # gugak_tracks 와의 관계
    track = relationship("GugakTrackOrm", back_populates="emotion_tag_rows")
```

**`soundbridge/adapter/outbound/orm/track_orm.py`** [MVP] ← v4.0 변경

```python
# 레이어: Outbound ORM — gugak_tracks 테이블
# [v4.0 변경]
#   - emotion_tags ARRAY 컬럼 제거 (1NF 위반) → track_emotion_tags 테이블로 분리
#   - loop_unit_beats Integer 컬럼 제거 (3NF 위반) → jangdan FK로 참조
#   - jangdan String → jangdan_name FK(String)로 변경
#   - relationship 2개 추가 (jangdan_rel, emotion_tag_rows)
import uuid
from sqlalchemy import Column, String, Integer, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from soundbridge.adapter.outbound.orm.base_orm import Base

class GugakTrackOrm(Base):
    __tablename__ = "gugak_tracks"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title               = Column(String(200), nullable=False)
    artist              = Column(String(100), nullable=False)
    instrument          = Column(String(50), nullable=False)

    # [v4.0 변경] 단순 String → FK (3NF: id→jangdan→loop_unit_beats 이행종속 제거)
    jangdan_name        = Column(String(50), ForeignKey("jangdan.name"), nullable=False)

    # [v4.0 제거] emotion_tags = Column(ARRAY(Text)) ← 1NF 위반이었음
    # [v4.0 제거] loop_unit_beats = Column(Integer)  ← 3NF 위반이었음

    bpm                 = Column(Integer, nullable=False)
    # cue_points: 의도적 비정규화 — WaveSurfer.js 전달 전용, 단독 쿼리 없음
    cue_points          = Column(JSONB, nullable=False, default=[])
    audio_url           = Column(Text, nullable=False)
    public_license_type = Column(String(20), nullable=False)
    description_ko      = Column(Text, nullable=False, default="")
    description_en      = Column(Text, nullable=False, default="")
    embedding           = Column(Vector(1536), nullable=True)   # pgvector 1536차원
    created_at          = Column(TIMESTAMP(timezone=True), nullable=False)

    # [v4.0 신규] relationships
    jangdan_rel      = relationship("JangdanOrm", back_populates="tracks")
    emotion_tag_rows = relationship(
        "TrackEmotionTagOrm",
        back_populates="track",
        order_by="TrackEmotionTagOrm.sort_order",
        cascade="all, delete-orphan",
    )
```

**`soundbridge/adapter/outbound/orm/match_log_orm.py`** [MVP] ← v4.0 변경

```python
# 레이어: Outbound ORM — match_logs 테이블
# [v4.0 변경] similarity_score: String(20) → Float (타입 불일치 수정)
import uuid
from sqlalchemy import Column, Text, String, Float, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from soundbridge.adapter.outbound.orm.base_orm import Base

class MatchLogOrm(Base):
    __tablename__ = "match_logs"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_text       = Column(Text, nullable=False)
    lang             = Column(String(5), nullable=False)
    matched_track_id = Column(UUID(as_uuid=True), ForeignKey("gugak_tracks.id"), nullable=False)
    # [v4.0 변경] String(20) → Float
    similarity_score = Column(Float, nullable=False)
    created_at       = Column(TIMESTAMP(timezone=True), nullable=False)
```

**`soundbridge/adapter/outbound/orm/user_orm.py`** [v1.1]

```python
from sqlalchemy import Column, String, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from soundbridge.adapter.outbound.orm.base_orm import Base
import uuid

class UserOrm(Base):
    __tablename__ = "users"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name              = Column(String(100), nullable=False)
    email             = Column(String(255), unique=True, nullable=False, index=True)
    auth_provider     = Column(String(20), nullable=False)
    hashed_password   = Column(String(255), nullable=True)
    is_email_verified = Column(Boolean, nullable=False, default=False)
    profile_image_url = Column(String(500), nullable=True)
    created_at        = Column(TIMESTAMP(timezone=True), nullable=False)

class EmailVerificationOrm(Base):
    __tablename__ = "email_verifications"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), nullable=False, index=True)
    token      = Column(String(100), unique=True, nullable=False, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    used_at    = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

class SavedTrackOrm(Base):
    __tablename__ = "saved_tracks"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), nullable=False, index=True)
    track_id   = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

class DownloadLogOrm(Base):
    __tablename__ = "download_logs"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), nullable=False, index=True)
    track_id   = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
```

### Task 6-2. ORM Mapper [MVP] ← v4.0 변경

**`soundbridge/adapter/outbound/mappers/track_orm_mapper.py`**

```python
# 레이어: Outbound Mapper — GugakTrackOrm → GugakTrack 도메인 엔티티 변환
# [v4.0 변경]
#   - emotion_tags: orm.emotion_tag_rows(relationship, sort_order 순) → EmotionTag 리스트
#   - loop_unit_beats: jangdan_rel.loop_unit_beats 참조 → GugakTrack.loop_unit_beats property로 자동 계산
#   - joinedload 전략은 Repository에서 결정 — 매퍼는 이미 로드된 컬렉션을 변환만 함
from soundbridge.adapter.outbound.orm.track_orm import GugakTrackOrm
from soundbridge.domain.entities.track_entity import GugakTrack, CuePoint
from soundbridge.domain.value_objects.emotion_vo import EmotionTag
from soundbridge.domain.value_objects.jangdan_vo import Jangdan, JangdanType
from soundbridge.domain.value_objects.instrument_vo import Instrument
from soundbridge.domain.value_objects.license_vo import PublicLicense

class TrackOrmMapper:

    def to_entity(self, orm: GugakTrackOrm) -> GugakTrack:
        # [v4.0 변경] emotion_tags: relationship에서 sort_order 순으로 조립
        emotion_tags = [
            EmotionTag(row.emotion_tag)
            for row in orm.emotion_tag_rows   # sort_order ASC 보장 (relationship order_by)
        ]

        # [v4.0 변경] jangdan_name FK → Jangdan VO 생성
        # loop_unit_beats는 GugakTrack.loop_unit_beats property가 JANGDAN_LOOP_UNITS에서 자동 계산
        jangdan = Jangdan(type=JangdanType(orm.jangdan_name))

        cue_points = [
            CuePoint(
                time_sec=cp["time_sec"],
                label=cp["label"],
                emotion=cp.get("emotion", ""),
            )
            for cp in (orm.cue_points or [])
        ]

        return GugakTrack(
            id=orm.id,
            title=orm.title,
            artist=orm.artist,
            instrument=Instrument(orm.instrument),
            jangdan=jangdan,
            emotion_tags=emotion_tags,
            bpm=orm.bpm,
            cue_points=cue_points,
            audio_url=orm.audio_url,
            public_license=PublicLicense(orm.public_license_type),
            description_ko=orm.description_ko,
            description_en=orm.description_en,
        )
```

### Task 6-3. PgRepository 구현 [MVP] ← v4.0 변경

**`soundbridge/adapter/outbound/pg/track_discover_pg_repository.py`**

```python
# 레이어: Outbound — TrackRepository + EmbeddingPort 구현
# [v4.0 변경]
#   - 모든 트랙 조회 쿼리에 joinedload(emotion_tag_rows, jangdan_rel) 추가
#   - joinedload 전략은 _track_load_options()에서만 결정 (포트 인터페이스 노출 금지)
#   - emotions 필터: ARRAY 연산자 → TrackEmotionTagOrm JOIN (일반 B-tree 인덱스)
#   - loop_unit 필터: JangdanOrm JOIN
#   - result.unique() 필수 (joinedload 중복 방지)
#   - save_match_log: similarity_score Float으로 직접 저장 (str 변환 제거)
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import joinedload
import google.generativeai as genai

from soundbridge.app.ports.output.track_repository import TrackRepository
from soundbridge.app.ports.output.embedding_port import EmbeddingPort
from soundbridge.adapter.outbound.orm.track_orm import GugakTrackOrm
from soundbridge.adapter.outbound.orm.track_emotion_tag_orm import TrackEmotionTagOrm  # [v4.0]
from soundbridge.adapter.outbound.orm.match_log_orm import MatchLogOrm
from soundbridge.adapter.outbound.mappers.track_orm_mapper import TrackOrmMapper
from soundbridge.domain.entities.track_entity import GugakTrack
from soundbridge.infrastructure.settings import settings


def _track_load_options() -> list:
    """
    공통 joinedload 옵션.
    joinedload 전략은 Repository 내부에서만 결정한다 (포트 인터페이스 노출 금지).
    """
    return [
        joinedload(GugakTrackOrm.emotion_tag_rows),  # [v4.0] track_emotion_tags JOIN
        joinedload(GugakTrackOrm.jangdan_rel),       # [v4.0] jangdan JOIN
    ]


class TrackDiscoverPgRepository(TrackRepository, EmbeddingPort):

    def __init__(self, session: AsyncSession):
        self._session = session
        genai.configure(api_key=settings.gemini_api_key)
        self._mapper = TrackOrmMapper()

    async def find_by_id(self, track_id: uuid.UUID) -> GugakTrack | None:
        result = await self._session.execute(
            select(GugakTrackOrm)
            .options(*_track_load_options())
            .where(GugakTrackOrm.id == track_id)
        )
        row = result.unique().scalar_one_or_none()
        return self._mapper.to_entity(row) if row else None

    async def find_by_ids(self, track_ids: list[uuid.UUID]) -> list[GugakTrack]:
        result = await self._session.execute(
            select(GugakTrackOrm)
            .options(*_track_load_options())
            .where(GugakTrackOrm.id.in_(track_ids))
        )
        rows = result.unique().scalars().all()
        id_order = {tid: i for i, tid in enumerate(track_ids)}
        return sorted(
            [self._mapper.to_entity(r) for r in rows],
            key=lambda t: id_order.get(t.id, 999)
        )

    async def find_popular(self, limit: int = 6) -> list[GugakTrack]:
        result = await self._session.execute(
            select(GugakTrackOrm)
            .options(*_track_load_options())
            .limit(limit)
        )
        return [self._mapper.to_entity(r) for r in result.unique().scalars().all()]

    async def find_with_filters(
        self,
        instruments: list[str] | None,
        jangdans: list[str] | None,
        emotions: list[str] | None,
        bpm_min: int | None,
        bpm_max: int | None,
        loop_unit: int | None,
        license_type: str | None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[GugakTrack], int]:
        query = select(GugakTrackOrm).options(*_track_load_options())

        if instruments:
            query = query.where(GugakTrackOrm.instrument.in_(instruments))
        if jangdans:
            query = query.where(GugakTrackOrm.jangdan_name.in_(jangdans))
        if bpm_min is not None:
            query = query.where(GugakTrackOrm.bpm >= bpm_min)
        if bpm_max is not None:
            query = query.where(GugakTrackOrm.bpm <= bpm_max)
        if license_type:
            query = query.where(GugakTrackOrm.public_license_type == license_type)

        # [v4.0 변경] emotions 필터: ARRAY 연산자 → JOIN (일반 B-tree 인덱스 사용)
        if emotions:
            query = (
                query
                .join(TrackEmotionTagOrm,
                      TrackEmotionTagOrm.track_id == GugakTrackOrm.id)
                .where(TrackEmotionTagOrm.emotion_tag.in_(emotions))
                .distinct()
            )

        # [v4.0 변경] loop_unit 필터: jangdan.loop_unit_beats JOIN
        if loop_unit is not None:
            from soundbridge.adapter.outbound.orm.jangdan_orm import JangdanOrm
            query = (
                query
                .join(JangdanOrm, JangdanOrm.name == GugakTrackOrm.jangdan_name)
                .where(JangdanOrm.loop_unit_beats == loop_unit)
            )

        total_result = await self._session.execute(
            select(GugakTrackOrm.id).select_from(query.subquery())
        )
        total = len(total_result.all())

        query = query.limit(limit).offset(offset)
        result = await self._session.execute(query)
        rows = result.unique().scalars().all()
        return [self._mapper.to_entity(r) for r in rows], total

    async def save_match_log(
        self,
        input_text: str,
        lang: str,
        matched_track_id: uuid.UUID,
        similarity_score: float,
    ) -> None:
        log = MatchLogOrm(
            input_text=input_text,
            lang=lang,
            matched_track_id=matched_track_id,
            similarity_score=similarity_score,   # [v4.0] Float 직접 저장
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(log)

    # ── EmbeddingPort 구현 ──────────────────────────────────────
    async def embed_text(self, text: str) -> list[float]:
        """TODO: Gemini 임베딩 API 또는 OpenAI text-embedding-3-small 연동"""
        ...

    async def find_similar_tracks(
        self, query_vector: list[float], top_k: int = 3, filters: dict | None = None
    ) -> list[uuid.UUID]:
        """pgvector 코사인 유사도 검색"""
        result = await self._session.execute(
            text("""
                SELECT id FROM gugak_tracks
                ORDER BY embedding <=> :vec
                LIMIT :k
            """),
            {"vec": str(query_vector), "k": top_k}
        )
        return [row[0] for row in result.fetchall()]
```

### Task 6-4. Gemini Adapter [MVP]

**`soundbridge/adapter/outbound/external/gemini_adapter.py`**

```python
# 레이어: Outbound — Gemini API GeminiPort 구현
import json
import google.generativeai as genai
from soundbridge.app.ports.output.gemini_port import GeminiPort
from soundbridge.app.dtos.track_discover_dto import EmotionAnalysisResult, MatchExplanation
from soundbridge.infrastructure.settings import settings
from soundbridge.infrastructure.exceptions import GeminiApiException

EMOTION_ANALYSIS_PROMPT = """
당신은 음악 감성 분석 전문가입니다.
사용자가 좋아하는 음악 정보를 분석해 국악 매칭에 필요한 감성 키워드를 추출하세요.

입력: {user_input}

다음 JSON 형식으로만 응답하세요 (마크다운 없이):
{{
  "emotions": ["감성1", "감성2"],
  "mood": "전반적 분위기",
  "instrument_hints": ["악기1"],
  "embed_text": "임베딩 생성용 정제 텍스트 (한국어, 2-3문장)"
}}
"""

MATCH_EXPLANATION_PROMPT = """
사용자가 '{user_input}'을(를) 좋아한다고 했습니다.
아래 국악 트랙이 왜 감성적으로 비슷한지 한국어와 영어로 각각 1-2문장 설명하세요.

트랙: {track_title} ({instrument}, {jangdan})
감성: {emotion_tags}

JSON 형식으로만 응답 (마크다운 없이):
{{"ko": "한국어 설명", "en": "English explanation"}}
"""

class GeminiAdapter(GeminiPort):

    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self._client = genai.GenerativeModel(settings.gemini_model)

    async def analyze_emotion(self, user_input: str, lang: str) -> EmotionAnalysisResult:
        try:
            prompt = EMOTION_ANALYSIS_PROMPT.format(user_input=user_input)
            response = await self._client.generate_content_async(prompt)
            data = json.loads(response.text)
            return EmotionAnalysisResult(
                emotions=data["emotions"],
                mood=data["mood"],
                instrument_hints=data["instrument_hints"],
                embed_text=data["embed_text"],
            )
        except Exception as e:
            raise GeminiApiException(f"감성 분석 실패: {e}")

    async def explain_match(self, user_input: str, tracks: list, lang: str) -> list[MatchExplanation]:
        explanations = []
        for track in tracks:
            try:
                prompt = MATCH_EXPLANATION_PROMPT.format(
                    user_input=user_input,
                    track_title=track.title,
                    instrument=track.instrument.value,
                    jangdan=track.jangdan.type.value,
                    emotion_tags=", ".join(e.value for e in track.emotion_tags),
                )
                response = await self._client.generate_content_async(prompt)
                data = json.loads(response.text)
                explanations.append(MatchExplanation(
                    track_id=track.id, score=0.0,
                    explanation_ko=data["ko"],
                    explanation_en=data["en"],
                ))
            except Exception:
                explanations.append(MatchExplanation(
                    track_id=track.id, score=0.0,
                    explanation_ko="", explanation_en="",
                ))
        return explanations

    async def extract_cue_points(self, audio_features: dict):
        # TODO [v1.1]: 오디오 피처 기반 CUE 마커 자동 추출
        ...
```

### Task 6-5. Email Adapter [v1.1]

**`soundbridge/adapter/outbound/external/email_adapter.py`**

```python
# 레이어: Outbound — Resend 이메일 발송 구현
import httpx
from soundbridge.app.ports.output.email_port import EmailPort
from soundbridge.infrastructure.settings import settings
from soundbridge.infrastructure.exceptions import EmailSendException

VERIFY_EMAIL_TEMPLATE = {
    "ko": {
        "subject": "[SoundBridge] 이메일 인증을 완료해주세요",
        "html": """
            <h2>안녕하세요, {name}님!</h2>
            <p>아래 버튼을 클릭하면 이메일 인증이 완료됩니다.</p>
            <a href="{verify_url}">이메일 인증하기</a>
            <p>링크는 24시간 후 만료됩니다.</p>
        """,
    },
    "en": {
        "subject": "[SoundBridge] Please verify your email",
        "html": """
            <h2>Hi {name}!</h2>
            <p>Click the button below to verify your email.</p>
            <a href="{verify_url}">Verify Email</a>
            <p>This link expires in 24 hours.</p>
        """,
    },
}

class EmailAdapter(EmailPort):

    BASE_URL = "https://api.resend.com"

    def __init__(self):
        self._headers = {
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        }

    async def send_verification_email(self, to_email: str, name: str, token: str, lang: str) -> bool:
        verify_url = f"{settings.frontend_url}/auth/verify?token={token}"
        template = VERIFY_EMAIL_TEMPLATE.get(lang, VERIFY_EMAIL_TEMPLATE["ko"])
        return await self._send(
            to=to_email,
            subject=template["subject"],
            html=template["html"].format(name=name, verify_url=verify_url),
        )

    async def send_password_reset_email(self, to_email: str, name: str, token: str, lang: str) -> bool:
        reset_url = f"{settings.frontend_url}/auth/reset/confirm?token={token}"
        # TODO: 비밀번호 재설정 템플릿 구현
        return await self._send(to=to_email, subject="비밀번호 재설정", html="...")

    async def _send(self, to: str, subject: str, html: str) -> bool:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/emails",
                headers=self._headers,
                json={"from": settings.email_from, "to": [to], "subject": subject, "html": html},
            )
            if response.status_code not in (200, 201):
                raise EmailSendException(f"Resend API error: {response.text}")
            return True
```

---

## 7. Dependencies (Composition Root)

### Task 7-1. Provider 패턴 [MVP]

**`soundbridge/dependencies/track_discover_provider.py`**

```python
# 레이어: Dependencies — 유일한 DI 조립 지점
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from soundbridge.infrastructure.database import get_db
from soundbridge.infrastructure.redis_client import redis_client
from soundbridge.adapter.outbound.pg.track_discover_pg_repository import TrackDiscoverPgRepository
from soundbridge.adapter.outbound.external.gemini_adapter import GeminiAdapter
from soundbridge.app.use_cases.track_discover_interactor import TrackDiscoverInteractor
from soundbridge.app.use_cases.create_preset_interactor import CreatePresetInteractor
from soundbridge.app.ports.input.track_discover_use_case import TrackDiscoverUseCase
from soundbridge.app.ports.input.create_preset_use_case import CreatePresetUseCase

def get_track_discover_use_case(
    db: AsyncSession = Depends(get_db),
) -> TrackDiscoverUseCase:
    repository = TrackDiscoverPgRepository(session=db)
    gemini = GeminiAdapter()
    return TrackDiscoverInteractor(
        track_repo=repository,
        claude=gemini,
        embedding=repository,   # TrackDiscoverPgRepository가 EmbeddingPort도 구현
        redis=redis_client,
    )

def get_create_preset_use_case() -> CreatePresetUseCase:
    # 외부 IO 없음 — 매 요청마다 생성해도 무방
    return CreatePresetInteractor()
```

**`soundbridge/dependencies/user_auth_provider.py`** [v1.1]

```python
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from soundbridge.infrastructure.database import get_db
from soundbridge.infrastructure.settings import settings
from soundbridge.adapter.outbound.pg.user_auth_pg_repository import UserAuthPgRepository
from soundbridge.adapter.outbound.external.email_adapter import EmailAdapter
from soundbridge.app.use_cases.user_auth_interactor import UserAuthInteractor
from soundbridge.app.ports.input.user_auth_use_case import UserAuthUseCase

def get_user_auth_use_case(db: AsyncSession = Depends(get_db)) -> UserAuthUseCase:
    return UserAuthInteractor(
        user_repo=UserAuthPgRepository(session=db),
        email_port=EmailAdapter(),
    )

async def get_current_user_id(authorization: str = Header(...)) -> str:
    """JWT Bearer 토큰 검증 → user_id 반환"""
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
```

---

## 8. main.py 연동 [MVP]

**`main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from soundbridge.adapter.inbound.api import soundbridge_router
from soundbridge.adapter.outbound.pg.db_init import create_soundbridge_tables
from soundbridge.infrastructure.settings import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_soundbridge_tables()
    yield

app = FastAPI(
    title="SoundBridge API",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(soundbridge_router, prefix="/api")
```

---

## 9. DB 마이그레이션 (Alembic)

### Task 9-1. Alembic 초기화 [MVP]

```bash
pip install alembic
alembic init alembic
```

**`alembic/env.py`** 핵심 설정 ← v4.0 변경

```python
from soundbridge.infrastructure.settings import settings
from soundbridge.adapter.outbound.orm.base_orm import Base
# [MVP] ORM import — FK 참조 순서 중요
from soundbridge.adapter.outbound.orm import jangdan_orm           # [v4.0 신규]
from soundbridge.adapter.outbound.orm import track_orm
from soundbridge.adapter.outbound.orm import track_emotion_tag_orm # [v4.0 신규]
from soundbridge.adapter.outbound.orm import match_log_orm
# [v1.1] user_orm, saved_track_orm, download_log_orm, email_verification_orm

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

### Task 9-2. 마이그레이션 명령어

```bash
# 최초 마이그레이션 생성
alembic revision --autogenerate -m "init soundbridge tables"

# NeonDB main 브랜치에 적용
alembic upgrade head

# 롤백
alembic downgrade -1
```

### Task 9-3. pgvector 초기 마이그레이션 주의 [MVP]

```python
# alembic/versions/xxxx_init.py
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # 이후 테이블 생성 ...
```

### Task 9-4. v4.0 정규화 마이그레이션 [MVP] ← v4.0 신규

기존 데이터가 있는 경우에만 필요. 신규 구축(데이터 없음)이면 `create_all`로 충분하며 이 스크립트 불필요.

```python
# alembic/versions/xxxx_v4_normalize_emotion_tags_and_jangdan.py
"""v4.0 — 1NF/3NF 정규화: track_emotion_tags 분리, jangdan 마스터 분리

Revision ID: v4_normalize
"""
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    # 1. jangdan 마스터 테이블 생성
    op.create_table(
        "jangdan",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("loop_unit_beats", sa.Integer, nullable=False),
    )

    # 2. 장단 마스터 데이터 삽입
    op.execute("""
        INSERT INTO jangdan (name, loop_unit_beats) VALUES
        ('자진모리', 12), ('중모리', 12), ('굿거리', 12),
        ('휘모리', 4), ('세마치', 6), ('엇모리', 10)
    """)

    # 3. gugak_tracks: jangdan_name FK 컬럼 추가
    op.add_column("gugak_tracks",
        sa.Column("jangdan_name", sa.String(50),
                  sa.ForeignKey("jangdan.name"), nullable=True)
    )

    # 4. 기존 jangdan 값으로 jangdan_name 채우기
    op.execute("UPDATE gugak_tracks SET jangdan_name = jangdan")

    # 5. jangdan_name NOT NULL 설정
    op.alter_column("gugak_tracks", "jangdan_name", nullable=False)

    # 6. 기존 jangdan(String), loop_unit_beats 컬럼 제거
    op.drop_column("gugak_tracks", "jangdan")
    op.drop_column("gugak_tracks", "loop_unit_beats")

    # 7. track_emotion_tags 테이블 생성
    op.create_table(
        "track_emotion_tags",
        sa.Column("id", sa.UUID, primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("track_id", sa.UUID,
                  sa.ForeignKey("gugak_tracks.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("emotion_tag", sa.String(20), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, default=0),
    )

    # 8. 기존 emotion_tags 배열 → 행으로 마이그레이션
    op.execute("""
        INSERT INTO track_emotion_tags (id, track_id, emotion_tag, sort_order)
        SELECT
            gen_random_uuid(),
            id,
            tag,
            (ordinality - 1)::int
        FROM gugak_tracks,
             LATERAL unnest(emotion_tags) WITH ORDINALITY AS t(tag, ordinality)
        WHERE emotion_tags IS NOT NULL AND array_length(emotion_tags, 1) > 0
    """)

    # 9. emotion_tags ARRAY 컬럼 제거
    op.drop_column("gugak_tracks", "emotion_tags")

    # 10. match_logs.similarity_score String → Float
    op.alter_column("match_logs", "similarity_score",
                    type_=sa.Float, existing_type=sa.String(20),
                    postgresql_using="similarity_score::float")

    # 11. track_emotion_tags 인덱스
    op.create_index("ix_track_emotion_tags_tag",
                    "track_emotion_tags", ["emotion_tag"])

def downgrade() -> None:
    # 역순 복원
    op.add_column("gugak_tracks",
        sa.Column("emotion_tags", sa.ARRAY(sa.Text), nullable=True))
    op.execute("""
        UPDATE gugak_tracks t SET emotion_tags = (
            SELECT array_agg(emotion_tag ORDER BY sort_order)
            FROM track_emotion_tags WHERE track_id = t.id
        )
    """)
    op.drop_table("track_emotion_tags")
    op.add_column("gugak_tracks",
        sa.Column("jangdan", sa.String(50), nullable=True))
    op.execute("UPDATE gugak_tracks SET jangdan = jangdan_name")
    op.alter_column("gugak_tracks", "jangdan", nullable=False)
    op.add_column("gugak_tracks",
        sa.Column("loop_unit_beats", sa.Integer, nullable=True))
    op.execute("""
        UPDATE gugak_tracks t SET loop_unit_beats = (
            SELECT loop_unit_beats FROM jangdan WHERE name = t.jangdan_name
        )
    """)
    op.alter_column("gugak_tracks", "loop_unit_beats", nullable=False)
    op.drop_column("gugak_tracks", "jangdan_name")
    op.drop_table("jangdan")
    op.alter_column("match_logs", "similarity_score",
                    type_=sa.String(20), existing_type=sa.Float,
                    postgresql_using="similarity_score::text")
```

---

## 10. 패키지 설치

```bash
# 핵심 [MVP]
pip install fastapi uvicorn[standard] python-multipart

# DB [MVP]
pip install sqlalchemy[asyncio] psycopg alembic pgvector

# AI [MVP]
pip install google-generativeai

# 캐시 [MVP]
pip install redis[asyncio]

# 환경변수 [MVP]
pip install pydantic-settings python-dotenv

# 인증 [v1.1]
pip install python-jose[cryptography] bcrypt httpx
```

**`requirements.txt`**

```
# [MVP]
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
sqlalchemy[asyncio]>=2.0.0
psycopg>=3.1.0
alembic>=1.13.0
pgvector>=0.3.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
google-generativeai>=0.8.0
redis[asyncio]>=5.0.0
python-dotenv>=1.0.0

# [v1.1]
python-jose[cryptography]>=3.3.0
bcrypt>=4.1.0
httpx>=0.27.0
```

---

## 11. 환경변수

```bash
# .env

# [MVP]
DATABASE_URL=postgresql+psycopg://user:pwd@ep-xxx.neon.tech/soundbridge?sslmode=require
REDIS_URL=redis://localhost:6379
GEMINI_API_KEY=AIza...
APP_ENV=development
FRONTEND_URL=http://localhost:3000

# [v1.1]
SECRET_KEY=                         # openssl rand -hex 32
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@soundbridge.site

# [v1.1]
KOPIS_API_KEY=
KTO_API_KEY=
```

---

## 12. API 엔드포인트 전체 목록

```
[DISCOVER]  /api/soundbridge/discover                              [MVP]
  POST   /                       감성 매칭 검색 (preset_url 포함)
  GET    /popular                인기 트랙 목록
  GET    /{track_id}             트랙 상세                         [v1.2]

[CREATE]    /api/soundbridge/create                                [MVP]
  GET    /samples                샘플 목록 (필터 쿼리)
  POST   /download-log           다운로드 이력 저장                [v1.1]
  GET    /download-logs          내 다운로드 이력                  [v1.1]

[AUTH]      /api/soundbridge/auth                                  [v1.1]
  POST   /register
  POST   /login
  POST   /login/google
  POST   /verify-email
  POST   /resend-verification
  POST   /forgot-password
  POST   /reset-password
  GET    /me
  PATCH  /me
  DELETE /me

[SAVED]     /api/soundbridge/saved                                 [v1.1]
  GET    /tracks
  POST   /{track_id}
  DELETE /{track_id}

[CUE]       /api/soundbridge/cue                                   [v1.1]
  POST   /extract/{track_id}    CUE 마커 추출 (관리자용)

[EVENTS]    /api/soundbridge/events                                [v1.1]
  GET    /performances           KOPIS 공연 목록
  GET    /places                 관광 체험 장소
```

---

## 13. 구현 순서 (Phase별)

### MVP (공모전 제출)

```
Phase 1 — 기반 (Task 1-1, 2-1 ~ 2-5)
  디렉터리, 환경변수, DB·Redis 연결, 예외, ORM Base, db_init
  [v4.0] jangdan_orm.py, track_emotion_tag_orm.py 신규 생성 포함
  [v4.0] db_init에서 jangdan 시드 데이터 삽입 확인

Phase 2 — Domain + App Core (Task 3-1 ~ 3-2, 4-1 ~ 4-3)
  Value Objects, Track Entity, Ports, DTOs (프레임워크 없이 단위 테스트 가능)

Phase 3 — CREATE 프리셋 유스케이스 (Task 4-3 create_preset_dto, 4-4 create_preset_interactor)
  외부 IO 없음 — 순수 로직. 프론트 연동 전에 단독 테스트 완료

Phase 4 — DISCOVER 핵심 (Task 4-4 track_discover, 5-2~5-3 일부, 6-2~6-3, 7-1)
  TrackDiscoverInteractor, Router (preset_url 포함), PgRepository, GeminiAdapter
  [v4.0] joinedload 포함 쿼리 확인
  → POST /discover + preset_url 포함 응답 확인

Phase 5 — CREATE 샘플 필터 (Task 5-3 sample_create_router, 6-2 sample_create_pg)
  [v4.0] emotions 필터 JOIN 방식, loop_unit 필터 jangdan JOIN 확인
  GET /samples 동작 확인 → 프론트 FilterPanel 연동
```

### v1.1 (공모전 이후)

```
Phase 6 — 인증 (Task 4-4 user_auth, 5-3 user_auth_router, 6-1~6-4, 7-1)
  UserAuthInteractor, Router, UserOrm, EmailAdapter
  → 회원가입 → 이메일 인증 → 로그인 플로우 end-to-end

Phase 7 — SAVED + 다운로드 이력
  SavedTrack, DownloadLog Repository + Router

Phase 8 — 외부 API 연동
  KOPIS, 관광공사, CUE 추출 파이프라인
```

### v1.2 이후

```
Phase 9 — 최적화
  Redis 캐시 전면 적용, pgvector HNSW 인덱스, N+1 쿼리 제거
  임베딩 전수 확장 (16,721건 배치 처리)
```

---

## 14. 체크리스트

### MVP 기준

```
아키텍처
  □ Domain 레이어에 FastAPI·SQLAlchemy import 없음
  □ Router가 PgRepository 직접 import 없음
  □ Interactor가 ORM·HTTPException import 없음
  □ 프랙탈 네이밍 일치 (domain_character_suffix)
  □ 모든 Provider는 dependencies/ 에만 존재
  □ [v4.0] ORM 파일 — 테이블 1개당 파일 1개 원칙 준수
  □ [v4.0] joinedload 전략이 포트 인터페이스 밖으로 노출 없음

코드 품질
  □ Python type hint 100%
  □ async/await 일관 사용
  □ Pydantic v2 스타일

정규화 (v4.0)
  □ gugak_tracks에 emotion_tags ARRAY 컬럼 없음
  □ gugak_tracks에 loop_unit_beats 컬럼 없음
  □ track_emotion_tags 테이블 존재 + sort_order 컬럼
  □ jangdan 마스터 테이블 존재 + 시드 데이터 6건
  □ match_logs.similarity_score Float 타입 확인

ORM / Repository (v4.0)
  □ 모든 트랙 조회 쿼리에 joinedload(emotion_tag_rows) 포함
  □ 모든 트랙 조회 쿼리에 joinedload(jangdan_rel) 포함
  □ result.unique() 호출 (joinedload 중복 방지)
  □ emotions 필터: TrackEmotionTagOrm JOIN (ARRAY 연산자 아님)
  □ loop_unit 필터: JangdanOrm JOIN

DISCOVER→CREATE 연결
  □ DiscoverResult 내 각 트랙에 preset_url 포함 확인
  □ CreatePresetInteractor 단위 테스트 통과
  □ bpm_min/bpm_max 범위 계산 (max(60, bpm-20) / min(200, bpm+20))

DB
  □ NeonDB 연결 문자열 postgresql+psycopg:// 스킴 + sslmode=require 포함
  □ pgvector 익스텐션 활성화 확인
  □ Alembic migration 정상 적용
  □ [v4.0] upgrade / downgrade 양방향 테스트
  □ [v4.0] 기존 emotion_tags 배열 → 행 마이그레이션 검증
  □ pool_pre_ping=True 설정

배포
  □ .env 파일 .gitignore 등록
  □ requirements.txt 최신화
  □ CORS allow_origins 프로덕션 도메인 확인
```

### v1.1 추가 체크리스트

```
인증
  □ 비밀번호 bcrypt 해싱 확인
  □ JWT 만료 처리
  □ 이메일 인증 토큰 만료 처리
  □ Google OAuth 토큰 검증
  □ forgot-password 응답에서 이메일 존재 여부 노출 금지
```
