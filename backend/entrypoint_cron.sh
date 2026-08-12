#!/bin/bash

# Đợi 1 chút để hệ thống (hoặc API) khởi động xong
sleep 5
echo "Starting Realtime Auto-fetch Cron Service..."

while true; do
  echo "[$(date)] Running run_realtime_pipeline..."
  
  # Chạy script realtime
  python -m app.pipelines.run_realtime
  
  # Ngủ 6 tiếng (6 * 60 * 60 = 21600 giây) trước khi chạy lần tiếp theo
  echo "[$(date)] Pipeline finished. Sleeping for 6 hours..."
  sleep 21600
done
