# Landslide Automation

Cấu trúc tách rõ 3 phần:

1. `app/`: API, rainfall, terrain, risk, visualization, pipelines.
2. `Web/`: dashboard Leaflet.
3. `Output/latest`, `Output/runs`, `Output/static`: kết quả mới nhất, lịch sử run, file tĩnh cho web.

## Chạy API

```bash
cd Landslide_automation
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Mở:

```text
http://localhost:8000
http://localhost:8000/docs
```

## Endpoint chính

Realtime:

```text
POST /api/realtime/run?forecast_hour=6
GET  /api/realtime/latest
GET  /api/realtime/overlay/png
GET  /api/realtime/overlay/meta
```

Forecast:

```text
POST /api/forecast/run?hours=24
POST /api/forecast/run-batch?hours=6&hours=12&hours=24
GET  /api/forecast/latest?hours=24
GET  /api/forecast/overlay/png?hours=24
GET  /api/forecast/overlay/meta?hours=24
```

Validation 2018:

```text
POST /api/validation/2018/run
GET  /api/validation/2018/latest
GET  /api/validation/2018/roc
```