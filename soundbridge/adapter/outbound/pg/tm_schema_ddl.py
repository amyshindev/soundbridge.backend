# gugak_tracks TM 데이터셋 컬럼 DDL (스크립트·API 공용)

TM_COLUMN_DDLS: tuple[str, ...] = (
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS source_identifier VARCHAR(80)",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS classification_code VARCHAR(20) DEFAULT ''",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS genre_lclsf VARCHAR(50) DEFAULT ''",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS genre_mclsf VARCHAR(50) DEFAULT ''",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS genre_sclsf VARCHAR(50) DEFAULT ''",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS time_signature VARCHAR(20) DEFAULT ''",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS tempo_label VARCHAR(20) DEFAULT ''",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS original_track_code VARCHAR(50) DEFAULT ''",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS jangdan_raw VARCHAR(50) DEFAULT ''",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS whole_emotions JSONB DEFAULT '[]'::jsonb",
    "ALTER TABLE gugak_tracks ADD COLUMN IF NOT EXISTS whole_tones JSONB DEFAULT '[]'::jsonb",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_gugak_tracks_source_identifier
    ON gugak_tracks (source_identifier)
    WHERE source_identifier IS NOT NULL
    """,
)


def apply_tm_schema_sync(conn) -> None:
    """psycopg 동기 연결에 TM 컬럼을 추가합니다."""
    with conn.cursor() as cur:
        for ddl in TM_COLUMN_DDLS:
            cur.execute(ddl)
    conn.commit()
