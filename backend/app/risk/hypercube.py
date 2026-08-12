import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio
from scipy.stats import qmc, norm, truncnorm, beta as beta_dist
from scipy.special import erfinv

from app.core.config import get_monte_carlo_settings
from app.core.paths import INPUT_DIR
from app.terrain.prepare_terrain import build_terrain_data
from app.risk.monte_carlo import summarize_risk_array

SOIL_PROPERTIES = INPUT_DIR / "Soil_Properties.csv"

_EPS = 1e-12

def _to_logn_params(mu: float, cov: float) -> tuple[float, float]:
    """(mean, COV) -> (mu_ln, sigma_ln) cho Log-normal."""
    if cov <= 0:
        return np.log(mu), 0.0
    sigma2 = np.log(1.0 + cov**2)
    return np.log(mu) - 0.5 * sigma2, np.sqrt(sigma2)

def _beta_ab(mu: float, cov: float) -> tuple[float, float] | None:
    """(mean, COV) -> (alpha, beta) cho Beta. Trả None nếu không khả thi."""
    if not (0.0 < mu < 1.0):
        return None
    if cov <= 0:
        return (1e6, 1e6 * (1 / mu - 1))
    var = (cov * mu)**2
    if var >= mu * (1 - mu):
        return None
    ab_sum = mu * (1 - mu) / var - 1.0
    a = mu * ab_sum
    b = (1 - mu) * ab_sum
    return (a, b) if a > 0 and b > 0 else None

def get_prop(df: pd.DataFrame, name: str) -> tuple[float, float]:
    row = df.loc[df["Properties"].str.strip().str.lower() == name.lower()]
    if row.empty:
        raise ValueError(f"Missing soil property: {name}")
    val = float(row.iloc[0]["Value"])
    cov = float(row.iloc[0]["COV"])
    return val, cov

def map_to_distributions(U: np.ndarray, soil_props: pd.DataFrame) -> np.ndarray:
    """
    Map unit hypercube U (n x 5) -> [γ, φ, c', n, Ks]
    """
    n_samp = U.shape[0]
    out = np.zeros((n_samp, 5), dtype=float)
    U_safe = np.clip(U, _EPS, 1 - _EPS)

    mu_gamma, cov_gamma = get_prop(soil_props, "unit weight")
    mu_phi_deg, cov_phi = get_prop(soil_props, "friction angle")
    mu_c, cov_c = get_prop(soil_props, "cohesion")
    mu_n, cov_n = get_prop(soil_props, "porosity")
    mu_ks, cov_ks = get_prop(soil_props, "hydraulic conductivity")

    mu_phi = np.deg2rad(mu_phi_deg)
    sigma_phi = np.deg2rad(mu_phi_deg * cov_phi)

    # --- col 0: γ ~ Log-normal ---
    mu_ln, sig_ln = _to_logn_params(mu_gamma, cov_gamma)
    if sig_ln > 0:
        out[:, 0] = np.exp(mu_ln + sig_ln * np.sqrt(2) * erfinv(2 * U_safe[:, 0] - 1))
    else:
        out[:, 0] = np.exp(mu_ln)

    # --- col 1: φ ~ Truncated Normal [5°, 50°] (rad) ---
    phi_min = np.deg2rad(5.0)
    phi_max = np.deg2rad(50.0)
    if sigma_phi <= 0:
        out[:, 1] = np.clip(np.full(n_samp, mu_phi), phi_min, phi_max)
    else:
        a_phi = (phi_min - mu_phi) / sigma_phi
        b_phi = (phi_max - mu_phi) / sigma_phi
        out[:, 1] = truncnorm.ppf(U_safe[:, 1], a=a_phi, b=b_phi, loc=mu_phi, scale=sigma_phi)

    # --- col 2: c' ~ Truncated Normal [0, +∞) ---
    sigma_c = mu_c * cov_c
    if sigma_c <= 0:
        out[:, 2] = max(mu_c, 0.0)
    else:
        a_c = (0.0 - mu_c) / sigma_c
        b_c = np.inf
        out[:, 2] = truncnorm.ppf(U_safe[:, 2], a=a_c, b=b_c, loc=mu_c, scale=sigma_c)

    # --- col 3: n ~ Beta(α, β) ---
    ab = _beta_ab(mu_n, cov_n)
    if ab is not None:
        alpha_n, beta_n = ab
        out[:, 3] = beta_dist.ppf(U_safe[:, 3], a=alpha_n, b=beta_n)
    else:
        out[:, 3] = np.clip(mu_n + (mu_n * cov_n) * norm.ppf(U_safe[:, 3]), 0.05, 0.65)

    # --- col 4: Ks ~ Log-normal ---
    mu_ln_ks, sig_ln_ks = _to_logn_params(mu_ks, cov_ks)
    if sig_ln_ks > 0:
        out[:, 4] = np.exp(mu_ln_ks + sig_ln_ks * np.sqrt(2) * erfinv(2 * U_safe[:, 4] - 1))
    else:
        out[:, 4] = np.exp(mu_ln_ks)

    return out

def calculate_risk_lhs(
    rain_intensity: float,
    duration: float,
    output_dir: str | Path,
    output_prefix: str = "risk",
    region_id: str = "nha_trang",
    num_iterations: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Tính P_failure bằng LHS và ghi GeoTIFF vào output_dir."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    settings = get_monte_carlo_settings()
    # LHS converges very fast, 500-1000 is usually plenty. We cap at 1000 if not specified to avoid long runs
    # that are not needed. If a specific num_iterations is provided, we use it.
    default_iters = settings.get("iterations", 500)
    if default_iters > 1000:
        default_iters = 500
    num_iterations = int(num_iterations or default_iters)
    seed = settings.get("seed", 42) if seed is None else seed

    terrain_status = build_terrain_data(force=False, region_id=region_id)
    dem_path = Path(terrain_status["dem_path"])
    terrain_csv = Path(terrain_status["terrain_csv"])

    with rasterio.open(dem_path) as src:
        template_meta = src.meta.copy()
        height, width = src.shape
        transform = src.transform

    terrain_data = pd.read_csv(terrain_csv)
    if not SOIL_PROPERTIES.exists():
        raise FileNotFoundError(f"Không tìm thấy soil_properties.csv: {SOIL_PROPERTIES}")
    soil_props = pd.read_csv(SOIL_PROPERTIES)

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

    # LHS sampling
    sampler = qmc.LatinHypercube(d=5, seed=seed)
    U = sampler.random(n=num_iterations)
    samples = map_to_distributions(U, soil_props)

    for i in range(num_iterations):
        gamma = samples[i, 0]
        phi_rad = samples[i, 1]
        cohesion = samples[i, 2]
        porosity = samples[i, 3]
        ks = samples[i, 4]

        tan_phi = np.tan(phi_rad)
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
        "algorithm": "LHS",
    }
