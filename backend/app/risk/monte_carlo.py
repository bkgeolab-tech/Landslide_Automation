from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio

from app.core.config import get_monte_carlo_settings
from app.core.paths import INPUT_DIR
from app.terrain.prepare_terrain import build_terrain_data

SOIL_PROPERTIES = INPUT_DIR / "soil_properties.csv"


def _read_soil_properties() -> pd.DataFrame:
    if not SOIL_PROPERTIES.exists():
        raise FileNotFoundError(f"Không tìm thấy soil_properties.csv: {SOIL_PROPERTIES}")

    soil_props = pd.read_csv(SOIL_PROPERTIES)
    required = {"Properties", "Value", "COV"}
    missing = required - set(soil_props.columns)
    if missing:
        raise ValueError(f"soil_properties.csv thiếu cột: {sorted(missing)}")
    return soil_props


def _make_property_sampler(soil_props: pd.DataFrame, rng: np.random.Generator):
    def random_property(name: str) -> float:
        row = soil_props[soil_props["Properties"] == name]
        if row.empty:
            raise ValueError(f"soil_properties.csv không có property: {name}")

        mean = float(row["Value"].values[0])
        cov = float(row["COV"].values[0])
        std_dev = abs(mean * cov)
        return float(rng.normal(mean, std_dev))

    return random_property


def summarize_risk_array(result_2d: np.ndarray, transform, nodata: float = -9999.0) -> dict[str, Any]:
    valid = np.isfinite(result_2d) & (result_2d != nodata)
    values = result_2d[valid]

    if values.size == 0:
        return {
            "valid_pixels": 0,
            "max_p_failure": None,
            "mean_p_failure": None,
            "area_km2": 0.0,
            "area_p_failure_gt_0_3_km2": 0.0,
            "area_p_failure_gt_0_5_km2": 0.0,
            "area_p_failure_gt_0_7_km2": 0.0,
            "percent_p_failure_gt_0_3": 0.0,
            "percent_p_failure_gt_0_5": 0.0,
            "percent_p_failure_gt_0_7": 0.0,
        }

    pixel_area_m2 = abs(float(transform.a) * float(transform.e))
    total_area_km2 = values.size * pixel_area_m2 / 1_000_000.0

    def area_gt(threshold: float) -> float:
        return float(np.sum(values > threshold) * pixel_area_m2 / 1_000_000.0)

    a03 = area_gt(0.3)
    a05 = area_gt(0.5)
    a07 = area_gt(0.7)

    return {
        "valid_pixels": int(values.size),
        "max_p_failure": float(np.nanmax(values)),
        "mean_p_failure": float(np.nanmean(values)),
        "area_km2": float(total_area_km2),
        "area_p_failure_gt_0_3_km2": a03,
        "area_p_failure_gt_0_5_km2": a05,
        "area_p_failure_gt_0_7_km2": a07,
        "percent_p_failure_gt_0_3": float(100 * a03 / total_area_km2) if total_area_km2 > 0 else 0.0,
        "percent_p_failure_gt_0_5": float(100 * a05 / total_area_km2) if total_area_km2 > 0 else 0.0,
        "percent_p_failure_gt_0_7": float(100 * a07 / total_area_km2) if total_area_km2 > 0 else 0.0,
    }


def summarize_risk_tif(input_tif: str | Path) -> dict[str, Any]:
    with rasterio.open(input_tif) as src:
        data = src.read(1).astype("float32")
        nodata = src.nodata if src.nodata is not None else -9999.0
        return summarize_risk_array(data, src.transform, nodata=nodata)


def calculate_risk(
    rain_intensity: float,
    duration: float,
    output_dir: str | Path,
    output_prefix: str = "risk",
    region_id: str = "nha_trang",
    num_iterations: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Tính P_failure bằng Monte Carlo và ghi GeoTIFF vào output_dir."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = get_monte_carlo_settings()
    num_iterations = int(num_iterations or settings["iterations"])
    seed = settings["seed"] if seed is None else seed
    rng = np.random.default_rng(seed)

    terrain_status = build_terrain_data(force=False, region_id=region_id)
    dem_path = Path(terrain_status["dem_path"])
    terrain_csv = Path(terrain_status["terrain_csv"])

    with rasterio.open(dem_path) as src:
        template_meta = src.meta.copy()
        height, width = src.shape
        transform = src.transform

    terrain_data = pd.read_csv(terrain_csv)
    soil_props = _read_soil_properties()
    random_property = _make_property_sampler(soil_props, rng)

    terrain_data["Slope"] = terrain_data["Slope"].replace(-9999, np.nan)
    slope_rad = np.radians(terrain_data["Slope"].values)

    rt = float(rain_intensity)
    t = float(duration)

    num_pixels = terrain_data.shape[0]
    monte_carlo_fs = np.zeros((num_pixels, num_iterations), dtype="float32")

    curvature = terrain_data["Curvature"].values.astype("float64")
    soil_depth = terrain_data["Soil_depth"].values.astype("float64")

    gamma_water = 9.81
    sin_slope = np.sin(slope_rad)
    cos_slope = np.cos(slope_rad)
    safe_slope = sin_slope * cos_slope

    for i in range(num_iterations):
        porosity = max(random_property("Porosity"), 0.01)
        ks = max(random_property("Hydraulic conductivity"), 1e-6)
        gamma = max(random_property("Unit weight"), 1e-6)
        phi = random_property("Friction Angle")
        cohesion = max(random_property("Cohesion"), 0.0)

        tan_phi = np.tan(np.radians(phi))
        vs = (ks * sin_slope * cos_slope) / porosity

        hw = (1.0 / porosity) * (rt * t + t * (curvature / 2.0) * vs * rt * t)
        hw = np.clip(hw, 0, soil_depth)

        numerator = cohesion + ((gamma * soil_depth - gamma_water * hw) * (cos_slope ** 2) * tan_phi)
        denominator = gamma * soil_depth * safe_slope

        with np.errstate(divide="ignore", invalid="ignore"):
            fs = numerator / denominator
            fs[(~np.isfinite(fs)) | (denominator <= 0)] = 1.5

        monte_carlo_fs[:, i] = fs.astype("float32")

    p_failure = np.mean(monte_carlo_fs <= 1.0, axis=1)

    result_2d = np.full((height, width), -9999.0, dtype=np.float32)
    rows = terrain_data["Row"].values.astype(int)
    cols = terrain_data["Col"].values.astype(int)

    valid = (
        (rows >= 0) & (rows < height) &
        (cols >= 0) & (cols < width) &
        np.isfinite(p_failure)
    )
    result_2d[rows[valid], cols[valid]] = p_failure[valid].astype("float32")

    output_tif = output_dir / f"{output_prefix}_model.tif"
    meta = template_meta.copy()
    meta.update({
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": template_meta["crs"],
        "transform": template_meta["transform"],
        "nodata": -9999.0,
        "compress": "lzw"
    })

    with rasterio.open(output_tif, "w", **meta) as dst:
        dst.write(result_2d, 1)

    summary = summarize_risk_array(result_2d, transform, nodata=-9999.0)

    return {
        "status": "success",
        "output_tif": str(output_tif),
        "rain_intensity": rt,
        "duration": t,
        "num_iterations": num_iterations,
        "seed": seed,
        "summary": summary,
        "terrain_status": terrain_status,
    }
