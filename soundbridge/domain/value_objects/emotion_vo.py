from enum import Enum


class EmotionTag(str, Enum):
    JOYFUL = "신남"
    LYRICAL = "서정"
    GRAND = "웅장"
    SAD = "슬픔"
    MYSTICAL = "신비"
    CALM = "차분"


EMOTION_TAG_EN: dict[EmotionTag, str] = {
    EmotionTag.JOYFUL: "Joyful",
    EmotionTag.LYRICAL: "Lyrical",
    EmotionTag.GRAND: "Grand",
    EmotionTag.SAD: "Melancholic",
    EmotionTag.MYSTICAL: "Mystical",
    EmotionTag.CALM: "Calm",
}
