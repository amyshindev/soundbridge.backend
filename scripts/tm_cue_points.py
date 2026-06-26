"""TM 라벨링 JSON → gugak_tracks.cue_points (A/B/C) 변환."""

from __future__ import annotations

CUE_LABELS = ("A", "B", "C")


def _annotation_duration_sec(annotation: dict) -> float | None:
    ends: list[float] = []
    for key in ("sigimsage_regions", "lyrics_regions"):
        for region in annotation.get(key) or []:
            end = region.get("end_sec")
            if end is not None:
                ends.append(float(end))
    return max(ends) if ends else None


def _pad_moments(
    deduped: list[tuple[float, str]],
    duration_sec: float | None,
) -> list[tuple[float, str]]:
    if len(deduped) >= 3 or not duration_sec or duration_sec <= 0:
        return deduped

    default_emotion = deduped[0][1] if deduped else "구간"
    used = {time_sec for time_sec, _ in deduped}
    for ratio in (0.33, 0.66, 0.5, 0.25, 0.75):
        if len(deduped) >= 3:
            break
        candidate = duration_sec * ratio
        if any(abs(candidate - existing) < 0.25 for existing in used):
            continue
        deduped.append((candidate, default_emotion))
        used.add(candidate)

    deduped.sort(key=lambda item: item[0])
    return deduped


def _emotion_from_sigimsage(region: dict) -> str:
    types = region.get("sigimsage_types") or []
    if types:
        return str(types[0]).strip()
    return "시김새"


def _emotion_from_lyrics(region: dict) -> str:
    text = (region.get("lyrics") or "").strip()
    return text[:40] if text else "가사"


def build_cue_points_from_annotation(annotation: dict) -> list[dict]:
    """라벨링 annotation → [{time_sec, label, emotion}, ...] (최대 3개)."""
    moments: list[tuple[float, str]] = []

    for region in annotation.get("sigimsage_regions") or []:
        start = region.get("start_sec")
        if start is None:
            continue
        moments.append((float(start), _emotion_from_sigimsage(region)))

    for region in annotation.get("lyrics_regions") or []:
        start = region.get("start_sec")
        if start is None:
            continue
        moments.append((float(start), _emotion_from_lyrics(region)))

    if not moments:
        return []

    moments.sort(key=lambda item: item[0])

    deduped: list[tuple[float, str]] = []
    for time_sec, emotion in moments:
        if deduped and time_sec - deduped[-1][0] < 0.25:
            continue
        deduped.append((time_sec, emotion))

    deduped = _pad_moments(deduped, _annotation_duration_sec(annotation))

    if len(deduped) == 1:
        picks = [0]
    elif len(deduped) == 2:
        picks = [0, 1]
    else:
        last = len(deduped) - 1
        mid = last // 2
        picks = [0, mid, last]

    return [
        {
            "time_sec": round(deduped[i][0], 2),
            "label": CUE_LABELS[idx],
            "emotion": deduped[i][1],
        }
        for idx, i in enumerate(picks[:3])
    ]
