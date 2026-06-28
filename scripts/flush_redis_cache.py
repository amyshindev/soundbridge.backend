"""SoundBridge Redis 캐시 삭제 (sb:* 키).

Usage:
  cd backend
  python scripts/flush_redis_cache.py
  python scripts/flush_redis_cache.py --all   # sb:* 외 전체 DB flush
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    import redis
except ModuleNotFoundError as e:
    raise SystemExit("redis 패키지가 필요합니다: pip install -r requirements.txt") from e

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


def load_env_files() -> None:
    for path in (BACKEND_DIR / ".env", ROOT_DIR / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    load_env_files()
    parser = argparse.ArgumentParser(description="SoundBridge Redis 캐시 삭제")
    parser.add_argument(
        "--all",
        action="store_true",
        help="sb:* 만이 아니라 현재 Redis DB 전체 flush",
    )
    args = parser.parse_args()

    url = os.getenv("REDIS_URL", "redis://localhost:6379").strip()
    client = redis.from_url(url, decode_responses=True)

    try:
        client.ping()
    except redis.ConnectionError as e:
        raise SystemExit(
            f"Redis 연결 실패 ({url}).\n"
            "  로컬: docker compose up redis -d 또는 Redis 서버 실행 후 재시도"
        ) from e

    if args.all:
        client.flushdb()
        print(f"Flushed entire Redis DB at {url}")
        return

    keys = list(client.scan_iter("sb:*"))
    if keys:
        client.delete(*keys)
    print(f"Deleted {len(keys)} keys matching sb:* from {url}")


if __name__ == "__main__":
    main()
