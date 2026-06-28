# 레이어: Outbound — embedding 컬럼 차원·HNSW 인덱스 마이그레이션
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.infrastructure.embedding_config import EMBEDDING_DIMENSION, EMBEDDING_HNSW_INDEX
from soundbridge.infrastructure.settings import settings

HNSW_INDEX_DDL = f"""
CREATE INDEX IF NOT EXISTS {EMBEDDING_HNSW_INDEX}
ON gugak_tracks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64)
WHERE embedding IS NOT NULL AND source_identifier IS NOT NULL
"""


async def migrate_embedding_column_dimension(session: AsyncSession) -> None:
    dim = settings.embedding_dimension
    result = await session.execute(
        text("""
            SELECT format_type(a.atttypid, a.atttypmod) AS coltype
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            WHERE c.relname = 'gugak_tracks'
              AND a.attname = 'embedding'
              AND NOT a.attisdropped
        """)
    )
    row = result.fetchone()
    if not row:
        return

    expected = f"vector({dim})"
    if row[0] == expected:
        return

    await session.execute(
        text("UPDATE gugak_tracks SET embedding = NULL WHERE embedding IS NOT NULL")
    )
    await session.execute(
        text(f"ALTER TABLE gugak_tracks ALTER COLUMN embedding TYPE vector({dim})")
    )
    await session.commit()


async def ensure_embedding_hnsw_index(session: AsyncSession) -> None:
    """DISCOVER 유사도 검색용 HNSW 인덱스 (cosine)."""
    exists = await session.execute(
        text("""
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = :name
        """),
        {"name": EMBEDDING_HNSW_INDEX},
    )
    if exists.fetchone():
        return

    await session.execute(text(HNSW_INDEX_DDL))
    await session.commit()


def ensure_embedding_hnsw_index_sync(conn) -> None:
    """스크립트용 동기 HNSW 인덱스 생성."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public' AND indexname = %s
            """,
            (EMBEDDING_HNSW_INDEX,),
        )
        if cur.fetchone():
            return
        cur.execute(HNSW_INDEX_DDL)
    conn.commit()
    print(f"[schema] HNSW index ready: {EMBEDDING_HNSW_INDEX}")


def ensure_embedding_column_dimension_sync(conn) -> None:
    """스크립트용 embedding 컬럼 차원 마이그레이션."""
    dim = settings.embedding_dimension
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT format_type(a.atttypid, a.atttypmod) AS coltype
            FROM pg_attribute a
            JOIN pg_class c ON a.attrelid = c.oid
            WHERE c.relname = 'gugak_tracks'
              AND a.attname = 'embedding'
              AND NOT a.attisdropped
            """
        )
        row = cur.fetchone()
        if not row:
            return
        expected = f"vector({dim})"
        if row[0] == expected:
            return
        cur.execute("UPDATE gugak_tracks SET embedding = NULL WHERE embedding IS NOT NULL")
        cur.execute(
            f"ALTER TABLE gugak_tracks ALTER COLUMN embedding TYPE vector({dim})"
        )
    conn.commit()
    print(f"[schema] embedding column migrated to vector({dim})")
