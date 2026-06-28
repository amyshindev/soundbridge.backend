# 레이어: Outbound — startup 테이블 생성 + 장단 마스터 초기 데이터
from soundbridge.adapter.outbound.orm import (  # noqa: F401
    jangdan_orm,
    match_log_orm,
    track_emotion_tag_orm,
    track_orm,
)
from soundbridge.adapter.outbound.orm.jangdan_orm import JangdanOrm
from soundbridge.adapter.outbound.pg.embed_schema_migrate import (
    ensure_embedding_hnsw_index,
    migrate_embedding_column_dimension,
)
from soundbridge.adapter.outbound.pg.schema_migrate import migrate_gugak_tracks_tm_columns
from soundbridge.infrastructure.config import is_database_configured
from soundbridge.infrastructure import database

JANGDAN_SEED = [
    ("자진모리", 12),
    ("중모리", 12),
    ("굿거리", 12),
    ("휘모리", 4),
    ("세마치", 6),
    ("엇모리", 10),
]


async def create_soundbridge_tables() -> None:
    await database.init_db()
    if not is_database_configured():
        return

    assert database.AsyncSessionLocal is not None
    async with database.AsyncSessionLocal() as session:
        for name, beats in JANGDAN_SEED:
            exists = await session.get(JangdanOrm, name)
            if not exists:
                session.add(JangdanOrm(name=name, loop_unit_beats=beats))
        await session.commit()
        await migrate_gugak_tracks_tm_columns(session)
        await migrate_embedding_column_dimension(session)
        await ensure_embedding_hnsw_index(session)
