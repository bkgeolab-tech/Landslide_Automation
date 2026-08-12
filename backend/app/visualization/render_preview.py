import matplotlib
matplotlib.use("Agg")

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import rasterio


def render_png(
    input_tif: str | Path,
    output_png: str | Path | None = None,
    title: str = "Landslide Hazard Map",
) -> dict[str, Any]:
    input_tif = Path(input_tif)
    if output_png is None:
        output_png = input_tif.with_name(input_tif.stem + "_preview.png")
    output_png = Path(output_png)
    output_png.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(input_tif) as src:
        data = src.read(1).astype("float32")
        nodata = src.nodata

    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)

    fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
    img = ax.imshow(data, cmap="jet", vmin=0, vmax=1)
    fig.colorbar(img, ax=ax, label="P_failure")
    ax.set_title(title)
    ax.set_axis_off()
    fig.savefig(output_png, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return {
        "status": "success",
        "output_png": str(output_png)
    }
