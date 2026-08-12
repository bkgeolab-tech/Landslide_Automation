from pathlib import Path
from typing import Any

from app.core.paths import OUTPUT_STATIC_DIR, copy_file, write_json
from app.core.s3 import is_s3_enabled, upload_file_to_s3, get_public_url


def publish_static_file(src: Path | str, filename: str) -> str:
    """Copy file to static folder, and upload to S3 if enabled."""
    dst = OUTPUT_STATIC_DIR / filename
    copy_file(src, dst)
    
    if is_s3_enabled():
        success = upload_file_to_s3(dst, filename)
        if success:
            return get_public_url(filename)
            
    return str(dst)


def publish_latest_artifacts(
    result: dict[str, Any],
    latest_json: Path,
    static_prefix: str,
) -> dict[str, Any]:
    """
    Ghi latest JSON và copy các file bản đồ sang Output/static để API/web lấy ổn định.
    Nếu S3 được bật, tự động đẩy file lên mây.
    """
    web = result.get("web", {})
    risk = result.get("risk", {})
    preview = result.get("preview", {})

    static_paths: dict[str, str] = {}

    if web.get("overlay_png"):
        static_paths["overlay_png"] = publish_static_file(web["overlay_png"], f"{static_prefix}_overlay.png")
    if web.get("overlay_meta"):
        static_paths["overlay_meta"] = publish_static_file(web["overlay_meta"], f"{static_prefix}_overlay.json")
    if web.get("web_tif"):
        static_paths["web_tif"] = publish_static_file(web["web_tif"], f"{static_prefix}_web.tif")
    if risk.get("output_tif"):
        static_paths["model_tif"] = publish_static_file(risk["output_tif"], f"{static_prefix}_model.tif")
    if preview.get("output_png"):
        static_paths["preview_png"] = publish_static_file(preview["output_png"], f"{static_prefix}_preview.png")

    validation_metrics = result.get("validation_metrics", {})
    validation_files = validation_metrics.get("files", {}) if isinstance(validation_metrics, dict) else {}

    if validation_files.get("roc_png"):
        static_paths["roc_png"] = publish_static_file(validation_files["roc_png"], f"{static_prefix}_roc.png")
    if validation_files.get("roc_json"):
        static_paths["roc_json"] = publish_static_file(validation_files["roc_json"], f"{static_prefix}_roc.json")
    if validation_files.get("sampled_points_geojson"):
        static_paths["validation_points_geojson"] = publish_static_file(validation_files["sampled_points_geojson"], f"{static_prefix}_points.geojson")
    if validation_files.get("sampled_points_csv"):
        static_paths["validation_points_csv"] = publish_static_file(validation_files["sampled_points_csv"], f"{static_prefix}_points.csv")

    result["static"] = static_paths
    write_json(latest_json, result)
    return result
