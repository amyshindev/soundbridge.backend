"""adapter/inbound — DISCOVER API 라우터 테스트."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from soundbridge.app.dtos.track_discover_dto import DiscoverResult


def test_discover_post_returns_tracks(discover_app_client, sample_track_result) -> None:
    client = discover_app_client
    client.mock_use_case.discover = AsyncMock(
        return_value=DiscoverResult(
            tracks=[sample_track_result],
            input_summary='"테스트" 와 감성이 닮은 국악',
        )
    )

    response = client.post(
        "/discover",
        json={"input": "서정적인 곡", "lang": "ko", "enrich": False},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["input_summary"]
    assert len(body["tracks"]) == 1
    assert body["tracks"][0]["title"] == "회심곡"
    assert body["tracks"][0].get("preset_url")


def test_get_popular_tracks(discover_app_client, sample_track_result) -> None:
    client = discover_app_client
    client.mock_use_case.get_popular_tracks = AsyncMock(return_value=[sample_track_result])

    response = client.get("/discover/popular?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "회심곡"


def test_get_track_detail_not_found(discover_app_client) -> None:
    from soundbridge.infrastructure.exceptions import TrackNotFoundException

    client = discover_app_client
    client.mock_use_case.get_track_detail = AsyncMock(
        side_effect=TrackNotFoundException(str(uuid.uuid4()))
    )

    response = client.get(f"/discover/{uuid.uuid4()}")

    assert response.status_code == 404
