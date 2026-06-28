"""TM 원천데이터 음원(wav/mp3) → Cloudflare R2 업로드.

로컬 `원천데이터` 아래 KC_TM_* 파일을 R2에 올리고, 선택적으로 DB `audio_url`을
공개 URL로 갱신합니다. (프론트 `resolveAudioUrl`은 https URL을 그대로 사용)

필수 env (.env):
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_ENDPOINT_URL          # https://<account_id>.r2.cloudflarestorage.com
  R2_BUCKET_NAME

선택 env:
  R2_PUBLIC_BASE_URL       # 예: https://pub-xxxx.r2.dev 또는 커스텀 CDN (--update-db 시 필요)
  R2_KEY_PREFIX            # 객체 키 접두사 (기본 빈 문자열, 예: tm/)

Usage:
  cd backend
  python scripts/upload_audio_to_r2.py --dry-run --limit 5
  python scripts/upload_audio_to_r2.py --data-root "C:/Users/hi/Desktop/국악음원_sample/test"
  python scripts/upload_audio_to_r2.py --skip-existing
  python scripts/upload_audio_to_r2.py --update-db
"""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
import psycopg

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from soundbridge.app.dtos.r2_storage_dto import R2StorageConfig
from soundbridge.infrastructure.audio_file_resolver import validate_audio_filename
from soundbridge.infrastructure.pg_script_util import load_database_url, normalize_psycopg_url
from soundbridge.infrastructure.secret_manager import secretmanager

AUDIO_EXTENSIONS = {".wav", ".mp3"}


def create_s3_client(cfg: R2StorageConfig):
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint_url,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
        region_name="auto",
    )


def iter_tm_audio_files(data_root: Path) -> list[Path]:
    """data_root 또는 data_root/원천데이터 아래 TM 음원 파일 수집 (파일명 기준 dedupe)."""
    candidates = [data_root, data_root / "원천데이터"]
    search_roots = [p for p in candidates if p.is_dir()]
    if not search_roots:
        raise FileNotFoundError(
            f"음원 폴더를 찾을 수 없습니다: {data_root} 또는 {data_root / '원천데이터'}"
        )

    by_name: dict[str, Path] = {}
    for root in search_roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            try:
                validate_audio_filename(path.name)
            except ValueError:
                continue
            by_name[path.name] = path

    return [by_name[name] for name in sorted(by_name)]


def guess_content_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".wav":
        return "audio/wav"
    if ext == ".mp3":
        return "audio/mpeg"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def object_exists(client, cfg: R2StorageConfig, key: str) -> bool:
    try:
        client.head_object(Bucket=cfg.bucket_name, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def upload_file(client, cfg: R2StorageConfig, path: Path) -> str:
    filename = path.name
    key = cfg.object_key(filename)
    client.upload_file(
        str(path),
        cfg.bucket_name,
        key,
        ExtraArgs={"ContentType": guess_content_type(path)},
    )
    return key


def update_audio_urls(conn, mapping: dict[str, str]) -> int:
    """filename -> public_url. audio_url 이 파일명인 행만 갱신."""
    updated = 0
    with conn.cursor() as cur:
        for filename, public_url in mapping.items():
            cur.execute(
                """
                UPDATE gugak_tracks
                SET audio_url = %s
                WHERE audio_url = %s
                   OR audio_url LIKE %s
                """,
                (public_url, filename, f"%/{filename}"),
            )
            updated += cur.rowcount
    conn.commit()
    return updated


def run(
    *,
    data_root: Path,
    dry_run: bool,
    limit: int | None,
    skip_existing: bool,
    update_db: bool,
    force: bool,
) -> None:
    cfg = secretmanager.get_r2_storage_config()
    if update_db and not cfg.public_base_url:
        raise SystemExit("--update-db 는 R2_PUBLIC_BASE_URL 이 필요합니다.")

    files = iter_tm_audio_files(data_root)
    if limit:
        files = files[:limit]
    if not files:
        print("업로드할 TM 음원 파일이 없습니다.")
        return

    print(
        f"targets: {len(files)} bucket={cfg.bucket_name} "
        f"prefix={cfg.key_prefix or '(none)'} dry_run={dry_run} "
        f"skip_existing={skip_existing} update_db={update_db}"
    )

    client = None if dry_run else create_s3_client(cfg)
    uploaded = 0
    skipped = 0
    failed = 0
    url_mapping: dict[str, str] = {}

    for idx, path in enumerate(files, start=1):
        filename = path.name
        key = cfg.object_key(filename)
        label = f"[{idx}/{len(files)}] {filename}"

        try:
            if dry_run:
                public = cfg.public_url(filename) if cfg.public_base_url else f"s3://{key}"
                print(f"[DRY] {label} <- {path}")
                print(f"      key={key} url={public}")
                uploaded += 1
                if update_db and cfg.public_base_url:
                    url_mapping[filename] = cfg.public_url(filename)
                continue

            assert client is not None
            if skip_existing and not force and object_exists(client, cfg, key):
                print(f"{label} skip (already in R2)")
                skipped += 1
                if update_db and cfg.public_base_url:
                    url_mapping[filename] = cfg.public_url(filename)
                continue

            upload_file(client, cfg, path)
            print(f"{label} uploaded -> {key}")
            uploaded += 1
            if update_db and cfg.public_base_url:
                url_mapping[filename] = cfg.public_url(filename)
        except Exception as e:
            failed += 1
            print(f"{label} FAILED: {e}", file=sys.stderr)

    print(f"done: uploaded={uploaded}, skipped={skipped}, failed={failed}")

    if update_db and url_mapping and not dry_run:
        conn = psycopg.connect(normalize_psycopg_url(load_database_url()))
        try:
            count = update_audio_urls(conn, url_mapping)
            print(f"db: audio_url updated rows={count}")
        finally:
            conn.close()
    elif update_db and dry_run:
        print(f"db: would update up to {len(url_mapping)} filenames (dry-run)")


def main() -> None:
    secretmanager.bootstrap()

    parser = argparse.ArgumentParser(description="TM 음원 → Cloudflare R2 업로드")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path(
            os.getenv(
                "AUDIO_FILES_HOST_PATH",
                r"C:/Users/hi/Desktop/국악음원_sample/test/원천데이터",
            )
        ),
        help="TM 데이터 루트 또는 원천데이터 폴더",
    )
    parser.add_argument("--dry-run", action="store_true", help="업로드/DB 갱신 없이 목록만")
    parser.add_argument("--limit", type=int, default=0, help="처리 파일 수 제한 (0=전체)")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="R2에 이미 있으면 업로드 생략 (기본: 덮어쓰기)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="--skip-existing 여도 R2에 있어도 다시 업로드",
    )
    parser.add_argument(
        "--update-db",
        action="store_true",
        help="업로드 후 gugak_tracks.audio_url 을 R2 공개 URL로 갱신",
    )
    args = parser.parse_args()

    run(
        data_root=args.data_root,
        dry_run=args.dry_run,
        limit=args.limit or None,
        skip_existing=args.skip_existing,
        update_db=args.update_db,
        force=args.force,
    )


if __name__ == "__main__":
    main()
