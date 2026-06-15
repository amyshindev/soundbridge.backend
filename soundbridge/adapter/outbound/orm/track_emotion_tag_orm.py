# 레이어: Outbound ORM — track_emotion_tags 테이블 (1NF 분리)
import uuid

from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from soundbridge.adapter.outbound.orm.base_orm import Base


class TrackEmotionTagOrm(Base):
    __tablename__ = "track_emotion_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    track_id = Column(
        UUID(as_uuid=True),
        ForeignKey("gugak_tracks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    emotion_tag = Column(String(20), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    track = relationship("GugakTrackOrm", back_populates="emotion_tag_rows")
