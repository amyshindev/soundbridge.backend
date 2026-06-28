# 레이어: Outbound Mapper — GugakTrackOrm → GugakTrack 도메인 엔티티 변환
from soundbridge.adapter.outbound.orm.track_orm import GugakTrackOrm
from soundbridge.domain.entities.cue_point_entity import CuePoint
from soundbridge.domain.entities.track_entity import GugakTrack
from soundbridge.domain.value_objects.emotion_vo import EmotionTag
from soundbridge.domain.value_objects.instrument_vo import Instrument
from soundbridge.domain.value_objects.jangdan_vo import Jangdan
from soundbridge.domain.value_objects.license_vo import PublicLicense


class TrackOrmMapper:

    def to_entity(self, orm: GugakTrackOrm) -> GugakTrack:
        instrument = Instrument.from_db_value(orm.instrument)

        jangdan = Jangdan.from_name(orm.jangdan_name or "")

        try:
            license_type = PublicLicense(orm.public_license_type)
        except ValueError:
            license_type = PublicLicense.KOGL_1

        emotion_tags: list[EmotionTag] = []
        for row in orm.emotion_tag_rows:
            try:
                emotion_tags.append(EmotionTag(row.emotion_tag))
            except ValueError:
                pass

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
            title=orm.title or "",
            artist=orm.artist or "",
            instrument=instrument,
            jangdan=jangdan,
            emotion_tags=emotion_tags,
            bpm=orm.bpm or 0,
            cue_points=cue_points,
            audio_url=orm.audio_url or "",
            public_license=license_type,
            description_ko=orm.description_ko or "",
            description_en=orm.description_en or "",
            source_identifier=orm.source_identifier,
            genre_mclsf=(orm.genre_mclsf or "").strip(),
        )
