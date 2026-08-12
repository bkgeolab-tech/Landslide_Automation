import json
import os
from pathlib import Path
from typing import Any

from app.core.paths import INPUT_DIR, REGIONS_DIR, ensure_project_dirs

DEFAULT_REGION_CONFIG: dict[str, Any] = {
    "region_id": "nha_trang",
    "region_name": "Nha Trang, Vietnam",
    "roi": [109.1, 12.1, 109.3, 12.2],
    "model_crs": "EPSG:32649",
    "soil_depth": {
        "method": "elevation_linear",
        "hmax": 2.9,
        "hmin": 1.0,
        "dem_min": None,
        "dem_max": None
    },
    "validation_2018": {
        "event_name": "Nha Trang rainfall event 2018",
        "start_time": "2018-11-17T03:00:00",
        "end_time": "2018-11-18T07:00:00",
        "rain_source": "GSMaP"
    }
}


def region_config_path(region_id: str = "nha_trang") -> Path:
    return REGIONS_DIR / f"{region_id}.json"


def legacy_region_config_path() -> Path:
    return INPUT_DIR / "region_config.json"


def load_region_config(region_id: str = "nha_trang") -> dict[str, Any]:
    """
    Đọc cấu hình vùng nghiên cứu.

    Ưu tiên cấu trúc mới: Input/regions/nha_trang.json.
    Nếu chưa có nhưng còn file cũ Input/region_config.json thì dùng file cũ.
    Nếu không có gì thì tự tạo cấu hình mặc định cho Nha Trang.
    """
    ensure_project_dirs()

    new_path = region_config_path(region_id)
    old_path = legacy_region_config_path()

    if new_path.exists():
        with open(new_path, "r", encoding="utf-8") as f:
            return json.load(f)

    if old_path.exists():
        with open(old_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg.setdefault("region_id", region_id)
        cfg.setdefault("region_name", "Nha Trang, Vietnam")
        cfg.setdefault("roi", DEFAULT_REGION_CONFIG["roi"])
        cfg.setdefault("validation_2018", DEFAULT_REGION_CONFIG["validation_2018"])
        return cfg

    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_REGION_CONFIG, f, indent=2, ensure_ascii=False)

    return DEFAULT_REGION_CONFIG.copy()


def get_roi(region_id: str = "nha_trang") -> list[float]:
    env_roi = os.getenv("RAIN_ROI", "").strip()
    if env_roi:
        values = [float(x.strip()) for x in env_roi.split(",")]
        if len(values) != 4:
            raise ValueError("RAIN_ROI phải có dạng west,south,east,north")
        west, south, east, north = values
        if west >= east or south >= north:
            raise ValueError("RAIN_ROI không hợp lệ: west/east hoặc south/north bị đảo.")
        return values

    cfg = load_region_config(region_id)
    roi = cfg.get("roi", DEFAULT_REGION_CONFIG["roi"])
    if len(roi) != 4:
        raise ValueError("roi trong file cấu hình phải có 4 giá trị: west,south,east,north")
    return [float(x) for x in roi]


def get_ecmwf_settings() -> dict[str, Any]:
    return {
        "collection": os.getenv("ECMWF_COLLECTION", "ECMWF/NRT_FORECAST/IFS/OPER"),
        "precip_band": os.getenv("ECMWF_PRECIP_BAND", "total_precipitation_sfc"),
        "lookback_days": int(os.getenv("ECMWF_LOOKBACK_DAYS", "5")),
        "scale": int(os.getenv("ECMWF_SCALE", "28000")),
        "default_forecast_hour": int(os.getenv("ECMWF_FORECAST_HOUR", "6")),
    }


def get_monte_carlo_settings() -> dict[str, Any]:
    seed_text = os.getenv("MC_SEED", "").strip()
    seed = int(seed_text) if seed_text else None
    return {
        "iterations": int(os.getenv("MC_ITERATIONS", "350")),
        "seed": seed,
    }
