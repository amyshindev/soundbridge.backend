# 레이어: Outbound Mapper — GugakTrackOrm → GugakTrack 도메인 엔티티 변환
from soundbridge.adapter.outbound.orm.track_orm import GugakTrackOrm
from soundbridge.domain.entities.track_entity import CuePoint, GugakTrack
from soundbridge.domain.value_objects.emotion_vo import EmotionTag
from soundbridge.domain.value_objects.instrument_vo import Instrument
from soundbridge.domain.value_objects.jangdan_vo import Jangdan, JangdanType
from soundbridge.domain.value_objects.license_vo import PublicLicense


class TrackOrmMapper:

    def to_entity(self, orm: GugakTrackOrm) -> GugakTrack:
        emotion_tags = [EmotionTag(row.emotion_tag) for row in orm.emotion_tag_rows]
        jangdan = Jangdan(type=JangdanType(orm.jangdan_name))
        cue_points = [
            CuePoint(
                time_sec=cp["time_sec"],
                label=cp["label"],
                emotion=cp.get("emotion", ""),
            )
            for cp in (orm.cue_points or [])
        ]
        return GugakTrack(
            id=orm.id,
            title=orm.title,
            artist=orm.artist,
            instrument=Instrument(orm.instrument),
            jangdan=jangdan,
            emotion_tags=emotion_tags,
            bpm=orm.bpm,
            cue_points=cue_points,
            audio_url=orm.audio_url,
            public_license=PublicLicense(orm.public_license_type),
            description_ko=orm.description_ko,
            description_en=orm.description_en,
        )
