"""Normalize gugak CSV fields to constrained label sets.

Target normalized sets:
- jangdan: 자진모리/중모리/굿거리/휘모리/세마치/엇모리
- instrument: 가야금/거문고/대금/해금/피리/아쟁
- emotion tags: 신남/서정/웅장/슬픔/신비/차분

This script reads an input CSV and writes a new CSV with added columns:
- jangdan_name
- instrument_name
- emotion_tags

Usage:
  python backend/scripts/normalize_gugak_csv.py \
    --input backend/scripts/gugak_500.csv \
    --output backend/scripts/gugak_500_normalized.csv
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

JANGDAN_VALUES = ("자진모리", "중모리", "굿거리", "휘모리", "세마치", "엇모리")
INSTRUMENT_VALUES = ("가야금", "거문고", "대금", "해금", "피리", "아쟁")
EMOTION_VALUES = ("신남", "서정", "웅장", "슬픔", "신비", "차분")

# Raw source code/name -> normalized instrument (restricted set)
INSTRUMENT_CODE_MAP: dict[str, str] = {
    # likely codes in public API
    "PHINST0001": "가야금",
    "PHINST0002": "대금",
    "PHINST0003": "해금",
    "PHINST0004": "거문고",
    "PHINST0005": "피리",
    "PHINST0006": "아쟁",
    # non-target instruments fallback to closest string family
    "PHINST0007": "대금",   # 소금 -> 관악기
    "PHINST0022": "아쟁",   # 장구 -> target set fallback
}

INSTRUMENT_KEYWORDS: list[tuple[str, str]] = [
    ("가야금", "가야금"),
    ("gayageum", "가야금"),
    ("거문고", "거문고"),
    ("geomungo", "거문고"),
    ("대금", "대금"),
    ("daegeum", "대금"),
    ("해금", "해금"),
    ("haegeum", "해금"),
    ("피리", "피리"),
    ("piri", "피리"),
    ("아쟁", "아쟁"),
    ("ajaeng", "아쟁"),
]

JANGDAN_EMOTION_MAP: dict[str, tuple[str, ...]] = {
    "자진모리": ("신남", "웅장"),
    "중모리": ("서정", "차분"),
    "굿거리": ("신남", "웅장"),
    "휘모리": ("신남", "슬픔"),
    "세마치": ("슬픔", "차분"),
    "엇모리": ("신비", "웅장"),
}


def infer_jangdan(row: dict[str, str]) -> str:
    text = " ".join(
        [
            row.get("rhythm", ""),
            row.get("beat", ""),
            row.get("phrs_desc_kor", ""),
            row.get("phrs_nm_kor", ""),
        ]
    )
    text = text.strip()

    for j in JANGDAN_VALUES:
        if j in text:
            return j

    if re.search(r"12", text):
        return "자진모리"
    if re.search(r"10|5", text):
        return "엇모리"
    if re.search(r"6", text):
        return "세마치"
    if re.search(r"4", text):
        return "휘모리"
    if re.search(r"3", text):
        return "중모리"

    return "중모리"


def infer_instrument(row: dict[str, str]) -> str:
    code = (row.get("instr_cd") or "").strip().upper()
    if code in INSTRUMENT_CODE_MAP:
        return INSTRUMENT_CODE_MAP[code]

    haystack = " ".join(
        [
            row.get("instr_cd", ""),
            row.get("phrs_desc_kor", ""),
            row.get("phrs_nm_kor", ""),
            row.get("phrs_desc_eng", ""),
            row.get("phrs_nm_eng", ""),
        ]
    ).lower()

    for keyword, normalized in INSTRUMENT_KEYWORDS:
        if keyword.lower() in haystack:
            return normalized

    return "가야금"


def infer_emotion_tags(jangdan: str) -> str:
    tags = JANGDAN_EMOTION_MAP.get(jangdan, ("차분",))
    # Pipe-separated string to keep CSV compact and deterministic.
    return "|".join(tag for tag in tags if tag in EMOTION_VALUES)


def normalize_csv(input_path: Path, output_path: Path) -> None:
    jangdan_counter: Counter[str] = Counter()
    instrument_counter: Counter[str] = Counter()
    emotion_counter: Counter[str] = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as rf:
        reader = csv.DictReader(rf)
        if not reader.fieldnames:
            raise ValueError("CSV header is missing.")

        out_fields = list(reader.fieldnames)
        for col in ("jangdan_name", "instrument_name", "emotion_tags"):
            if col not in out_fields:
                out_fields.append(col)

        with output_path.open("w", encoding="utf-8-sig", newline="") as wf:
            writer = csv.DictWriter(wf, fieldnames=out_fields)
            writer.writeheader()

            for row in reader:
                jangdan = infer_jangdan(row)
                instrument = infer_instrument(row)
                emotion_tags = infer_emotion_tags(jangdan)

                row["jangdan_name"] = jangdan
                row["instrument_name"] = instrument
                row["emotion_tags"] = emotion_tags
                writer.writerow(row)

                jangdan_counter[jangdan] += 1
                instrument_counter[instrument] += 1
                for tag in emotion_tags.split("|"):
                    emotion_counter[tag] += 1

    print(f"[done] input={input_path}")
    print(f"[done] output={output_path}")
    print("[summary] jangdan:", dict(jangdan_counter))
    print("[summary] instrument:", dict(instrument_counter))
    print("[summary] emotion:", dict(emotion_counter))


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize gugak CSV fields.")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

    normalize_csv(input_path=input_path, output_path=output_path)


if __name__ == "__main__":
    main()
