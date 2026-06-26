"""app 레이어 — TrackDiscoverInteractor 유스케이스 테스트."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from soundbridge.app.dtos.track_discover_dto import DiscoverCommand
from soundbridge.app.use_cases.track_discover_interactor import TrackDiscoverInteractor
from soundbridge.domain.entities.track_entity import GugakTrack
from soundbridge.infrastructure.exceptions import TrackNotFoundException


@pytest.mark.asyncio
async def test_discover_returns_matched_tracks(
    mock_track_repository: AsyncMock,
    mock_embedding_port: AsyncMock,
    mock_gemini_port: AsyncMock,
    sample_gugak_track: GugakTrack,
) -> None:
    interactor = TrackDiscoverInteractor(
        track_repo=mock_track_repository,
        gemini=mock_gemini_port,
        embedding=mock_embedding_port,
        redis=None,
    )

    result = await interactor.discover(
        DiscoverCommand(input_text="서정적인 느낌", lang="ko", enrich=False)
    )

    assert len(result.tracks) == 1
    assert result.tracks[0].title == sample_gugak_track.title
    assert "서정적인 느낌" in result.input_summary
    mock_embedding_port.embed_text.assert_awaited_once()
    mock_embedding_port.find_similar_tracks.assert_awaited_once()
    mock_track_repository.find_by_ids.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_popular_tracks(
    mock_track_repository: AsyncMock,
    mock_embedding_port: AsyncMock,
    mock_gemini_port: AsyncMock,
    sample_gugak_track: GugakTrack,
) -> None:
    interactor = TrackDiscoverInteractor(
        track_repo=mock_track_repository,
        gemini=mock_gemini_port,
        embedding=mock_embedding_port,
    )

    tracks = await interactor.get_popular_tracks(limit=3)

    assert len(tracks) == 1
    assert tracks[0].title == sample_gugak_track.title
    mock_track_repository.find_popular.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_get_track_detail_not_found(
    mock_track_repository: AsyncMock,
    mock_embedding_port: AsyncMock,
    mock_gemini_port: AsyncMock,
) -> None:
    mock_track_repository.find_by_id.return_value = None
    interactor = TrackDiscoverInteractor(
        track_repo=mock_track_repository,
        gemini=mock_gemini_port,
        embedding=mock_embedding_port,
    )

    with pytest.raises(TrackNotFoundException):
        await interactor.get_track_detail(str(uuid.uuid4()))


def test_template_explanations_ko(
    mock_track_repository: AsyncMock,
    mock_embedding_port: AsyncMock,
    mock_gemini_port: AsyncMock,
    sample_gugak_track: GugakTrack,
) -> None:
    interactor = TrackDiscoverInteractor(
        track_repo=mock_track_repository,
        gemini=mock_gemini_port,
        embedding=mock_embedding_port,
    )

    explanations = interactor._template_explanations(
        "뉴진스 어텐션",
        [sample_gugak_track],
        "ko",
    )

    assert len(explanations) == 1
    assert "회심곡" in explanations[0].explanation_ko
    assert explanations[0].track_id == sample_gugak_track.id
