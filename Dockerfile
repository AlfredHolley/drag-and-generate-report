FROM python:3.11-slim

# Set working directory
WORKDIR /app

# System dependencies — Pillow image support only (pycairo/svglib removed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel

# Copy requirements first — this layer is cached unless requirements.txt changes
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ /app/

# Copy fonts directory
COPY fonts/ /app/fonts/

# Copy logos from frontend directory
COPY frontend/logo_bw.svg /app/logo_bw.svg
COPY frontend/logo_bw.png /app/logo_bw.png

# Create directories for uploads and outputs
RUN mkdir -p /app/uploads /app/outputs

# Expose port
EXPOSE 5000

# Run with Gunicorn
# --preload: Charge l'app UNE SEULE fois avant de forker les workers
# Cela évite que chaque worker démarre son propre CleanupService
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--preload", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
