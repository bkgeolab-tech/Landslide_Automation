import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# app/core/paths.py -> app/core -> app -> Landslide_automation
BASE_DIR = Path(os.getenv("LANDSLIDE_BASE_DIR", Path(__file__).resolve().parents[2])).resolve()

DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
REGIONS_DIR = INPUT_DIR / "regions"
OUTPUT_DIR = DATA_DIR / "output"
LATEST_DIR = OUTPUT_DIR / "latest"
RUNS_DIR = OUTPUT_DIR / "runs"
OUTPUT_STATIC_DIR = OUTPUT_DIR / "static"
WEB_DIR = BASE_DIR / "Web"
RAIN_HISTORY = INPUT_DIR / "rain_history.csv"
GEE_KEY_PATH = Path(os.getenv("GEE_KEY_PATH", BASE_DIR / "gee-key.json")).resolve()

ROC_VALIDATION_DIR = INPUT_DIR / "ROC validation"
ROC_COMPARISON_CSV = ROC_VALIDATION_DIR / "ROC_Comparison.csv"
VALIDATION_POINTS_WGS84_CSV = ROC_VALIDATION_DIR / "Validation_points_WGS84.csv"


def ensure_project_dirs() -> None:
    """Tạo các thư mục output/input cơ bản nếu chưa có."""
    for path in [INPUT_DIR, REGIONS_DIR, ROC_VALIDATION_DIR, OUTPUT_DIR, LATEST_DIR, RUNS_DIR, OUTPUT_STATIC_DIR, WEB_DIR]:
        path.mkdir(parents=True, exist_ok=True)

    for sub in ["realtime", "forecast", "validation"]:
        (RUNS_DIR / sub).mkdir(parents=True, exist_ok=True)


def utc_now_compact() -> str:
    """Run ID an toàn cho tên folder/file."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def safe_unlink(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except PermissionError:
        # Windows đôi khi lock file khi trình duyệt/API đang đọc.
        pass


def copy_file(src: str | Path, dst: str | Path) -> Path:
    src_path = Path(src)
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    safe_unlink(dst_path)
    shutil.copy2(src_path, dst_path)
    return dst_path


def latest_forecast_json_path(hours: int) -> Path:
    return LATEST_DIR / f"forecast_h{int(hours):03d}.json"


def static_forecast_prefix(hours: int) -> str:
    return f"latest_forecast_h{int(hours):03d}"


def path_to_str(path: str | Path) -> str:
    return str(Path(path).resolve())


def error_response(message: str, status: str = "error") -> dict[str, Any]:
    return {"status": status, "message": message}
