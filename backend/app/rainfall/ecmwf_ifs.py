import csv
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import ee
from google.oauth2.service_account import Credentials

from app.core.config import get_ecmwf_settings, get_roi
from app.core.paths import GEE_KEY_PATH, RAIN_HISTORY


def initialize_gee() -> None:
    credentials = Credentials.from_service_account_file(
        GEE_KEY_PATH,
        scopes=["https://www.googleapis.com/auth/earthengine"]
    )
    ee.Initialize(credentials)


def unix_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def to_ee_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def append_rain_history(result: dict[str, Any]) -> None:
    RAIN_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    file_exists = RAIN_HISTORY.exists()

    fieldnames = [
        "created_at_utc",
        "source",
        "scenario",
        "collection",
        "band",
        "creation_time",
        "forecast_time",
        "forecast_hours",
        "accumulated_rainfall",
        "duration",
        "intensity",
        "n_images",
        "roi"
    ]

    with open(RAIN_HISTORY, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "created_at_utc": result.get("created_at_utc"),
            "source": result.get("source"),
            "scenario": result.get("scenario"),
            "collection": result.get("collection"),
            "band": result.get("band"),
            "creation_time": result.get("creation_time"),
            "forecast_time": result.get("forecast_time"),
            "forecast_hours": result.get("forecast_hours"),
            "accumulated_rainfall": result.get("accumulated_rainfall"),
            "duration": result.get("duration"),
            "intensity": result.get("intensity"),
            "n_images": result.get("n_images"),
            "roi": json.dumps(result.get("roi"), ensure_ascii=False)
        })


def fetch_ecmwf_ifs_rainfall(
    forecast_hour: int | None = None,
    region_id: str = "nha_trang",
    reducer: str = "max",
    save_history: bool = True,
) -> dict[str, Any]:
    """
    Lấy mưa dự báo ECMWF NRT IFS trên Google Earth Engine.

    Quy ước hiện tại:
    - total_precipitation_sfc là mưa tích lũy từ forecast hour 0 đến forecast_hour.
    - Giá trị từ GEE là mét, đổi sang mm.
    - reducer='max' dùng kịch bản bất lợi nhất trong ROI.
    - duration = forecast_hour, intensity = accumulated_rainfall / duration.
    """
    settings = get_ecmwf_settings()
    forecast_hour = int(forecast_hour or settings["default_forecast_hour"])

    initialize_gee()

    roi_coords = get_roi(region_id)
    roi = ee.Geometry.Rectangle(roi_coords)

    now = datetime.now(timezone.utc)
    search_start = now - timedelta(days=int(settings["lookback_days"]))

    collection = settings["collection"]
    band = settings["precip_band"]

    base_collection = (
        ee.ImageCollection(collection)
        .filter(ee.Filter.gte("creation_time", unix_ms(search_start)))
        .filter(ee.Filter.lte("creation_time", unix_ms(now)))
        .filter(ee.Filter.eq("forecast_hours", forecast_hour))
        .select(band)
    )

    n_available = int(base_collection.size().getInfo())
    if n_available == 0:
        raise RuntimeError(
            "Không tìm thấy dữ liệu ECMWF NRT IFS trong khoảng tìm kiếm. "
            "Hãy kiểm tra forecast_hours hoặc tăng ECMWF_LOOKBACK_DAYS trong .env."
        )

    latest_creation_time = base_collection.aggregate_max("creation_time").getInfo()
    latest_collection = base_collection.filter(ee.Filter.eq("creation_time", latest_creation_time))
    n_images = int(latest_collection.size().getInfo())

    rain_img_m = ee.Image(latest_collection.first()).clip(roi)
    image_info = rain_img_m.toDictionary([
        "creation_time",
        "forecast_time",
        "forecast_hours",
        "model",
        "stream"
    ]).getInfo()

    if reducer == "mean":
        ee_reducer = ee.Reducer.mean()
        scenario = "mean_roi"
    else:
        ee_reducer = ee.Reducer.max()
        scenario = "worst_case_max_roi"

    stats = rain_img_m.reduceRegion(
        reducer=ee_reducer,
        geometry=roi,
        scale=int(settings["scale"]),
        maxPixels=1e9,
        bestEffort=True
    )

    try:
        accumulated_rain_m = stats.get(band).getInfo()
        if accumulated_rain_m is None:
            accumulated_rain_m = 0.0
    except Exception:
        accumulated_rain_m = 0.0

    accumulated_rainfall_mm = float(accumulated_rain_m) * 1000.0
    duration = int(forecast_hour)
    intensity = accumulated_rainfall_mm / duration if duration > 0 else 0.0

    creation_time_ms = image_info.get("creation_time")
    forecast_time_ms = image_info.get("forecast_time")

    creation_time_iso = (
        datetime.fromtimestamp(creation_time_ms / 1000, tz=timezone.utc).isoformat()
        if creation_time_ms is not None else None
    )
    forecast_time_iso = (
        datetime.fromtimestamp(forecast_time_ms / 1000, tz=timezone.utc).isoformat()
        if forecast_time_ms is not None else None
    )

    result: dict[str, Any] = {
        "status": "success",
        "event": f"ECMWF NRT IFS rainfall forecast +{forecast_hour}h",
        "created_at_utc": to_ee_time(now),
        "creation_time": creation_time_iso,
        "forecast_time": forecast_time_iso,
        "forecast_hours": forecast_hour,
        "accumulated_rainfall": float(accumulated_rainfall_mm),
        "duration": duration,
        "intensity": float(intensity),
        "n_images": n_images,
        "roi": roi_coords,
        "scenario": scenario,
        "source": "ECMWF NRT IFS",
        "collection": collection,
        "band": band,
        "model": image_info.get("model"),
        "stream": image_info.get("stream"),
        "unit_note": (
            "ECMWF total_precipitation_sfc is cumulative precipitation since forecast hour 0; "
            "GEE unit is meter; accumulated_rainfall is converted to mm."
        )
    }

    if save_history:
        append_rain_history(result)

    return result
