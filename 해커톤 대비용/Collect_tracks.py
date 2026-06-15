# collect_tracks.py
# 국립국악원 국악디지털음원 API (XML) → gugak_tracks 테이블 INSERT
#
# 실행 전 확인:
#   1. data.go.kr 에서 API 키 발급 완료
#   2. PostgreSQL + pgvector 실행 중
#   3. Alembic migrate 완료 (gugak_tracks 테이블 존재)
#
# 환경변수 (.env):
#   GUGAK_API_KEY=발급받은_인증키
#   DATABASE_URL=postgresql://user:password@localhost:5432/soundbridge
#
# 실행:
#   python collect_tracks.py
#   python collect_tracks.py --dry-run   (DB 저장 없이 API 응답만 확인)
#   python collect_tracks.py --limit 50  (50건만 수집)

import os
import time
import uuid
import json
import argparse
import xml.etree.ElementTree as ET
import requests
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

# ── 설정 ──────────────────────────────────────────────────────────────────────
API_KEY  = os.getenv("GUGAK_API_KEY", "your_gugak_api_key")
DB_URL   = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/soundbridge")

# 공공데이터포털 국립국악원 국악디지털음원 API
BASE_URL = "https://apis.data.go.kr/1371034/phrasedataview2"

PAGE_SIZE   = 100    # 한 번에 가져올 건수 (최대 1000, 안정적으로 100 권장)
TARGET      = 500    # 수집 목표 건수
SLEEP_SEC   = 0.5    # 레이트 리밋 방지


# ── 1. XML 응답 파싱 ───────────────────────────────────────────────────────────
def _xml_text(elem: ET.Element | None, tag: str, default: str = "") -> str:
    if elem is None:
        return default
    child = elem.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _xml_item_to_dict(item_elem: ET.Element) -> dict:
    return {
        child.tag: (child.text or "").strip()
        for child in item_elem
        if child.tag
    }


def parse_xml_response(xml_text: str) -> tuple[list[dict], int]:
    """
    공공데이터포털 표준 XML → (items, total_count).
    구조: response > body > items > item, totalCount
    """
    xml_text = xml_text.strip()
    if not xml_text.startswith("<"):
        raise ValueError(f"XML이 아닌 응답: {xml_text[:300]}")

    root = ET.fromstring(xml_text)

    header = root.find("header")
    if header is not None:
        result_code = _xml_text(header, "resultCode")
        result_msg  = _xml_text(header, "resultMsg")
        if result_code and result_code != "00":
            raise ValueError(f"API 오류 {result_code}: {result_msg}")

    body = root.find("body")
    if body is None:
        raise ValueError("XML 응답에 body가 없습니다.")

    total_count = int(_xml_text(body, "totalCount", "0") or 0)

    items: list[dict] = []
    items_elem = body.find("items")
    if items_elem is not None:
        for item_elem in items_elem.findall("item"):
            items.append(_xml_item_to_dict(item_elem))

    return items, total_count


# ── 2. API 단일 페이지 호출 ───────────────────────────────────────────────────
def fetch_page(page: int, size: int) -> tuple[list[dict], int, str]:
    """
    공공데이터포털 API 호출 (XML 응답).
    국립국악원 API는 JSON을 지원하지 않고 XML만 반환합니다.
    """
    params = {
        "serviceKey": API_KEY,
        "pageNo":     page,
        "numOfRows":  size,
    }

    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()

    raw_xml = resp.text
    items, total_count = parse_xml_response(raw_xml)
    return items, total_count, raw_xml


# ── 3. 응답 필드 탐지 (첫 레코드 출력) ────────────────────────────────────────
def inspect_response(raw_xml: str, items: list[dict]) -> None:
    """
    API 응답 구조를 출력해서 실제 필드명 확인.
    처음 한 번만 실행해서 필드명 파악.
    """
    print("\n=== API XML 응답 (앞부분) ===")
    print(raw_xml[:3000])
    if items:
        print("\n=== 첫 번째 item (dict) ===")
        print(json.dumps(items[0], ensure_ascii=False, indent=2))
    print("=" * 40)


# ── 4. 응답 레코드 → gugak_tracks 스키마 매핑 ────────────────────────────────
def map_record(item: dict) -> dict | None:
    """
    API 응답 필드 → gugak_tracks 컬럼 매핑.

    공공데이터포털 국악디지털음원 API 주요 필드 (Swagger UI 기준):
      sorc_nm          : 음원명 (title)
      artst_nm         : 아티스트명 (artist)
      instrmnt_nm      : 악기명 (instrument)
      jangdan_nm       : 장단명 (jangdan)
      flctn_tempo      : 빠르기/BPM (bpm)
      sorc_cn          : 음원 설명 (description_ko)
      file_url         : 음원 파일 URL (audio_url)
      pblcte_se_nm     : 공개 구분 (public_license_type)

    ※ 실제 필드명이 다를 경우 아래 .get() 키를 Swagger UI에서 확인 후 수정
    """

    # 필수 필드 체크 — 없으면 스킵
    title = (
        item.get("sorc_nm") or
        item.get("srcNm") or
        item.get("title") or
        item.get("musicNm") or
        ""
    ).strip()

    if not title:
        return None

    # 악기명
    instrument = (
        item.get("instrmnt_nm") or
        item.get("instrmntNm") or
        item.get("instrument") or
        ""
    ).strip()

    # 장단명
    jangdan = (
        item.get("jangdan_nm") or
        item.get("jangdanNm") or
        item.get("jangdan") or
        ""
    ).strip()

    # BPM (문자열로 올 수 있으므로 안전하게 변환)
    bpm_raw = (
        item.get("flctn_tempo") or
        item.get("tempo") or
        item.get("bpm") or
        0
    )
    try:
        bpm = int(float(str(bpm_raw))) if bpm_raw else 0
    except (ValueError, TypeError):
        bpm = 0

    # 아티스트
    artist = (
        item.get("artst_nm") or
        item.get("artstNm") or
        item.get("artist") or
        ""
    ).strip()

    # 음원 URL
    audio_url = (
        item.get("file_url") or
        item.get("fileUrl") or
        item.get("audio_url") or
        item.get("url") or
        ""
    ).strip()

    # 설명
    description_ko = (
        item.get("sorc_cn") or
        item.get("srcCn") or
        item.get("description") or
        item.get("cn") or
        ""
    ).strip()

    # 저작권 유형
    license_type = (
        item.get("pblcte_se_nm") or
        item.get("pblctSeNm") or
        item.get("licenseType") or
        "KOGL_1"   # 국립국악원 기본값
    ).strip()

    # emotion_tags: API에 없으면 악기+장단으로 기본 추론
    # 실제 감성 태그는 embed_pipeline 전에 Claude로 보강
    emotion_tags = []
    if jangdan:
        # 장단 기반 기본 감성 매핑
        jangdan_emotion = {
            "자진모리": ["경쾌", "빠름"],
            "중모리":   ["서정", "느림"],
            "굿거리":   ["흥겨움", "신명"],
            "세마치":   ["슬픔", "차분"],
            "진양조":   ["슬픔", "깊음", "느림"],
            "엇모리":   ["독특", "변박"],
            "휘모리":   ["빠름", "긴박"],
        }
        for key, tags in jangdan_emotion.items():
            if key in jangdan:
                emotion_tags = tags
                break

    return {
        "id":                  str(uuid.uuid4()),
        "title":               title,
        "artist":              artist,
        "instrument":          instrument,
        "jangdan":             jangdan,
        "emotion_tags":        emotion_tags,
        "bpm":                 bpm,
        "audio_url":           audio_url,
        "public_license_type": license_type,
        "description_ko":      description_ko,
        "description_en":      "",   # Claude API로 나중에 생성
    }


# ── 5. DB에 트랙 저장 ─────────────────────────────────────────────────────────
def save_tracks(conn, tracks: list[dict]) -> int:
    """
    gugak_tracks 테이블에 INSERT.
    ON CONFLICT (title, artist) DO NOTHING → 중복 재실행 안전.
    """
    if not tracks:
        return 0

    cur = conn.cursor()

    # title + artist 중복 방지 인덱스가 없으면 title만으로 체크
    execute_values(
        cur,
        """
        INSERT INTO gugak_tracks (
            id, title, artist, instrument, jangdan,
            emotion_tags, bpm, audio_url,
            public_license_type, description_ko, description_en,
            created_at
        )
        VALUES %s
        ON CONFLICT DO NOTHING
        """,
        [
            (
                t["id"],
                t["title"],
                t["artist"],
                t["instrument"],
                t["jangdan"],
                t["emotion_tags"],
                t["bpm"],
                t["audio_url"],
                t["public_license_type"],
                t["description_ko"],
                t["description_en"],
                "NOW()",
            )
            for t in tracks
        ],
        template="(%s,%s,%s,%s,%s,%s::text[],%s,%s,%s,%s,%s,%s)"
    )

    inserted = cur.rowcount
    conn.commit()
    cur.close()
    return inserted


# ── 6. 전체 수집 실행 ─────────────────────────────────────────────────────────
def run_collect(target: int = TARGET, dry_run: bool = False) -> None:
    """
    페이지네이션으로 target 건수만큼 수집.
    dry_run=True → DB 저장 없이 API 응답 구조만 출력.
    """
    conn = None if dry_run else psycopg2.connect(DB_URL)

    total_saved  = 0
    total_skip   = 0
    page         = 1
    inspected    = False

    print(f"🎵 국악디지털음원 수집 시작 (목표: {target}건, dry_run={dry_run})\n")

    while total_saved < target:
        try:
            print(f"  📄 페이지 {page} 요청 중...")
            items, total_count, raw_xml = fetch_page(page, PAGE_SIZE)

            # 첫 번째 페이지에서 응답 구조 출력
            if not inspected:
                inspect_response(raw_xml, items)
                inspected = True

            if not items:
                print(f"  ✅ 더 이상 데이터 없음 (총 {total_count}건 중 {total_saved}건 수집)")
                break

            # 레코드 매핑
            mapped = []
            for item in items:
                record = map_record(item)
                if record:
                    mapped.append(record)
                else:
                    total_skip += 1

            # 목표 건수 초과 방지
            remaining = target - total_saved
            mapped    = mapped[:remaining]

            if dry_run:
                print(f"  [DRY RUN] 페이지 {page}: {len(mapped)}건 매핑됨")
                if mapped:
                    print(f"  첫 번째 레코드: {json.dumps(mapped[0], ensure_ascii=False, indent=2)}")
                total_saved += len(mapped)
            else:
                inserted = save_tracks(conn, mapped)
                total_saved += inserted
                print(f"  [{total_saved:>3}/{target}] 페이지 {page}: {inserted}건 저장, {total_skip}건 스킵")

            # 목표 달성
            if total_saved >= target:
                break

            # 마지막 페이지 체크
            if page * PAGE_SIZE >= total_count:
                print(f"  ✅ 전체 데이터 수집 완료 ({total_count}건 중 {total_saved}건)")
                break

            page += 1
            time.sleep(SLEEP_SEC)

        except requests.exceptions.HTTPError as e:
            print(f"  ❌ HTTP 오류: {e}")
            print(f"  응답: {e.response.text[:500] if e.response else 'N/A'}")
            break

        except requests.exceptions.ConnectionError:
            print(f"  ❌ 연결 오류 — API 서버 확인 필요")
            break

        except Exception as e:
            print(f"  ❌ 예외: {e}")
            import traceback
            traceback.print_exc()
            break

    if conn:
        conn.close()

    print(f"\n🎉 수집 완료 — 저장 {total_saved}건 / 스킵 {total_skip}건")
    print(f"\n다음 단계: python embed_pipeline.py")


# ── 7. 수집 후 현황 확인 ──────────────────────────────────────────────────────
def check_db() -> None:
    """수집 결과 DB 현황 출력."""
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM gugak_tracks")
    total = cur.fetchone()[0]

    cur.execute("SELECT instrument, COUNT(*) FROM gugak_tracks GROUP BY instrument ORDER BY COUNT(*) DESC LIMIT 10")
    by_instrument = cur.fetchall()

    cur.execute("SELECT jangdan, COUNT(*) FROM gugak_tracks GROUP BY jangdan ORDER BY COUNT(*) DESC LIMIT 10")
    by_jangdan = cur.fetchall()

    cur.close()
    conn.close()

    print(f"\n=== DB 현황 ===")
    print(f"총 트랙 수: {total}건")
    print(f"\n악기별 분포:")
    for inst, cnt in by_instrument:
        print(f"  {inst or '(없음)'}: {cnt}건")
    print(f"\n장단별 분포:")
    for jd, cnt in by_jangdan:
        print(f"  {jd or '(없음)'}: {cnt}건")


# ── 실행 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="국악디지털음원 수집 스크립트")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 API 응답 구조만 확인")
    parser.add_argument("--limit",   type=int, default=TARGET, help=f"수집 건수 (기본: {TARGET})")
    parser.add_argument("--check",   action="store_true", help="DB 현황만 출력")
    args = parser.parse_args()

    if args.check:
        check_db()
    else:
        run_collect(target=args.limit, dry_run=args.dry_run)