"""domain 레이어 — GugakTrack 엔티티 테스트."""
from soundbridge.domain.entities.track_entity import GugakTrack
from soundbridge.domain.value_objects.emotion_vo import EmotionTag
from soundbridge.domain.value_objects.license_vo import PublicLicense


def test_loop_unit_beats_from_jangdan(sample_gugak_track: GugakTrack) -> None:
    assert sample_gugak_track.loop_unit_beats == 12


def test_license_properties_kogl_1(sample_gugak_track: GugakTrack) -> None:
    assert sample_gugak_track.public_license == PublicLicense.KOGL_1
    assert sample_gugak_track.is_commercial is True
    assert sample_gugak_track.license_label_en == "CC-BY (Commercial OK)"


def test_primary_emotion(sample_gugak_track: GugakTrack) -> None:
    assert sample_gugak_track.primary_emotion == EmotionTag.LYRICAL


def test_primary_emotion_empty_when_no_tags(track_id, sample_gugak_track: GugakTrack) -> None:
    track = GugakTrack(
        id=sample_gugak_track.id,
        title=sample_gugak_track.title,
        artist=sample_gugak_track.artist,
        instrument=sample_gugak_track.instrument,
        jangdan=sample_gugak_track.jangdan,
        emotion_tags=[],
        bpm=sample_gugak_track.bpm,
        cue_points=sample_gugak_track.cue_points,
        audio_url=sample_gugak_track.audio_url,
        public_license=sample_gugak_track.public_license,
        description_ko=sample_gugak_track.description_ko,
        description_en=sample_gugak_track.description_en,
    )
    assert track.primary_emotion is None
