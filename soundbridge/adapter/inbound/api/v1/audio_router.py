# 레이어: Inbound — 국악 원천데이터 음원 스트리밍
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from soundbridge.infrastructure.audio_file_resolver import resolve_audio_path, validate_audio_filename
from soundbridge.infrastructure.settings import settings

router = APIRouter()

_MEDIA_TYPES = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
}


@router.get("/{filename}")
async def get_audio_file(filename: str) -> FileResponse:
    if not settings.audio_files_root:
        raise HTTPException(status_code=503, detail="음원 파일 경로가 설정되지 않았습니다")

    try:
        validate_audio_filename(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="잘못된 음원 파일명입니다") from e

    root = Path(settings.audio_files_root)
    path = resolve_audio_path(root, filename)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="음원 파일을 찾을 수 없습니다")

    media_type = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        headers={"Accept-Ranges": "bytes"},
    )
