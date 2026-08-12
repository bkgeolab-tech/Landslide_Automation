import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.cm as cm
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject


def reproject_risk_to_wgs84(
    input_tif: str | Path,
    output_tif: str | Path,
) -> str:
    input_tif = Path(input_tif)
    output_tif = Path(output_tif)
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    dst_crs = "EPSG:4326"

    with rasterio.open(input_tif) as src:
        transform, width, height = calculate_default_transform(
            src.crs,
            dst_crs,
            src.width,
            src.height,
            *src.bounds
        )

        kwargs = src.meta.copy()
        kwargs.update({
            "crs": dst_crs,
            "transform": transform,
            "width": width,
            "height": height,
            "driver": "GTiff",
            "dtype": "float32",
            "nodata": -9999.0,
            "compress": "lzw"
        })

        with rasterio.open(output_tif, "w", **kwargs) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                src_nodata=src.nodata,
                dst_transform=transform,
                dst_crs=dst_crs,
                dst_nodata=-9999.0,
                resampling=Resampling.bilinear
            )

    return str(output_tif)


def render_leaflet_overlay(
    web_tif: str | Path,
    output_png: str | Path,
    output_json: str | Path,
    opacity: float = 0.65,
) -> dict[str, Any]:
    web_tif = Path(web_tif)
    output_png = Path(output_png)
    output_json = Path(output_json)
    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(web_tif) as src:
        data = src.read(1).astype("float32")
        nodata = src.nodata
        bounds = src.bounds

    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)

    valid = np.isfinite(data)
    norm = np.clip(data, 0, 1)

    cmap = mpl.colormaps["jet"]
    rgba = cmap(norm)
    rgba[~valid, 3] = 0.0
    rgba[valid, 3] = float(opacity)

    plt.imsave(output_png, rgba)

    meta = {
        "status": "success",
        "crs": "EPSG:4326",
        "bounds": [
            [float(bounds.bottom), float(bounds.left)],
            [float(bounds.top), float(bounds.right)]
        ],
        "south": float(bounds.bottom),
        "west": float(bounds.left),
        "north": float(bounds.top),
        "east": float(bounds.right),
        "overlay_png": str(output_png),
        "web_tif": str(web_tif)
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    return meta


def prepare_leaflet_outputs(
    input_model_tif: str | Path,
    output_dir: str | Path,
    output_prefix: str = "risk",
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    web_tif = output_dir / f"{output_prefix}_web.tif"
    overlay_png = output_dir / f"{output_prefix}_overlay.png"
    overlay_meta = output_dir / f"{output_prefix}_overlay.json"

    reproject_risk_to_wgs84(input_model_tif, web_tif)
    meta = render_leaflet_overlay(web_tif, overlay_png, overlay_meta)

    return {
        "status": "success",
        "web_tif": str(web_tif),
        "overlay_png": str(overlay_png),
        "overlay_meta": str(overlay_meta),
        "bounds": meta["bounds"]
    }
