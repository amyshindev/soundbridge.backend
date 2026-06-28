"""민감 정보(.env) 로드 및 API 키 조회 SSoT."""

from __future__ import annotations

import os
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class SecretManager:

    def __init__(self) -> None:
        self._bootstrapped = False
        self._exaone_api_key = ""

    def bootstrap(self, *, env_file: Path | None = None) -> None:
        from dotenv import load_dotenv

        if env_file is not None and env_file.is_file():
            load_dotenv(env_file)
        else:
            for path in (_BACKEND_DIR / ".env", _BACKEND_DIR.parent / ".env"):
                if path.is_file():
                    load_dotenv(path)

        self._reload_secrets()
        self._bootstrapped = True

    def _ensure_bootstrapped(self) -> None:
        if not self._bootstrapped:
            self.bootstrap()

    def _reload_secrets(self) -> None:
        self._exaone_api_key = os.getenv("EXAONE_API_KEY", "").strip()

    def get_exaone_api_key(self) -> str:
        self._ensure_bootstrapped()
        return self._exaone_api_key


secretmanager = SecretManager()

__all__ = ["SecretManager", "secretmanager"]
