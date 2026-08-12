# Landslide Automation

Cấu trúc tách rõ 3 phần:

1. `app/`: API, rainfall, terrain, risk, visualization, pipelines.
2. `Web/`: dashboard Leaflet.
3. `Output/latest`, `Output/runs`, `Output/static`: kết quả mới nhất, lịch sử run, file tĩnh cho web.

## Chạy API bằng Docker (VS Code / PowerShell)

Mở terminal (Terminal trong VS Code hoặc PowerShell trên Windows) và chạy các lệnh sau:

```powershell
# Di chuyển vào thư mục code
cd "E:\000. LANDSLIDE SERVER\Landslide_Automation" 

# Di chuyển vào thư mục backend để chạy docker
cd backend

# Khởi chạy các dịch vụ qua Docker Compose
docker-compose up -d --build
```

Để dừng server, chạy lệnh:

```powershell
docker-compose down
```

Để mở Website
```text
https://landslide-automation.vercel.app/
```

## Config link Cloudflare Tunnel cho Web (Sài Quick Tunnel của CloudFlare)
Do chưa có config domain cứng vào Project cho nên khi Docker compose thì Cloudflare sẽ tạo ra 1 link random -> cần config vào Vercel để Web có thể nhận được dữ liệu từ Backend

1. Mở Dashboard Vercel của Project:

```text
https://vercel.com/bkgeolab-techs-projects/landslide-automation
```

2. Chọn Environment Variables ở Thanh menu bên trái

3. Chọn Edit `VITE_API_BASE_URL`, nhập giá trị `Value = CLOUDFLARE_LINK` (được generate khi chạy `docker-compose`)

4. Bấm nút Redeploy để khởi động lại web



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