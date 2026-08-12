from fastapi import APIRouter, Query

from app.api._helpers import file_or_redirect, json_or_404
from app.core.paths import OUTPUT_STATIC_DIR, latest_forecast_json_path, static_forecast_prefix
from app.pipelines.run_forecast import run_forecast_pipeline, run_multiple_forecasts

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.post("/run")
def run_forecast(
    hours: int = Query(24, ge=1, le=360),
    region_id: str = "nha_trang",
):
    """API dùng chung, truyền tham số query `?hours=...`"""
    return run_forecast_pipeline(hours=hours, region_id=region_id)


@router.post("/run/6")
def run_forecast_6h(region_id: str = "nha_trang"):
    """API chạy riêng biệt cho 6 giờ"""
    return run_forecast_pipeline(hours=6, region_id=region_id)


@router.post("/run/12")
def run_forecast_12h(region_id: str = "nha_trang"):
    """API chạy riêng biệt cho 12 giờ"""
    return run_forecast_pipeline(hours=12, region_id=region_id)


@router.post("/run/24")
def run_forecast_24h(region_id: str = "nha_trang"):
    """API chạy riêng biệt cho 24 giờ"""
    return run_forecast_pipeline(hours=24, region_id=region_id)


@router.post("/run-batch")
def run_forecast_batch(
    hours: list[int] = Query(default=[6, 12, 24]),
    region_id: str = "nha_trang",
):
    return run_multiple_forecasts(hours_list=hours, region_id=region_id)


@router.get("/latest")
def latest_forecast(hours: int = Query(24, ge=1, le=360)):
    return json_or_404(
        latest_forecast_json_path(hours),
        f"Chưa có forecast +{hours}h. Hãy gọi POST /api/forecast/run?hours={hours} trước."
    )


def _prefix(hours: int) -> str:
    return static_forecast_prefix(hours)


@router.get("/overlay/png")
def forecast_overlay_png(hours: int = Query(24, ge=1, le=360)):
    prefix = _prefix(hours)
    return file_or_redirect(
        OUTPUT_STATIC_DIR / f"{prefix}_overlay.png",
        media_type="image/png",
        filename=f"{prefix}_overlay.png",
    )


@router.get("/overlay/meta")
def forecast_overlay_meta(hours: int = Query(24, ge=1, le=360)):
    prefix = _prefix(hours)
    return file_or_redirect(
        OUTPUT_STATIC_DIR / f"{prefix}_overlay.json",
        media_type="application/json",
        filename=f"{prefix}_overlay.json",
    )


@router.get("/tif/model")
def forecast_model_tif(hours: int = Query(24, ge=1, le=360)):
    prefix = _prefix(hours)
    return file_or_redirect(
        OUTPUT_STATIC_DIR / f"{prefix}_model.tif",
        media_type="image/tiff",
        filename=f"{prefix}_model.tif",
    )


@router.get("/tif/web")
def forecast_web_tif(hours: int = Query(24, ge=1, le=360)):
    prefix = _prefix(hours)
    return file_or_redirect(
        OUTPUT_STATIC_DIR / f"{prefix}_web.tif",
        media_type="image/tiff",
        filename=f"{prefix}_web.tif",
    )


@router.get("/preview/png")
def forecast_preview_png(hours: int = Query(24, ge=1, le=360)):
    prefix = _prefix(hours)
    return file_or_redirect(
        OUTPUT_STATIC_DIR / f"{prefix}_preview.png",
        media_type="image/png",
        filename=f"{prefix}_preview.png",
    )
