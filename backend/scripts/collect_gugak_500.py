"""국립국악원 국악디지털음원 OpenAPI 수집 스크립트.

API: http://apis.data.go.kr/1371034/phrasedataview2/view
데이터셋: https://www.data.go.kr/data/15097515/openapi.do
"""

from __future__ import annotations

import csv
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("GUGAK_API_KEY")
BASE_URL = "http://apis.data.go.kr/1371034/phrasedataview2/view"
DATASET_URL = "https://www.data.go.kr/data/15097515/openapi.do"


def _item_to_dict(item: ET.Element) -> dict[str, str]:
    return {child.tag: (child.text or "") for child in item}


def fetch_page(page: int = 1, size: int = 100) -> tuple[list[dict[str, str]], int]:
    if not API_KEY:
        raise RuntimeError("GUGAK_API_KEY가 .env에 없습니다.")

    response = requests.get(
        BASE_URL,
        params={
            "serviceKey": API_KEY,
            "pageNo": page,
            "numOfRows": size,
        },
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = "utf-8"

    text = response.text.strip()
    if not text.startswith("<"):
        raise RuntimeError(
            f"XML이 아닌 응답 (HTTP {response.status_code}): {text[:200]}"
        )

    root = ET.fromstring(text)
    header = root.find("header")
    if header is not None:
        code = (header.findtext("resultCode") or "").strip()
        message = (header.findtext("resultMsg") or "").strip()
        if code and code not in ("00", "0"):
            raise RuntimeError(f"API 오류 resultCode={code} ({message})")

    body = root.find("body")
    if body is None:
        raise RuntimeError("응답에 body가 없습니다.")

    total_count = int(body.findtext("totalCount") or "0")
    items = [_item_to_dict(item) for item in body.findall(".//item")]
    return items, total_count


def collect_tracks(
    *,
    target_count: int = 500,
    page_size: int = 100,
    delay_sec: float = 0.5,
) -> list[dict[str, str]]:
    all_tracks: list[dict[str, str]] = []
    total_count: int | None = None
    page = 1

    while len(all_tracks) < target_count:
        print(f"페이지 {page} 수집 중...")
        try:
            items, total_count = fetch_page(page=page, size=page_size)
        except Exception as exc:
            print(f"  오류: {exc}")
            print(f"  활용신청 확인: {DATASET_URL}")
            break

        if page == 1:
            if items:
                print("응답 필드명:", list(items[0].keys()))
            print(f"  전체 {total_count}건 중 수집 목표 {target_count}건")

        if not items:
            print("  더 이상 데이터 없음")
            break

        all_tracks.extend(items)
        print(f"  → {len(items)}건 수집 (누계: {len(all_tracks)}건)")

        if len(all_tracks) >= total_count:
            break

        page += 1
        time.sleep(delay_sec)

    return all_tracks[:target_count]


def save_csv(tracks: list[dict[str, str]], filename: str = "gugak_500.csv") -> None:
    if not tracks:
        print("수집된 데이터 없음")
        return

    output = Path(filename)
    if not output.is_absolute():
        output = Path(__file__).resolve().parent / output

    fieldnames = list(tracks[0].keys())
    with output.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(tracks)
    print(f"{output} 저장 완료 ({len(tracks)}건)")


if __name__ == "__main__":
    try:
        tracks = collect_tracks()
        save_csv(tracks)
    except KeyboardInterrupt:
        sys.exit(130)
