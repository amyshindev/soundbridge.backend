"""국립국악원 API(XML) -> 현재 SoundBridge 스키마 적재 스크립트.

대상 테이블
- gugak_tracks (jangdan_name, cue_points, ...)
- track_emotion_tags (분리 테이블)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import psycopg
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GUGAK_API_KEY", "").strip()
DB_URL = os.getenv("DATABASE_URL", "").strip()
BASE_URL = "https://apis.data.go.kr/1371034/phrasedataview2/view"

PAGE_SIZE = 20
TARGET = 500
SLEEP_SEC = 0.4

VALID_JANGDAN = {"자진모리", "중모리", "굿거리", "휘모리", "세마치", "엇모리"}
VALID_EMOTIONS = {"신남", "서정", "웅장", "슬픔", "신비", "차분"}
JANGDAN_FALLBACK = "중모리"

# 국악 API 악기 코드 → 백엔드 Instrument enum 한글명
INSTRUMENT_CODE_MAP: dict[str, str] = {
    "PHINST0022": "장구",
    "PHINST0001": "가야금",
    "PHINST0002": "대금",
    "PHINST0003": "해금",
    "PHINST0004": "거문고",
    "PHINST0005": "피리",
    "PHINST0006": "아쟁",
    "PHINST0007": "소금",
}

INSTRUMENT_KEYWORDS: list[tuple[str, str]] = [
    ("장구", "장구"),
    ("가야금", "가야금"),
    ("대금", "대금"),
    ("해금", "해금"),
    ("거문고", "거문고"),
    ("피리", "피리"),
    ("아쟁", "아쟁"),
    ("소금", "소금"),
    ("jang-gu", "장구"),
    ("gayageum", "가야금"),
    ("daegeum", "대금"),
    ("haegeum", "해금"),
    ("geomungo", "거문고"),
    ("piri", "피리"),
    ("ajaeng", "아쟁"),
    ("sogeum", "소금"),
]


def normalize_db_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg://")
    if url.startswith("postgresql+psycopg_async://"):
        return "postgresql://" + url.removeprefix("postgresql+psycopg_async://")
    return url


def _xml_text(elem: ET.Element | None, tag: str, default: str = "") -> str:
    if elem is None:
        return default
    child = elem.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _xml_item_to_dict(item_elem: ET.Element) -> dict[str, str]:
    return {child.tag: (child.text or "").strip() for child in item_elem if child.tag}


def parse_xml_response(xml_text: str) -> tuple[list[dict[str, str]], int]:
    root = ET.fromstring(xml_text.strip())
    header = root.find("header")
    if header is not None:
        code = _xml_text(header, "resultCode")
        msg = _xml_text(header, "resultMsg")
        if code and code not in {"00", "0"}:
            raise ValueError(f"API 오류 {code}: {msg}")

    body = root.find("body")
    if body is None:
        raise ValueError("XML body 없음")
    total_count = int(_xml_text(body, "totalCount", "0") or 0)

    items: list[dict[str, str]] = []
    items_elem = body.find("items")
    if items_elem is not None:
        for item_elem in items_elem.findall("item"):
            items.append(_xml_item_to_dict(item_elem))
    return items, total_count


def fetch_page(page: int, size: int) -> tuple[list[dict[str, str]], int, str]:
    if not API_KEY:
        raise RuntimeError("GUGAK_API_KEY 가 비어 있습니다.")
    resp = requests.get(
        BASE_URL,
        params={"serviceKey": API_KEY, "pageNo": page, "numOfRows": size},
        timeout=60,
    )
    resp.raise_for_status()
    items, total_count = parse_xml_response(resp.text)
    return items, total_count, resp.text


def infer_jangdan(item: dict[str, str]) -> str:
    candidates = [
        item.get("jangdan_nm", ""),
        item.get("jangdanNm", ""),
        item.get("jangdan", ""),
        item.get("rhythm", ""),
        item.get("beat", ""),
    ]
    blob = " ".join(candidates)
    for jangdan in VALID_JANGDAN:
        if jangdan in blob:
            return jangdan

    rhythm = (item.get("rhythm") or item.get("beat") or "").strip()
    if "12" in rhythm:
        return "자진모리"
    if "6" in rhythm:
        return "세마치"
    if "4" in rhythm:
        return "휘모리"
    if "5" in rhythm or "10" in rhythm:
        return "엇모리"
    if "3" in rhythm:
        return "중모리"

    title = item.get("phrs_nm_kor") or item.get("title") or ""
    idx = sum(ord(c) for c in title) % len(VALID_JANGDAN)
    return list(VALID_JANGDAN)[idx]


def infer_emotions(jangdan: str) -> list[str]:
    table: dict[str, list[str]] = {
        "자진모리": ["신남", "웅장"],
        "중모리": ["서정", "차분"],
        "굿거리": ["신남", "웅장"],
        "휘모리": ["신남", "슬픔"],
        "세마치": ["슬픔", "차분"],
        "엇모리": ["신비", "웅장"],
    }
    tags = table.get(jangdan, ["차분"])
    return [t for t in tags if t in VALID_EMOTIONS]


def infer_instrument(item: dict[str, str]) -> str:
    code = (item.get("instr_cd") or item.get("instrument_code") or "").strip().upper()
    if code in INSTRUMENT_CODE_MAP:
        return INSTRUMENT_CODE_MAP[code]

    for field in ("instrmnt_nm", "instrument", "phrs_desc_kor", "phrs_nm_eng"):
        text = (item.get(field) or "").strip()
        for keyword, name in INSTRUMENT_KEYWORDS:
            if keyword in text:
                return name

    return "장구"


def parse_bpm(item: dict[str, str]) -> int:
    raw = item.get("flctn_tempo") or item.get("tempo") or item.get("bpm") or ""
    m = re.search(r"\d+", str(raw))
    if m:
        return int(m.group())
    return 90


def normalize_license(item: dict[str, str]) -> str:
    raw = (
        item.get("pblcte_se_nm")
        or item.get("pblctSeNm")
        or item.get("public_license_type")
        or ""
    )
    if "2" in raw:
        return "KOGL_2"
    return "KOGL_1"


def map_record(item: dict[str, str]) -> dict | None:
    title = (item.get("phrs_nm_kor") or item.get("sorc_nm") or item.get("title") or "").strip()
    if not title:
        return None

    artist = (item.get("singer") or item.get("artst_nm") or item.get("artist") or "국립국악원").strip()
    instrument = infer_instrument(item)
    jangdan_name = infer_jangdan(item)
    bpm = parse_bpm(item)
    audio_url = (item.get("wav_file_path") or item.get("file_url") or item.get("audio_url") or "").strip()
    description_ko = (item.get("phrs_desc_kor") or item.get("sorc_cn") or "").strip()
    description_en = (item.get("phrs_desc_eng") or "").strip()
    license_type = normalize_license(item)
    emotion_tags = infer_emotions(jangdan_name)

    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "artist": artist,
        "instrument": instrument,
        "jangdan_name": jangdan_name,
        "bpm": bpm,
        "cue_points": json.dumps([]),
        "audio_url": audio_url,
        "public_license_type": license_type,
        "description_ko": description_ko,
        "description_en": description_en,
        "created_at": datetime.now(timezone.utc),
        "emotion_tags": emotion_tags,
    }


def load_from_csv(csv_path: str, limit: int) -> list[dict]:
    rows: list[dict] = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = map_record(row)
            if rec:
                rows.append(rec)
            if len(rows) >= limit:
                break
    return rows


def get_existing_keys(conn) -> set[tuple[str, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT title, artist FROM gugak_tracks")
        return {(row[0], row[1]) for row in cur.fetchall()}


def save_tracks(conn, tracks: list[dict]) -> int:
    if not tracks:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO gugak_tracks (
                id, title, artist, instrument, jangdan_name, bpm,
                cue_points, audio_url, public_license_type,
                description_ko, description_en, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
            """,
            [
                (
                    t["id"],
                    t["title"],
                    t["artist"],
                    t["instrument"],
                    t["jangdan_name"],
                    t["bpm"],
                    t["cue_points"],
                    t["audio_url"],
                    t["public_license_type"],
                    t["description_ko"],
                    t["description_en"],
                    t["created_at"],
                )
                for t in tracks
            ],
        )

        tag_rows = []
        for t in tracks:
            for i, tag in enumerate(t["emotion_tags"]):
                tag_rows.append((str(uuid.uuid4()), t["id"], tag, i))
        if tag_rows:
            cur.executemany(
                """
                INSERT INTO track_emotion_tags (id, track_id, emotion_tag, sort_order)
                VALUES (%s, %s, %s, %s)
                """,
                tag_rows,
            )
    conn.commit()
    return len(tracks)


def inspect_response(raw_xml: str, items: list[dict[str, str]]) -> None:
    print("\n=== API XML 응답 미리보기 ===")
    print(raw_xml[:1200])
    if items:
        print("\n=== 첫 item ===")
        print(json.dumps(items[0], ensure_ascii=False, indent=2))
    print("=" * 40)


def run_collect(target: int = TARGET, dry_run: bool = False, csv_path: str = "") -> None:
    if not dry_run and not DB_URL:
        raise RuntimeError("DATABASE_URL 이 비어 있습니다.")

    conn = None if dry_run else psycopg.connect(normalize_db_url(DB_URL))
    existing = set() if dry_run else get_existing_keys(conn)

    total_saved = 0
    total_skip = 0
    page = 1
    inspected = False

    if csv_path:
        print(f"CSV 적재 시작 target={target} dry_run={dry_run} file={csv_path}")
        mapped = load_from_csv(csv_path, target)
        deduped = []
        for rec in mapped:
            key = (rec["title"], rec["artist"])
            if key in existing:
                total_skip += 1
                continue
            existing.add(key)
            deduped.append(rec)
        if dry_run:
            print(f"[DRY] mapped={len(deduped)} skip={total_skip}")
            if deduped:
                print(json.dumps(deduped[0], ensure_ascii=False, indent=2, default=str))
            total_saved = len(deduped)
        else:
            total_saved = save_tracks(conn, deduped)
            print(f"[{total_saved}/{target}] inserted={total_saved} skip={total_skip}")
        if conn:
            conn.close()
        print(f"완료: saved={total_saved}, skip={total_skip}")
        return

    print(f"수집 시작 target={target} dry_run={dry_run}")
    while total_saved < target:
        items, total_count, raw_xml = fetch_page(page, PAGE_SIZE)
        if not inspected:
            inspect_response(raw_xml, items)
            inspected = True
        if not items:
            break

        mapped: list[dict] = []
        for item in items:
            record = map_record(item)
            if not record:
                total_skip += 1
                continue
            key = (record["title"], record["artist"])
            if key in existing:
                total_skip += 1
                continue
            existing.add(key)
            mapped.append(record)

        mapped = mapped[: target - total_saved]
        if dry_run:
            total_saved += len(mapped)
            print(f"[DRY] page={page} mapped={len(mapped)} skip={total_skip}")
            if mapped:
                print(json.dumps(mapped[0], ensure_ascii=False, indent=2, default=str))
        else:
            inserted = save_tracks(conn, mapped)
            total_saved += inserted
            print(f"[{total_saved}/{target}] page={page} inserted={inserted} skip={total_skip}")

        if page * PAGE_SIZE >= total_count:
            break
        page += 1
        time.sleep(SLEEP_SEC)

    if conn:
        conn.close()
    print(f"완료: saved={total_saved}, skip={total_skip}")


def check_db() -> None:
    conn = psycopg.connect(normalize_db_url(DB_URL))
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM gugak_tracks")
        total = cur.fetchone()[0]
        cur.execute(
            "SELECT instrument, COUNT(*) FROM gugak_tracks "
            "GROUP BY instrument ORDER BY COUNT(*) DESC LIMIT 10"
        )
        by_inst = cur.fetchall()
        cur.execute(
            "SELECT jangdan_name, COUNT(*) FROM gugak_tracks "
            "GROUP BY jangdan_name ORDER BY COUNT(*) DESC LIMIT 10"
        )
        by_jangdan = cur.fetchall()
    conn.close()

    print(f"\n총 트랙: {total}")
    print("\n악기 분포:")
    for inst, cnt in by_inst:
        print(f"  {inst or '(없음)'}: {cnt}")
    print("\n장단 분포:")
    for jangdan, cnt in by_jangdan:
        print(f"  {jangdan or '(없음)'}: {cnt}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="국악디지털음원 수집 -> DB 적재")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 매핑만 확인")
    parser.add_argument("--limit", type=int, default=TARGET, help=f"수집 건수 (기본 {TARGET})")
    parser.add_argument("--check", action="store_true", help="DB 통계만 출력")
    parser.add_argument("--csv", type=str, default="", help="로컬 CSV 경로 (예: scripts/gugak_500.csv)")
    args = parser.parse_args()

    if args.check:
        check_db()
    else:
        run_collect(target=args.limit, dry_run=args.dry_run, csv_path=args.csv)