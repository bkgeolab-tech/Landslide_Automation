from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.paths import OUTPUT_STATIC_DIR

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/static/{filename:path}")
def get_static_output(filename: str):
    """
    Endpoint phụ để tải file trong Output/static.
    Các endpoint realtime/forecast/validation nên được ưu tiên dùng trước.
    """
    base = OUTPUT_STATIC_DIR.resolve()
    requested = (OUTPUT_STATIC_DIR / filename).resolve()

    if not str(requested).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Đường dẫn không hợp lệ.")

    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="File không tồn tại.")

    return FileResponse(requested)
