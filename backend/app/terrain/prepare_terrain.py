import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from rasterio.crs import CRS
from rasterio.warp import Resampling, calculate_default_transform, reproject

from app.core.config import load_region_config
from app.core.paths import INPUT_DIR, ensure_project_dirs

SOURCE_DEM = INPUT_DIR / "DEM.tif"
MODEL_DEM = INPUT_DIR / "DEM_model.tif"
TERRAIN_CSV = INPUT_DIR / "terrain_data.csv"
TERRAIN_META = INPUT_DIR / "terrain_meta.json"


def estimate_utm_crs(src: rasterio.DatasetReader) -> CRS:
    """Tự ước lượng UTM zone từ DEM geographic."""
    left, bottom, right, top = src.bounds
    lon_center = (left + right) / 2
    lat_center = (bottom + top) / 2
    zone = int((lon_center + 180) // 6) + 1
    epsg = 32600 + zone if lat_center >= 0 else 32700 + zone
    return CRS.from_epsg(epsg)


def ensure_metric_dem(force: bool = False, region_id: str = "nha_trang") -> Path:
    """
    Nếu DEM gốc đang ở WGS84 degree thì reproject sang DEM_model.tif hệ mét.
    Nếu DEM gốc đã projected CRS thì dùng trực tiếp DEM gốc.
    """
    ensure_project_dirs()

    if not SOURCE_DEM.exists():
        raise FileNotFoundError(f"Không tìm thấy DEM: {SOURCE_DEM}")

    config = load_region_config(region_id)

    with rasterio.open(SOURCE_DEM) as src:
        if src.crs is None:
            raise ValueError("DEM không có CRS. Cần gán CRS cho DEM trước khi tính terrain.")

        if not src.crs.is_geographic:
            return SOURCE_DEM

        model_crs = config.get("model_crs")
        dst_crs = CRS.from_string(model_crs) if model_crs else estimate_utm_crs(src)

        if MODEL_DEM.exists() and not force:
            with rasterio.open(MODEL_DEM) as model_src:
                model_is_newer = MODEL_DEM.stat().st_mtime >= SOURCE_DEM.stat().st_mtime
                same_crs = model_src.crs == dst_crs
                if model_is_newer and same_crs:
                    return MODEL_DEM

        transform, width, height = calculate_default_transform(
            src.crs,
            dst_crs,
            src.width,
            src.height,
            *src.bounds
        )

        kwargs = src.meta.copy()
        kwargs.update({
            "driver": "GTiff",
            "crs": dst_crs,
            "transform": transform,
            "width": width,
            "height": height,
            "compress": "lzw"
        })

        with rasterio.open(MODEL_DEM, "w", **kwargs) as dst:
            for band_id in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band_id),
                    destination=rasterio.band(dst, band_id),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    dst_nodata=src.nodata,
                    resampling=Resampling.bilinear
                )

    return MODEL_DEM


def compute_soil_depth_from_dem(
    dem_work: np.ndarray,
    valid_dem: np.ndarray,
    config: dict[str, Any]
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    h_i = hmax - ((DEM_i - DEMmin) / (DEMmax - DEMmin)) * (hmax - hmin)
    """
    soil_cfg = config.get("soil_depth", {})
    hmax = float(soil_cfg.get("hmax", 2.9))
    hmin = float(soil_cfg.get("hmin", 1.0))

    valid_values = dem_work[valid_dem]
    if valid_values.size == 0:
        raise ValueError("DEM không có pixel hợp lệ để tính soil depth.")

    dem_min = float(np.nanmin(valid_values)) if soil_cfg.get("dem_min") is None else float(soil_cfg["dem_min"])
    dem_max = float(np.nanmax(valid_values)) if soil_cfg.get("dem_max") is None else float(soil_cfg["dem_max"])

    if abs(dem_max - dem_min) < 1e-12:
        soil_depth = np.full_like(dem_work, (hmax + hmin) / 2, dtype="float64")
    else:
        normalized_elevation = (dem_work - dem_min) / (dem_max - dem_min)
        normalized_elevation = np.clip(normalized_elevation, 0, 1)
        soil_depth = hmax - normalized_elevation * (hmax - hmin)

    soil_depth[~valid_dem] = np.nan

    return soil_depth, {
        "method": "elevation_linear",
        "hmax": hmax,
        "hmin": hmin,
        "dem_min": dem_min,
        "dem_max": dem_max
    }


def get_terrain_signature(dem_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    dem_path = Path(dem_path)
    with rasterio.open(dem_path) as src:
        return {
            "source_dem_path": str(SOURCE_DEM.resolve()),
            "source_dem_size": SOURCE_DEM.stat().st_size,
            "source_dem_modified_time": SOURCE_DEM.stat().st_mtime,
            "model_dem_path": str(dem_path.resolve()),
            "model_dem_size": dem_path.stat().st_size,
            "model_dem_modified_time": dem_path.stat().st_mtime,
            "width": src.width,
            "height": src.height,
            "crs": str(src.crs),
            "transform": list(src.transform),
            "nodata": src.nodata,
            "region_id": config.get("region_id"),
            "model_crs": config.get("model_crs"),
            "soil_depth_config": config.get("soil_depth")
        }


def terrain_cache_is_valid(dem_path: Path, config: dict[str, Any]) -> bool:
    if not TERRAIN_CSV.exists() or not TERRAIN_META.exists():
        return False

    current_signature = get_terrain_signature(dem_path, config)
    with open(TERRAIN_META, "r", encoding="utf-8") as f:
        old_signature = json.load(f)

    comparable_old = {k: old_signature.get(k) for k in current_signature.keys()}
    return current_signature == comparable_old


def build_terrain_data(force: bool = False, region_id: str = "nha_trang") -> dict[str, Any]:
    """
    Tạo terrain_data.csv từ DEM:
    1. Đọc DEM.tif.
    2. Reproject sang CRS mét nếu DEM đang là geographic.
    3. Tính Slope, Curvature, Soil_depth.
    4. Cache terrain_data.csv bằng terrain_meta.json.
    """
    ensure_project_dirs()
    config = load_region_config(region_id)
    dem_path = ensure_metric_dem(force=force, region_id=region_id)

    if not force and terrain_cache_is_valid(dem_path, config):
        return {
            "status": "cached",
            "message": "terrain_data.csv is already valid for current DEM and config",
            "dem_path": str(dem_path),
            "terrain_csv": str(TERRAIN_CSV)
        }

    with rasterio.open(dem_path) as src:
        if src.crs is not None and src.crs.is_geographic:
            raise ValueError("DEM dùng cho mô hình vẫn đang ở geographic degree. Reproject chưa thành công.")

        dem = src.read(1).astype("float64")
        nodata = src.nodata
        transform = src.transform
        xres = abs(transform.a)
        yres = abs(transform.e)

    valid_dem = np.isfinite(dem)
    if nodata is not None:
        valid_dem &= dem != nodata

    dem_work = dem.copy()
    dem_work[~valid_dem] = np.nan

    dz_dy, dz_dx = np.gradient(dem_work, yres, xres)
    slope_rad = np.arctan(np.sqrt(dz_dx ** 2 + dz_dy ** 2))
    slope_deg = np.degrees(slope_rad)

    d2z_dx2 = np.gradient(dz_dx, xres, axis=1)
    d2z_dy2 = np.gradient(dz_dy, yres, axis=0)
    curvature = d2z_dx2 + d2z_dy2

    soil_depth, soil_depth_info = compute_soil_depth_from_dem(dem_work, valid_dem, config)

    valid = valid_dem & np.isfinite(slope_deg) & np.isfinite(curvature) & np.isfinite(soil_depth)
    rows, cols = np.where(valid)

    terrain_data = pd.DataFrame({
        "pointid": np.arange(1, len(rows) + 1),
        "grid_code": dem[rows, cols],
        "Slope": slope_deg[rows, cols],
        "Soil_depth": soil_depth[rows, cols],
        "Curvature": curvature[rows, cols],
        "Row": rows,
        "Col": cols
    })

    TERRAIN_CSV.parent.mkdir(parents=True, exist_ok=True)
    terrain_data.to_csv(TERRAIN_CSV, index=False)

    meta = get_terrain_signature(dem_path, config)
    meta["soil_depth_info"] = soil_depth_info
    meta["num_pixels"] = int(len(terrain_data))

    with open(TERRAIN_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return {
        "status": "success",
        "message": "terrain_data.csv has been rebuilt from metric DEM",
        "dem_path": str(dem_path),
        "terrain_csv": str(TERRAIN_CSV),
        "num_pixels": int(len(terrain_data)),
        "soil_depth_info": soil_depth_info
    }
