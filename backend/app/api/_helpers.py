from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse


def json_or_404(path: Path, message: str):
    if not path.exists():
        raise HTTPException(status_code=404, detail=message)
    from app.core.paths import read_json
    return read_json(path)


def file_or_404(path: Path, media_type: str | None = None, filename: str | None = None):
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File chưa tồn tại: {path.name}. Hãy chạy pipeline trước.")
    return FileResponse(path, media_type=media_type, filename=filename)


def file_or_redirect(path: Path, media_type: str | None = None, filename: str | None = None):
    from app.core.s3 import is_s3_enabled, get_public_url
    
    if is_s3_enabled():
        if filename:
            url = get_public_url(filename)
            return RedirectResponse(url=url, status_code=307)
            
    return file_or_404(path, media_type, filename)
