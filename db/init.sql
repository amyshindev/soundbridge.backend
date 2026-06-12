-- pgvector 익스텐션 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 국악 트랙 테이블
CREATE TABLE IF NOT EXISTS gugak_tracks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               VARCHAR(200) NOT NULL,
    artist              VARCHAR(100),
    instrument          VARCHAR(50),
    jangdan             VARCHAR(50),
    emotion_tags        TEXT[],
    bpm                 INTEGER,
    loop_unit_beats     INTEGER,
    cue_points          JSONB DEFAULT '[]',
    audio_url           TEXT,
    public_license_type VARCHAR(20),
    description_ko      TEXT,
    description_en      TEXT,
    created_at          TIMESTAMP DEFAULT NOW()
);

-- 임베딩 테이블
CREATE TABLE IF NOT EXISTS track_embeddings (
    track_id         UUID REFERENCES gugak_tracks(id) ON DELETE CASCADE,
    embedding_vector VECTOR(768),
    created_at       TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (track_id)
);

-- 매칭 로그
CREATE TABLE IF NOT EXISTS match_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    input_text       TEXT,
    matched_track_id UUID REFERENCES gugak_tracks(id),
    similarity_score FLOAT,
    created_at       TIMESTAMP DEFAULT NOW()
);

-- 유사도 검색용 인덱스 (500건이면 ivfflat 충분)
CREATE INDEX IF NOT EXISTS idx_embedding_vector
    ON track_embeddings
    USING ivfflat (embedding_vector vector_cosine_ops)
    WITH (lists = 10);