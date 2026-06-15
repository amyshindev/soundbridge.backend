"""API 키 및 외부 SDK 클라이언트 중앙 관리 (Gemini 등)."""

from __future__ import annotations

from pathlib import Path

import google.generativeai as genai

from soundbridge.infrastructure.settings import settings


class Keymaker:
    """환경 변수에서 시크릿을 읽고 SDK 클라이언트를 구성."""

    def __init__(self) -> None:
        self._gemini_key: str = ""
        self._gemini_model: genai.GenerativeModel | None = None

    def bootstrap(self, *, env_file: Path | None = None) -> None:
        """`.env` 로드 후 클라이언트 초기화. 여러 번 호출해도 안전."""
        if env_file is not None and env_file.is_file():
            from dotenv import load_dotenv

            load_dotenv(env_file)
        self.refresh()

    def refresh(self) -> None:
        """환경 변수를 다시 읽고 클라이언트를 재구성."""
        self._gemini_key = settings.gemini_api_key.strip()
        self._gemini_model = None
        if self._gemini_key:
            genai.configure(api_key=self._gemini_key)
            self._gemini_model = genai.GenerativeModel(settings.gemini_model)

    def has_gemini(self) -> bool:
        return bool(self._gemini_key)

    def get_gemini_model(self) -> genai.GenerativeModel | None:
        return self._gemini_model

    @property
    def gemini_embedding_model(self) -> str:
        return settings.gemini_embedding_model


keymaker = Keymaker()

__all__ = ["Keymaker", "keymaker"]
