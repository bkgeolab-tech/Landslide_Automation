from fastapi import APIRouter

from app.api._helpers import file_or_redirect, json_or_404
from app.core.paths import LATEST_DIR, OUTPUT_STATIC_DIR
from app.pipelines.run_validation_2018 import run_validation_2018_pipeline

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.post("/2018/run")
def run_validation_2018(region_id: str = "nha_trang"):
    return run_validation_2018_pipeline(region_id=region_id)


@router.get("/2018/latest")
def latest_validation_2018():
    return json_or_404(
        LATEST_DIR / "validation_2018.json",
        "Chưa có validation 2018 result. Hãy gọi POST /api/validation/2018/run trước."
    )


@router.get("/2018/roc")
def validation_2018_roc():
    latest = json_or_404(
        LATEST_DIR / "validation_2018.json",
        "Chưa có validation 2018 result."
    )
    return latest.get("validation_metrics", {
        "roc_available": False,
        "message": "Chưa có thông tin ROC."
    })


@router.get("/2018/roc/png")
def validation_2018_roc_png():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_validation_2018_roc.png",
        media_type="image/png",
        filename="latest_validation_2018_roc.png",
    )


@router.get("/2018/points")
def validation_2018_points_geojson():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_validation_2018_points.geojson",
        media_type="application/geo+json",
        filename="latest_validation_2018_points.geojson",
    )


@router.get("/2018/points/csv")
def validation_2018_points_csv():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_validation_2018_points.csv",
        media_type="text/csv",
        filename="latest_validation_2018_points.csv",
    )


@router.get("/2018/overlay/png")
def validation_overlay_png():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_validation_2018_overlay.png",
        media_type="image/png",
        filename="latest_validation_2018_overlay.png",
    )


@router.get("/2018/overlay/meta")
def validation_overlay_meta():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_validation_2018_overlay.json",
        media_type="application/json",
        filename="latest_validation_2018_overlay.json",
    )


@router.get("/2018/tif/model")
def validation_model_tif():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_validation_2018_model.tif",
        media_type="image/tiff",
        filename="latest_validation_2018_model.tif",
    )


@router.get("/2018/tif/web")
def validation_web_tif():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_validation_2018_web.tif",
        media_type="image/tiff",
        filename="latest_validation_2018_web.tif",
    )


@router.get("/2018/preview/png")
def validation_preview_png():
    return file_or_redirect(
        OUTPUT_STATIC_DIR / "latest_validation_2018_preview.png",
        media_type="image/png",
        filename="latest_validation_2018_preview.png",
    )
