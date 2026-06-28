# 레이어: Domain — 감성 태그 VO (DISCOVER 필터 + TM 라벨 정규화)
from enum import Enum


class EmotionTag(str, Enum):
    JOYFUL = "신남"
    LYRICAL = "서정"
    GRAND = "웅장"
    SAD = "슬픔"
    MYSTICAL = "신비"
    CALM = "차분"


DISCOVER_EMOTION_VALUES: tuple[str, ...] = tuple(member.value for member in EmotionTag)

EMOTION_TAG_EN: dict[EmotionTag, str] = {
    EmotionTag.JOYFUL: "Joyful",
    EmotionTag.LYRICAL: "Lyrical",
    EmotionTag.GRAND: "Grand",
    EmotionTag.SAD: "Melancholic",
    EmotionTag.MYSTICAL: "Mystical",
    EmotionTag.CALM: "Calm",
}

# TM whole_emotions 원문 라벨 → DISCOVER 6감성
TM_EMOTION_LABEL_MAP: dict[str, str] = {
    "신비로운": EmotionTag.MYSTICAL.value,
    "몽환적인": EmotionTag.MYSTICAL.value,
    "차분한": EmotionTag.CALM.value,
    "잔잔한": EmotionTag.CALM.value,
    "명상적인": EmotionTag.CALM.value,
    "애절한": EmotionTag.SAD.value,
    "쓸쓸한": EmotionTag.SAD.value,
    "강렬한": EmotionTag.GRAND.value,
    "강한": EmotionTag.GRAND.value,
    "기품 있는": EmotionTag.GRAND.value,
    "웅장한": EmotionTag.GRAND.value,
    "서사적인": EmotionTag.LYRICAL.value,
    "시적인": EmotionTag.LYRICAL.value,
    "다정한": EmotionTag.LYRICAL.value,
    "표현적인": EmotionTag.LYRICAL.value,
    "단아한": EmotionTag.LYRICAL.value,
    "우아한": EmotionTag.LYRICAL.value,
    "진지한": EmotionTag.CALM.value,
    "신나는": EmotionTag.JOYFUL.value,
    "활기찬": EmotionTag.JOYFUL.value,
}


def map_tm_emotion_tags(whole_emotions: list[dict], *, top_n: int = 3) -> list[str]:
    """TM whole_emotions → 정규화된 감성 태그(빈도 상위 N개)."""
    scored: dict[str, int] = {}
    for item in whole_emotions or []:
        label = (item.get("emotion") or "").strip()
        count = int(item.get("count") or 1)
        mapped = TM_EMOTION_LABEL_MAP.get(label)
        if mapped:
            scored[mapped] = scored.get(mapped, 0) + count

    if not scored:
        return []

    ranked = sorted(scored.items(), key=lambda item: item[1], reverse=True)
    return [tag for tag, _ in ranked[:top_n]]
