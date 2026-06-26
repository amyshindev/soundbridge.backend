"""Ollama 모델 목록 확인 (nomic-embed-text, exaone 등)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from dotenv import load_dotenv

load_dotenv()

base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
url = f"{base}/api/tags"

try:
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode())
except urllib.error.URLError as e:
    raise SystemExit(f"Ollama 연결 실패 ({base}): {e}") from e

for model in data.get("models", []):
    print(model.get("name"), model.get("size"))
