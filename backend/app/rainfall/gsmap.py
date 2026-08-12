from typing import Any

import ee
from google.oauth2.service_account import Credentials

from app.core.config import get_roi, load_region_config
from app.core.paths import GEE_KEY_PATH


def initialize_gee() -> None:
    credentials = Credentials.from_service_account_file(
        GEE_KEY_PATH,
        scopes=["https://www.googleapis.com/auth/earthengine"]
    )
    ee.Initialize(credentials)


def fetch_gsmap_2018_event(region_id: str = "nha_trang") -> dict[str, Any]:
    """Lấy mưa GSMaP cho sự kiện validation 2018."""
    initialize_gee()

    cfg = load_region_config(region_id)
    validation_cfg = cfg.get("validation_2018", {})

    event_name = validation_cfg.get("event_name", "Nha Trang rainfall event 2018")
    start_time = validation_cfg.get("start_time", "2018-11-17T03:00:00")
    end_time = validation_cfg.get("end_time", "2018-11-18T07:00:00")

    roi = ee.Geometry.Rectangle(get_roi(region_id))

    dataset = (
        ee.ImageCollection("JAXA/GPM_L3/GSMaP/v6/operational")
        .filterDate(start_time, end_time)
        .select("hourlyPrecipRate")
    )

    rain_img = dataset.sum().clip(roi)
    n_images = int(dataset.size().getInfo())
    duration = n_images

    stats = rain_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=11000,
        maxPixels=1e9,
        bestEffort=True
    )

    try:
        accumulated_rainfall = stats.get("hourlyPrecipRate").getInfo()
        if accumulated_rainfall is None:
            accumulated_rainfall = 0.0
    except Exception:
        accumulated_rainfall = 0.0

    intensity = float(accumulated_rainfall) / duration if duration > 0 else 0.0

    return {
        "status": "success",
        "event": event_name,
        "start_time": start_time,
        "end_time": end_time,
        "accumulated_rainfall": float(accumulated_rainfall),
        "duration": int(duration),
        "intensity": float(intensity),
        "n_images": int(n_images),
        "source": "GSMaP",
        "collection": "JAXA/GPM_L3/GSMaP/v6/operational",
        "band": "hourlyPrecipRate"
    }
