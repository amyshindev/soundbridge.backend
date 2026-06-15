# 레이어: Outbound — startup 테이블 생성 + 장단 마스터 초기 데이터
from sqlalchemy import text

from soundbridge.adapter.outbound.orm import (  # noqa: F401
    jangdan_orm,
    match_log_orm,
    track_emotion_tag_orm,
    track_orm,
)
from soundbridge.adapter.outbound.orm.base_orm import Base
from soundbridge.adapter.outbound.orm.jangdan_orm import JangdanOrm
from soundbridge.infrastructure.database import AsyncSessionLocal, engine

JANGDAN_SEED = [
    ("자진모리", 12),
    ("중모리", 12),
    ("굿거리", 12),
    ("휘모리", 4),
    ("세마치", 6),
    ("엇모리", 10),
]


async def create_soundbridge_tables() -> None:
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        for name, beats in JANGDAN_SEED:
            exists = await session.get(JangdanOrm, name)
            if not exists:
                session.add(JangdanOrm(name=name, loop_unit_beats=beats))
        await session.commit()
