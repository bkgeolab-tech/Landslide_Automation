from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import files, forecast, realtime, validation
from app.core.paths import OUTPUT_STATIC_DIR, WEB_DIR, ensure_project_dirs

ensure_project_dirs()

app = FastAPI(
    title="Landslide Hazard Automation API",
    description="Realtime, forecast, and validation API for landslide hazard mapping.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(realtime.router)
app.include_router(forecast.router)
app.include_router(validation.router)
app.include_router(files.router)

# if WEB_DIR.exists():
#     app.mount("/web_old", StaticFiles(directory=str(WEB_DIR)), name="web")


if OUTPUT_STATIC_DIR.exists():
    app.mount("/outputs/static", StaticFiles(directory=str(OUTPUT_STATIC_DIR)), name="output_static")


@app.get("/")
def index():
    return JSONResponse({
        "status": "success",
        "message": "Landslide API is running. Please start the React frontend separately (e.g. npm run dev on port 5173)."
    })


@app.get("/health")
def health():
    return {"status": "ok"}
