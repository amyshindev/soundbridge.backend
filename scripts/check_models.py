"""임베딩 서버 모델 목록 확인 (nomic-embed-text 등)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

base = os.getenv("EMBED_BASE_URL", "http://localhost:11434").rstrip("/")
url = f"{base}/api/tags"

try:
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode())
except urllib.error.URLError as e:
    raise SystemExit(f"임베딩 서버 연결 실패 ({base}): {e}") from e

for model in data.get("models", []):
    print(model.get("name"), model.get("size"))
