# 레이어: Outbound ORM — jangdan 마스터 테이블 (3NF 분리)
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from soundbridge.adapter.outbound.orm.base_orm import Base


class JangdanOrm(Base):
    __tablename__ = "jangdan"

    name = Column(String(50), primary_key=True)
    loop_unit_beats = Column(Integer, nullable=False)

    tracks = relationship("GugakTrackOrm", back_populates="jangdan_rel")
