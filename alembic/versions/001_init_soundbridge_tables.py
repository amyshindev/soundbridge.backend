"""init soundbridge tables

Revision ID: 001_init
Revises:
Create Date: 2026-06-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "jangdan",
        sa.Column("name", sa.String(50), primary_key=True),
        sa.Column("loop_unit_beats", sa.Integer(), nullable=False),
    )
    op.execute("""
        INSERT INTO jangdan (name, loop_unit_beats) VALUES
        ('자진모리', 12), ('중모리', 12), ('굿거리', 12),
        ('휘모리', 4), ('세마치', 6), ('엇모리', 10)
    """)

    op.create_table(
        "gugak_tracks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("artist", sa.String(100), nullable=False),
        sa.Column("instrument", sa.String(50), nullable=False),
        sa.Column("jangdan_name", sa.String(50), sa.ForeignKey("jangdan.name"), nullable=False),
        sa.Column("bpm", sa.Integer(), nullable=False),
        sa.Column("cue_points", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("audio_url", sa.Text(), nullable=False),
        sa.Column("public_license_type", sa.String(20), nullable=False),
        sa.Column("description_ko", sa.Text(), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "track_emotion_tags",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("track_id", sa.UUID(), sa.ForeignKey("gugak_tracks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emotion_tag", sa.String(20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_track_emotion_tags_track_id", "track_emotion_tags", ["track_id"])
    op.create_index("ix_track_emotion_tags_tag", "track_emotion_tags", ["emotion_tag"])

    op.create_table(
        "match_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("lang", sa.String(5), nullable=False),
        sa.Column("matched_track_id", sa.UUID(), sa.ForeignKey("gugak_tracks.id"), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("match_logs")
    op.drop_index("ix_track_emotion_tags_tag", table_name="track_emotion_tags")
    op.drop_index("ix_track_emotion_tags_track_id", table_name="track_emotion_tags")
    op.drop_table("track_emotion_tags")
    op.drop_table("gugak_tracks")
    op.drop_table("jangdan")
