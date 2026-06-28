"""add HNSW index on gugak_tracks.embedding

Revision ID: 002_hnsw
Revises: 001_init
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002_hnsw"
down_revision: Union[str, None] = "001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_gugak_tracks_embedding_hnsw
        ON gugak_tracks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE embedding IS NOT NULL AND source_identifier IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_gugak_tracks_embedding_hnsw")
