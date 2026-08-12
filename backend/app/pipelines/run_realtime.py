from pathlib import Path
from typing import Any

from app.core.paths import LATEST_DIR, RUNS_DIR, ensure_project_dirs, utc_now_compact, write_json
from app.pipelines._common import publish_latest_artifacts
from app.rainfall.ecmwf_ifs import fetch_ecmwf_ifs_rainfall
from app.risk.hypercube import calculate_risk_lhs as calculate_risk
from app.visualization.leaflet_overlay import prepare_leaflet_outputs
from app.visualization.render_preview import render_png


def run_realtime_pipeline(
    region_id: str = "nha_trang",
    forecast_hour: int = 6,
) -> dict[str, Any]:
    """
    Realtime hiện được hiểu là bản đồ nguy cơ gần hiện tại dựa trên forecast hour ngắn, mặc định +6h.
    """
    ensure_project_dirs()

    run_id = utc_now_compact()
    output_dir = RUNS_DIR / "realtime" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    rainfall = fetch_ecmwf_ifs_rainfall(
        forecast_hour=forecast_hour,
        region_id=region_id,
        reducer="max",
        save_history=True,
    )

    risk = calculate_risk(
        rain_intensity=rainfall["intensity"],
        duration=rainfall["duration"],
        output_dir=output_dir,
        output_prefix="risk",
        region_id=region_id,
    )

    web_result = prepare_leaflet_outputs(
        input_model_tif=risk["output_tif"],
        output_dir=output_dir,
        output_prefix="risk",
    )

    preview_result = render_png(
        risk["output_tif"],
        output_png=output_dir / "risk_preview.png",
        title=f"Realtime Landslide Hazard Map - ECMWF +{forecast_hour}h",
    )

    result = {
        "status": "success",
        "mode": "realtime",
        "run_id": run_id,
        "region_id": region_id,
        "event": rainfall["event"],
        "rainfall": rainfall,
        "risk": risk,
        "web": web_result,
        "preview": preview_result,
        "map": preview_result,
        "result_json": str(output_dir / "result.json"),
    }

    write_json(output_dir / "result.json", result)
    return publish_latest_artifacts(
        result=result,
        latest_json=LATEST_DIR / "realtime.json",
        static_prefix="latest_realtime",
    )


if __name__ == "__main__":
    import json
    print(json.dumps(run_realtime_pipeline(), indent=2, ensure_ascii=False))
