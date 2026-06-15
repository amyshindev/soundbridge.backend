"""SQLAlchemy Base — 모든 ORM 모델의 공통 DeclarativeBase."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """도메인 간 직접 의존 없이 ORM 메타데이터만 공유."""

    pass
