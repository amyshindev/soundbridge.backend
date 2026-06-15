# 레이어: Domain — MatchLog 엔티티
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class MatchLog:
    id: UUID
    input_text: str
    lang: str
    matched_track_id: UUID
    similarity_score: float
    created_at: datetime
