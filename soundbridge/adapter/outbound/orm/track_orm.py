# 레이어: Outbound ORM — gugak_tracks 테이블
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from soundbridge.adapter.outbound.orm.base_orm import Base
from soundbridge.infrastructure.embedding_config import EMBEDDING_DIMENSION


class GugakTrackOrm(Base):
    __tablename__ = "gugak_tracks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)
    artist = Column(String(100), nullable=False)
    instrument = Column(String(50), nullable=False)
    jangdan_name = Column(String(50), ForeignKey("jangdan.name"), nullable=False)
    bpm = Column(Integer, nullable=False)
    cue_points = Column(JSONB, nullable=False, default=list)
    audio_url = Column(Text, nullable=False)
    public_license_type = Column(String(20), nullable=False)
    description_ko = Column(Text, nullable=False, default="")
    description_en = Column(Text, nullable=False, default="")
    embedding = Column(Vector(EMBEDDING_DIMENSION), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)
    # 국악음원(TM) 학습데이터 메타
    source_identifier = Column(String(80), nullable=True, unique=True)
    classification_code = Column(String(20), nullable=False, default="")
    genre_lclsf = Column(String(50), nullable=False, default="")
    genre_mclsf = Column(String(50), nullable=False, default="")
    genre_sclsf = Column(String(50), nullable=False, default="")
    time_signature = Column(String(20), nullable=False, default="")
    tempo_label = Column(String(20), nullable=False, default="")
    original_track_code = Column(String(50), nullable=False, default="")
    jangdan_raw = Column(String(50), nullable=False, default="")
    whole_emotions = Column(JSONB, nullable=False, default=list)
    whole_tones = Column(JSONB, nullable=False, default=list)

    jangdan_rel = relationship("JangdanOrm", back_populates="tracks")
    emotion_tag_rows = relationship(
        "TrackEmotionTagOrm",
        back_populates="track",
        order_by="TrackEmotionTagOrm.sort_order",
        cascade="all, delete-orphan",
    )
