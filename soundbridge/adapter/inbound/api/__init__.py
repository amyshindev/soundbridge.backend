# 레이어: Inbound — 라우터 집계
from fastapi import APIRouter

from soundbridge.adapter.inbound.api.v1 import sample_create_router, track_discover_router

soundbridge_router = APIRouter()

soundbridge_router.include_router(
    track_discover_router.router,
    prefix="/soundbridge/discover",
    tags=["DISCOVER"],
)
soundbridge_router.include_router(
    sample_create_router.router,
    prefix="/soundbridge/create",
    tags=["CREATE"],
)
