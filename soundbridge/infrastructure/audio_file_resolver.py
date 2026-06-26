# 레이어: Infrastructure — 원천데이터 음원 파일명 → 실제 경로 해석
from __future__ import annotations

import os
import re
from pathlib import Path

_SAFE_AUDIO_FILENAME = re.compile(
    r"^KC_TM_[A-Z0-9_]+_S\d+\.(wav|mp3)$",
    re.IGNORECASE,
)

_index: dict[str, Path] | None = None
_index_root: Path | None = None


def validate_audio_filename(filename: str) -> str:
    basename = os.path.basename(filename)
    if basename != filename or ".." in filename or not basename:
        raise ValueError("invalid audio filename")
    if not _SAFE_AUDIO_FILENAME.match(basename):
        raise ValueError("invalid audio filename")
    return basename


def build_audio_index(root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not root.is_dir():
        return index
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".wav", ".mp3"}:
            index[path.name] = path
    return index


def warm_audio_index(root: Path) -> int:
    global _index, _index_root
    resolved = root.resolve()
    _index = build_audio_index(resolved)
    _index_root = resolved
    return len(_index)


def resolve_audio_path(root: Path, filename: str) -> Path | None:
    global _index, _index_root
    basename = validate_audio_filename(filename)
    resolved_root = root.resolve()
    if _index is None or _index_root != resolved_root:
        warm_audio_index(resolved_root)
    assert _index is not None
    path = _index.get(basename)
    if path is None:
        return None
    try:
        path.resolve().relative_to(resolved_root)
    except ValueError:
        return None
    return path
