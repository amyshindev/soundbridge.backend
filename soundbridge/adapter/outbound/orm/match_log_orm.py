# 레이어: Outbound ORM — match_logs 테이블
import uuid
from datetime import datetime

from sqlalchemy import Column, Float, ForeignKey, String, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID

from soundbridge.adapter.outbound.orm.base_orm import Base


class MatchLogOrm(Base):
    __tablename__ = "match_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_text = Column(Text, nullable=False)
    lang = Column(String(5), nullable=False)
    matched_track_id = Column(UUID(as_uuid=True), ForeignKey("gugak_tracks.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
