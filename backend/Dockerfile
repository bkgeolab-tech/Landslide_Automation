FROM python:3.11-slim

# Install system dependencies required for GDAL/Rasterio
RUN apt-get update && apt-get install -y \
    gdal-bin \
    libgdal-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for GDAL Python bindings
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Default command (used by the 'api' service)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
