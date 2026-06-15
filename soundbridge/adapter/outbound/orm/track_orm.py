# 레이어: Outbound ORM — gugak_tracks 테이블
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Integer, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from soundbridge.adapter.outbound.orm.base_orm import Base


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
    embedding = Column(Vector(1536), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False)

    jangdan_rel = relationship("JangdanOrm", back_populates="tracks")
    emotion_tag_rows = relationship(
        "TrackEmotionTagOrm",
        back_populates="track",
        order_by="TrackEmotionTagOrm.sort_order",
        cascade="all, delete-orphan",
    )
