# 레이어: Application — TM 트랙 enrich 프롬프트·임베딩 입력 텍스트 조립
from __future__ import annotations

from soundbridge.app.dtos.track_enrich_embed_dto import TrackEnrichTarget
from soundbridge.app.policies.track_enrich_policy import TRACK_ENRICH_PROMPT


def _instrument_display(value: str) -> str:
    if value in ("기타", "미분류", ""):
        return "미분류"
    return value


def _jangdan_display(jangdan_raw: str, jangdan_name: str) -> str:
    return jangdan_raw or jangdan_name or "없음"


def build_enrich_prompt(track: TrackEnrichTarget) -> str:
    emotions = ", ".join(track.emotion_tags) if track.emotion_tags else "없음"
    return TRACK_ENRICH_PROMPT.format(
        title=track.title,
        artist=track.artist,
        instrument=_instrument_display(track.instrument),
        jangdan=_jangdan_display(track.jangdan_raw, track.jangdan_name),
        emotions=emotions,
        description=track.description_ko or "없음",
    )


def build_embedding_document_text(
    track: TrackEnrichTarget,
    description_ko: str,
) -> str:
    genre_parts = [g for g in (track.genre_lclsf, track.genre_mclsf, track.genre_sclsf) if g]
    genre_line = " / ".join(genre_parts) if genre_parts else "없음"
    jangdan_display = _jangdan_display(track.jangdan_raw, track.jangdan_name)
    tags = ", ".join(track.emotion_tags) if track.emotion_tags else "없음"

    raw_emotions = sorted(
        track.whole_emotions or [],
        key=lambda x: int(x.get("count") or 0),
        reverse=True,
    )
    emotion_detail = ", ".join(
        f"{item.get('emotion', '')}({item.get('count', 0)})"
        for item in raw_emotions[:6]
        if item.get("emotion")
    )
    raw_tones = sorted(
        track.whole_tones or [],
        key=lambda x: int(x.get("count") or 0),
        reverse=True,
    )
    tone_detail = ", ".join(
        f"{item.get('tone', '')}({item.get('count', 0)})"
        for item in raw_tones[:6]
        if item.get("tone")
    )
    tempo_display = (
        track.tempo_label if track.tempo_label and track.tempo_label.upper() != "N/A" else "없음"
    )
    time_sig_display = track.time_signature or "없음"

    lines = [
        f"제목: {track.title}",
        f"연주·가창: {track.artist}",
        f"장르: {genre_line}",
        f"장단: {jangdan_display}",
        f"박자: {time_sig_display}  템포: {tempo_display}",
        f"감성 태그: {tags}",
    ]
    if emotion_detail:
        lines.append(f"감성 상세: {emotion_detail}")
    if tone_detail:
        lines.append(f"음색: {tone_detail}")
    lines.append(f"설명: {description_ko or '없음'}")
    return "\n".join(lines)
