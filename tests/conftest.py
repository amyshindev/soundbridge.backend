"""pytest 공통 설정 및 피스처."""
from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from soundbridge.app.dtos.track_discover_dto import DiscoverResult, TrackResult
from soundbridge.domain.entities.cue_point_entity import CuePoint
from soundbridge.domain.entities.track_entity import GugakTrack
from soundbridge.domain.value_objects.emotion_vo import EmotionTag
from soundbridge.domain.value_objects.instrument_vo import Instrument
from soundbridge.domain.value_objects.jangdan_vo import Jangdan, JangdanType
from soundbridge.domain.value_objects.license_vo import PublicLicense


@pytest.fixture
def track_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def sample_gugak_track(track_id: uuid.UUID) -> GugakTrack:
    return GugakTrack(
        id=track_id,
        title="회심곡",
        artist="미상",
        instrument=Instrument.VOCAL,
        jangdan=Jangdan(type=JangdanType.JAJINMORI),
        emotion_tags=[EmotionTag.LYRICAL, EmotionTag.CALM],
        bpm=0,
        cue_points=[
            CuePoint(time_sec=0.1, label="A", emotion="감아내기"),
            CuePoint(time_sec=9.9, label="B", emotion="밀어내기"),
            CuePoint(time_sec=19.0, label="C", emotion="굴려내기"),
        ],
        audio_url="KC_TM_ET_BM_S005672.wav",
        public_license=PublicLicense.KOGL_1,
        description_ko="불교 음악 회심곡",
        description_en="Buddhist vocal piece",
    )


@pytest.fixture
def sample_track_result(track_id: uuid.UUID) -> TrackResult:
    return TrackResult(
        track_id=track_id,
        title="회심곡",
        artist="미상",
        instrument="가창",
        jangdan="자진모리",
        emotion_tags=["서정", "차분"],
        bpm=0,
        loop_unit_beats=12,
        cue_points=[
            {"time_sec": 0.1, "label": "A", "emotion": "감아내기"},
        ],
        audio_url="KC_TM_ET_BM_S005672.wav",
        license_type="KOGL_1",
        license_label_en="CC-BY (Commercial OK)",
        description_ko="불교 음악 회심곡",
        description_en="Buddhist vocal piece",
        score=0.92,
        explanation="테스트 설명",
    )


@pytest.fixture
def mock_track_repository(sample_gugak_track: GugakTrack) -> AsyncMock:
    repo = AsyncMock()
    repo.find_by_ids.return_value = [sample_gugak_track]
    repo.find_by_id.return_value = sample_gugak_track
    repo.find_popular.return_value = [sample_gugak_track]
    repo.save_match_log.return_value = None
    return repo


@pytest.fixture
def mock_embedding_port(track_id: uuid.UUID) -> AsyncMock:
    port = AsyncMock()
    port.embed_text.return_value = [0.1] * 768
    port.find_similar_tracks.return_value = [track_id]
    return port


@pytest.fixture
def mock_exaone_port() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def discover_app_client() -> Iterator[Any]:
    """DISCOVER 라우터만 마운트한 테스트용 FastAPI 앱."""
    import importlib.util
    from pathlib import Path

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from soundbridge.app.use_cases.create_preset_interactor import CreatePresetInteractor
    from soundbridge.dependencies.create_preset_provider import get_create_preset_use_case
    from soundbridge.dependencies.track_discover_provider import get_track_discover_use_case

    backend = Path(__file__).resolve().parents[1]
    mod_path = backend / "soundbridge/adapter/inbound/api/v1/track_discover_router.py"
    spec = importlib.util.spec_from_file_location(
        "soundbridge.adapter.inbound.api.v1.track_discover_router",
        mod_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    try:
        spec.loader.exec_module(module)
    except TypeError as exc:
        if "on_startup" in str(exc):
            pytest.skip("FastAPI/Starlette 버전 불일치 — requirements.txt 기준 환경에서 실행하세요.")
        raise

    app = FastAPI()
    app.include_router(module.router, prefix="/discover")

    mock_use_case = AsyncMock()
    app.dependency_overrides[get_track_discover_use_case] = lambda: mock_use_case
    app.dependency_overrides[get_create_preset_use_case] = lambda: CreatePresetInteractor()

    with TestClient(app) as client:
        client.mock_use_case = mock_use_case  # type: ignore[attr-defined]
        yield client

    app.dependency_overrides.clear()
