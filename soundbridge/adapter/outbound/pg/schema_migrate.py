# 레이어: Outbound — gugak_tracks TM 데이터셋 컬럼 마이그레이션
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.adapter.outbound.pg.tm_schema_ddl import TM_COLUMN_DDLS


async def migrate_gugak_tracks_tm_columns(session: AsyncSession) -> None:
    for ddl in TM_COLUMN_DDLS:
        await session.execute(text(ddl))
    await session.commit()
