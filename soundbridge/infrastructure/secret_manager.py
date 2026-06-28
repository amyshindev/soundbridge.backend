"""민감 정보(.env) 로드 및 API 키·외부 서비스 설정 조회 SSoT."""

from __future__ import annotations

import os
from pathlib import Path

from soundbridge.app.dtos.r2_storage_dto import R2StorageConfig

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class SecretManager:

    def __init__(self) -> None:
        self._bootstrapped = False
        self._exaone_api_key = ""
        self._cohere_api_key = ""
        self._r2_access_key_id = ""
        self._r2_secret_access_key = ""
        self._r2_endpoint_url = ""
        self._r2_bucket_name = ""
        self._r2_public_base_url = ""
        self._r2_key_prefix = ""

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
        self._cohere_api_key = os.getenv("COHERE_API_KEY", "").strip()
        self._r2_access_key_id = os.getenv("R2_ACCESS_KEY_ID", "").strip()
        self._r2_secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
        self._r2_endpoint_url = os.getenv("R2_ENDPOINT_URL", "").strip()
        self._r2_bucket_name = os.getenv("R2_BUCKET_NAME", "").strip()
        self._r2_public_base_url = os.getenv("R2_PUBLIC_BASE_URL", "").strip()
        self._r2_key_prefix = os.getenv("R2_KEY_PREFIX", "").strip()

    def get_exaone_api_key(self) -> str:
        self._ensure_bootstrapped()
        return self._exaone_api_key

    def get_cohere_api_key(self) -> str:
        self._ensure_bootstrapped()
        return self._cohere_api_key

    def get_r2_storage_config(self, *, require_credentials: bool = True) -> R2StorageConfig:
        self._ensure_bootstrapped()
        if require_credentials:
            missing = [
                name
                for name, value in (
                    ("R2_ACCESS_KEY_ID", self._r2_access_key_id),
                    ("R2_SECRET_ACCESS_KEY", self._r2_secret_access_key),
                    ("R2_ENDPOINT_URL", self._r2_endpoint_url),
                    ("R2_BUCKET_NAME", self._r2_bucket_name),
                )
                if not value
            ]
            if missing:
                raise RuntimeError(f"R2 설정이 없습니다: {', '.join(missing)}")

        return R2StorageConfig(
            access_key_id=self._r2_access_key_id,
            secret_access_key=self._r2_secret_access_key,
            endpoint_url=self._r2_endpoint_url,
            bucket_name=self._r2_bucket_name,
            public_base_url=self._r2_public_base_url,
            key_prefix=self._r2_key_prefix,
        )


secretmanager = SecretManager()

__all__ = ["SecretManager", "secretmanager"]
