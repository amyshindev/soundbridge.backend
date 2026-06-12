# 레이어: Application — Domain → DTO 변환
from soundbridge.app.dtos.track_discover_dto import TrackResult
from soundbridge.domain.entities.track_entity import GugakTrack
from soundbridge.domain.value_objects.license_vo import LICENSE_EN_LABEL


def to_track_result(track: GugakTrack) -> TrackResult:
    return TrackResult(
        track_id=track.id,
        title=track.title,
        artist=track.artist,
        instrument=track.instrument.value,
        jangdan=track.jangdan.type.value,
        emotion_tags=[e.value for e in track.emotion_tags],
        bpm=track.bpm,
        loop_unit_beats=track.loop_unit_beats,
        cue_points=[
            {"time_sec": cp.time_sec, "label": cp.label, "emotion": cp.emotion}
            for cp in track.cue_points
        ],
        audio_url=track.audio_url,
        license_type=track.public_license.value,
        license_label_en=LICENSE_EN_LABEL[track.public_license],
        description_ko=track.description_ko,
        description_en=track.description_en,
    )
