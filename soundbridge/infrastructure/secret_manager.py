"""환경 변수 부트스트랩 (선택적 .env 로드)."""

from __future__ import annotations

from pathlib import Path


class Keymaker:
    """앱 시작 시 .env 파일을 한 번 더 로드할 때 사용."""

    def bootstrap(self, *, env_file: Path | None = None) -> None:
        if env_file is not None and env_file.is_file():
            from dotenv import load_dotenv

            load_dotenv(env_file)


keymaker = Keymaker()

__all__ = ["Keymaker", "keymaker"]
