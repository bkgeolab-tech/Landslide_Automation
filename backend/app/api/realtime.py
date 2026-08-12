from fastapi import APIRouter, Query

from app.api._helpers import file_or_redirect, json_or_404
from app.core.paths import LATEST_DIR, OUTPUT_STATIC_DIR
from app.pipelines.run_realtime import run_realtime_pipeline

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


@router.post("/run")
def run_realtime(
    forecast_hour: int = Query(6, ge=1, le=360),
    region_id: str = "nha_trang",
):
    return run_realtime_pipeline(region_id=region_id, forecast_hour=forecast_hour)


@router.get("/latest")
def latest_realtime():
    return json_or_404(
        LATEST_DIR / "realtime.json",
        "Chưa có realtime result. Hãy gọi POST /api/realtime/run trước."
    )


@router.get("/overlay/png")
def realtime_overlay_png():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_realtime_overlay.png",
        media_type="image/png",
        filename="latest_realtime_overlay.png",
    )


@router.get("/overlay/meta")
def realtime_overlay_meta():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_realtime_overlay.json",
        media_type="application/json",
        filename="latest_realtime_overlay.json",
    )


@router.get("/tif/model")
def realtime_model_tif():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_realtime_model.tif",
        media_type="image/tiff",
        filename="latest_realtime_model.tif",
    )


@router.get("/tif/web")
def realtime_web_tif():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_realtime_web.tif",
        media_type="image/tiff",
        filename="latest_realtime_web.tif",
    )


@router.get("/preview/png")
def realtime_preview_png():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_realtime_preview.png",
        media_type="image/png",
        filename="latest_realtime_preview.png",
    )
