from typing import Any

from app.core.paths import LATEST_DIR, RUNS_DIR, ensure_project_dirs, utc_now_compact, write_json
from app.pipelines._common import publish_latest_artifacts
from app.rainfall.gsmap import fetch_gsmap_2018_event
from app.risk.hypercube import calculate_risk_lhs as calculate_risk
from app.validation.roc_tools import build_validation_roc_outputs
from app.visualization.leaflet_overlay import prepare_leaflet_outputs
from app.visualization.render_preview import render_png


def run_validation_2018_pipeline(region_id: str = "nha_trang") -> dict[str, Any]:
    ensure_project_dirs()

    run_id = utc_now_compact()
    output_dir = RUNS_DIR / "validation" / "2018" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    rainfall = fetch_gsmap_2018_event(region_id=region_id)

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
        title="Validation Landslide Hazard Map - Nha Trang 2018",
    )

    validation_metrics = build_validation_roc_outputs(
        web_tif=web_result["web_tif"],
        output_dir=output_dir,
    )

    result = {
        "status": "success",
        "mode": "validation_2018",
        "run_id": run_id,
        "region_id": region_id,
        "event": rainfall["event"],
        "rainfall": rainfall,
        "risk": risk,
        "web": web_result,
        "preview": preview_result,
        "map": preview_result,
        "validation_metrics": validation_metrics,
        "result_json": str(output_dir / "result.json"),
    }

    write_json(output_dir / "result.json", result)
    return publish_latest_artifacts(
        result=result,
        latest_json=LATEST_DIR / "validation_2018.json",
        static_prefix="latest_validation_2018",
    )


if __name__ == "__main__":
    import json
    print(json.dumps(run_validation_2018_pipeline(), indent=2, ensure_ascii=False))
