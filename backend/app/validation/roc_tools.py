from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio

from app.core.paths import ROC_COMPARISON_CSV, VALIDATION_POINTS_WGS84_CSV


def _pick_column(df: pd.DataFrame, candidates: list[str], contains: list[str] | None = None) -> str:
    """Tìm cột theo tên chính xác trước, sau đó tìm theo từ khóa."""
    lower_map = {str(col).lower().strip(): col for col in df.columns}

    for name in candidates:
        key = name.lower().strip()
        if key in lower_map:
            return lower_map[key]

    if contains:
        for col in df.columns:
            col_lower = str(col).lower().strip()
            if all(token.lower() in col_lower for token in contains):
                return col

    raise ValueError(f"Không tìm thấy cột phù hợp. Các cột hiện có: {list(df.columns)}")


def read_static_roc_curve(csv_path: str | Path = ROC_COMPARISON_CSV) -> dict[str, Any]:
    """
    Đọc đường ROC của mô hình tĩnh dùng mưa trạm.

    File CSV có thể dùng các tên cột phổ biến:
    - FPR_WithUncertainty, TPR_WithUncertainty
    - False Positive Rate, True Positive Rate
    - FPR, TPR
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return {
            "available": False,
            "message": f"Không tìm thấy file ROC so sánh: {csv_path}",
            "csv_path": str(csv_path),
        }

    df = pd.read_csv(csv_path)
    fpr_col = _pick_column(
        df,
        ["False Positive Rate", "FPR", "FPR_WithUncertainty", "false_positive_rate"],
        contains=["fpr"],
    )
    tpr_col = _pick_column(
        df,
        ["True Positive Rate", "TPR", "TPR_WithUncertainty", "true_positive_rate"],
        contains=["tpr"],
    )

    fpr = pd.to_numeric(df[fpr_col], errors="coerce").to_numpy(dtype="float64")
    tpr = pd.to_numeric(df[tpr_col], errors="coerce").to_numpy(dtype="float64")

    valid = np.isfinite(fpr) & np.isfinite(tpr)
    fpr = np.clip(fpr[valid], 0.0, 1.0)
    tpr = np.clip(tpr[valid], 0.0, 1.0)

    if fpr.size < 2:
        return {
            "available": False,
            "message": "File ROC so sánh không đủ điểm hợp lệ.",
            "csv_path": str(csv_path),
        }

    order = np.argsort(fpr)
    fpr = fpr[order]
    tpr = tpr[order]
    auc = float(np.trapezoid(tpr, fpr))

    return {
        "available": True,
        "csv_path": str(csv_path),
        "fpr_col": str(fpr_col),
        "tpr_col": str(tpr_col),
        "fpr": fpr.tolist(),
        "tpr": tpr.tolist(),
        "auc": auc,
        "n_points": int(fpr.size),
    }


def read_validation_points(csv_path: str | Path = VALIDATION_POINTS_WGS84_CSV) -> pd.DataFrame:
    """
    Đọc validation points đã có Longitude/Latitude WGS84 và Label.
    Label: 1 = positive landslide, 0 = negative/non-landslide.
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Không tìm thấy validation points: {csv_path}")

    df = pd.read_csv(csv_path)
    lon_col = _pick_column(df, ["Longitude", "Lon", "longitude", "lon", "X_WGS84"])
    lat_col = _pick_column(df, ["Latitude", "Lat", "latitude", "lat", "Y_WGS84"])
    label_col = _pick_column(df, ["Label", "label", "Class", "class", "Landslide"])

    out = df.copy()
    out["Longitude"] = pd.to_numeric(out[lon_col], errors="coerce")
    out["Latitude"] = pd.to_numeric(out[lat_col], errors="coerce")
    out["Label"] = pd.to_numeric(out[label_col], errors="coerce")

    out = out[np.isfinite(out["Longitude"]) & np.isfinite(out["Latitude"]) & np.isfinite(out["Label"])].copy()
    out["Label"] = out["Label"].astype(int)
    out = out[out["Label"].isin([0, 1])].copy()

    if out.empty:
        raise ValueError("Validation_points_WGS84.csv không có điểm hợp lệ với Longitude, Latitude, Label.")

    return out


def sample_risk_at_points(web_tif: str | Path, points: pd.DataFrame) -> pd.DataFrame:
    """Sample P_failure từ risk web GeoTIFF EPSG:4326 tại Longitude/Latitude."""
    web_tif = Path(web_tif)
    if not web_tif.exists():
        raise FileNotFoundError(f"Không tìm thấy risk web tif để sample ROC: {web_tif}")

    coords = list(zip(points["Longitude"].astype(float), points["Latitude"].astype(float)))

    with rasterio.open(web_tif) as src:
        nodata = src.nodata
        values = np.array([v[0] for v in src.sample(coords)], dtype="float64")

    if nodata is not None:
        values = np.where(values == nodata, np.nan, values)

    sampled = points.copy()
    sampled["P_failure"] = values
    sampled = sampled[np.isfinite(sampled["P_failure"])].copy()
    sampled["P_failure"] = sampled["P_failure"].clip(0.0, 1.0)

    return sampled


def compute_roc_curve(y_true: np.ndarray, scores: np.ndarray) -> dict[str, Any]:
    """Tính ROC và AUC không cần sklearn."""
    y_true = np.asarray(y_true).astype(int)
    scores = np.asarray(scores).astype(float)

    valid = np.isfinite(scores) & np.isin(y_true, [0, 1])
    y_true = y_true[valid]
    scores = scores[valid]

    positives = int(np.sum(y_true == 1))
    negatives = int(np.sum(y_true == 0))

    if positives == 0 or negatives == 0 or scores.size < 2:
        return {
            "available": False,
            "message": "Không đủ cả positive và negative để tính ROC.",
            "n_samples": int(scores.size),
            "n_positive": positives,
            "n_negative": negatives,
        }

    thresholds = np.r_[np.inf, np.sort(np.unique(scores))[::-1], -np.inf]
    fpr_values: list[float] = []
    tpr_values: list[float] = []
    threshold_values: list[float | str] = []

    for threshold in thresholds:
        pred = scores >= threshold
        tp = int(np.sum(pred & (y_true == 1)))
        fp = int(np.sum(pred & (y_true == 0)))

        tpr = tp / positives
        fpr = fp / negatives

        tpr_values.append(float(tpr))
        fpr_values.append(float(fpr))
        if np.isposinf(threshold):
            threshold_values.append("inf")
        elif np.isneginf(threshold):
            threshold_values.append("-inf")
        else:
            threshold_values.append(float(threshold))

    fpr_arr = np.asarray(fpr_values, dtype="float64")
    tpr_arr = np.asarray(tpr_values, dtype="float64")
    order = np.argsort(fpr_arr)
    auc = float(np.trapezoid(tpr_arr[order], fpr_arr[order]))

    # Youden J để gợi ý ngưỡng tốt nhất.
    j_scores = tpr_arr - fpr_arr
    best_idx = int(np.nanargmax(j_scores))
    best_threshold = threshold_values[best_idx]

    return {
        "available": True,
        "fpr": fpr_values,
        "tpr": tpr_values,
        "thresholds": threshold_values,
        "auc": auc,
        "best_threshold_youden": best_threshold,
        "best_youden_j": float(j_scores[best_idx]),
        "n_samples": int(scores.size),
        "n_positive": positives,
        "n_negative": negatives,
    }


def write_points_geojson(points: pd.DataFrame, output_geojson: str | Path) -> str:
    output_geojson = Path(output_geojson)
    output_geojson.parent.mkdir(parents=True, exist_ok=True)

    features = []
    for _, row in points.iterrows():
        props = {}
        for col in points.columns:
            value = row[col]
            if pd.isna(value):
                props[str(col)] = None
            elif isinstance(value, (np.integer, int)):
                props[str(col)] = int(value)
            elif isinstance(value, (np.floating, float)):
                props[str(col)] = float(value)
            else:
                props[str(col)] = str(value)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(row["Longitude"]), float(row["Latitude"])],
            },
            "properties": props,
        })

    import json
    geojson = {"type": "FeatureCollection", "features": features}
    with open(output_geojson, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)

    return str(output_geojson)


def plot_roc_comparison(
    dynamic_roc: dict[str, Any],
    static_roc: dict[str, Any],
    output_png: str | Path,
) -> str:
    output_png = Path(output_png)
    output_png.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7.2, 5.6), dpi=160)

    ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1.2, label="Random classifier")

    if static_roc.get("available"):
        ax.plot(
            static_roc["fpr"],
            static_roc["tpr"],
            linewidth=2.2,
            label=f"Static rainfall-station model, AUC = {static_roc['auc']:.3f}",
        )

    if dynamic_roc.get("available"):
        ax.plot(
            dynamic_roc["fpr"],
            dynamic_roc["tpr"],
            linewidth=2.2,
            marker="o",
            markersize=3,
            label=f"Current validation P_failure model, AUC = {dynamic_roc['auc']:.3f}",
        )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC comparison - Validation 2018")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)

    return str(output_png)


def build_validation_roc_outputs(
    web_tif: str | Path,
    output_dir: str | Path,
    static_roc_csv: str | Path = ROC_COMPARISON_CSV,
    validation_points_csv: str | Path = VALIDATION_POINTS_WGS84_CSV,
) -> dict[str, Any]:
    """
    Tạo ROC validation 2018:
    1. Đọc ROC tĩnh từ CSV có sẵn.
    2. Đọc validation points WGS84 + label.
    3. Sample P_failure từ risk_web.tif.
    4. Tính ROC động của mô hình validation hiện tại.
    5. Vẽ hình so sánh và xuất GeoJSON điểm validation.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_png = output_dir / "validation_2018_roc.png"
    output_json = output_dir / "validation_2018_roc.json"
    output_points_csv = output_dir / "validation_points_sampled.csv"
    output_points_geojson = output_dir / "validation_points_sampled.geojson"

    static_roc = read_static_roc_curve(static_roc_csv)

    try:
        points = read_validation_points(validation_points_csv)
        sampled = sample_risk_at_points(web_tif, points)
        sampled.to_csv(output_points_csv, index=False)
        write_points_geojson(sampled, output_points_geojson)

        dynamic_roc = compute_roc_curve(
            y_true=sampled["Label"].to_numpy(),
            scores=sampled["P_failure"].to_numpy(),
        )
    except Exception as exc:
        sampled = pd.DataFrame()
        dynamic_roc = {
            "available": False,
            "message": f"Không tính được ROC động từ validation points: {exc}",
        }

    if static_roc.get("available") or dynamic_roc.get("available"):
        plot_roc_comparison(dynamic_roc, static_roc, output_png)
        roc_png = str(output_png)
    else:
        roc_png = None

    result = {
        "roc_available": bool(static_roc.get("available") or dynamic_roc.get("available")),
        "static_station_model": static_roc,
        "dynamic_pf_model": dynamic_roc,
        "files": {
            "roc_png": roc_png,
            "roc_json": str(output_json),
            "sampled_points_csv": str(output_points_csv) if output_points_csv.exists() else None,
            "sampled_points_geojson": str(output_points_geojson) if output_points_geojson.exists() else None,
        },
        "input_files": {
            "static_roc_csv": str(static_roc_csv),
            "validation_points_csv": str(validation_points_csv),
        },
    }

    from app.core.paths import write_json
    write_json(output_json, result)
    return result
