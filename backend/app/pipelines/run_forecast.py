from typing import Any

from app.core.paths import RUNS_DIR, ensure_project_dirs, latest_forecast_json_path, static_forecast_prefix, utc_now_compact, write_json
from app.pipelines._common import publish_latest_artifacts
from app.rainfall.ecmwf_ifs import fetch_ecmwf_ifs_rainfall
from app.risk.hypercube import calculate_risk_lhs as calculate_risk
from app.visualization.leaflet_overlay import prepare_leaflet_outputs
from app.visualization.render_preview import render_png


def run_forecast_pipeline(
    hours: int = 24,
    region_id: str = "nha_trang",
) -> dict[str, Any]:
    ensure_project_dirs()

    hours = int(hours)
    run_id = utc_now_compact()
    output_dir = RUNS_DIR / "forecast" / f"h{hours:03d}" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    rainfall = fetch_ecmwf_ifs_rainfall(
        forecast_hour=hours,
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
        title=f"Forecast Landslide Hazard Map - ECMWF +{hours}h",
    )

    result = {
        "status": "success",
        "mode": "forecast",
        "forecast_hours": hours,
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
        latest_json=latest_forecast_json_path(hours),
        static_prefix=static_forecast_prefix(hours),
    )


def run_multiple_forecasts(
    hours_list: list[int] | tuple[int, ...] = (6, 12, 24),
    region_id: str = "nha_trang",
) -> dict[str, Any]:
    results = []
    for h in hours_list:
        results.append(run_forecast_pipeline(hours=int(h), region_id=region_id))
    return {
        "status": "success",
        "mode": "forecast_batch",
        "hours_list": [int(h) for h in hours_list],
        "results": results,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_multiple_forecasts(), indent=2, ensure_ascii=False))
