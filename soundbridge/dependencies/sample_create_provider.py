# 레이어: Dependencies — CREATE DI 조립
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.adapter.outbound.pg.sample_create_pg_repository import SampleCreatePgRepository
from soundbridge.app.ports.input.sample_create_use_case import SampleCreateUseCase
from soundbridge.app.use_cases.sample_create_interactor import SampleCreateInteractor
from soundbridge.infrastructure.database import get_db


def get_sample_create_use_case(
    db: AsyncSession = Depends(get_db),
) -> SampleCreateUseCase:
    repository = SampleCreatePgRepository(session=db)
    return SampleCreateInteractor(sample_repo=repository)
