# 레이어: Infrastructure — EXAONE 응답 텍스트 정리
from __future__ import annotations

import re


def clean_enriched_description(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:\w+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"^풍부한 설명\s*[:：]\s*", "", text).strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        text = text[1:-1].strip()
    return text
