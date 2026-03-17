FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libfreetype6-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libcairo2-dev \
    libgirepository1.0-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first
RUN pip install --upgrade pip setuptools wheel

# Copy requirements first for better caching
COPY backend/requirements.txt /app/requirements.txt

# Install Python dependencies from requirements.txt
# This layer will be cached unless requirements.txt changes
RUN pip install --no-cache-dir -r requirements.txt || \
    (echo "Warning: Some packages from requirements.txt failed, installing core packages..." && \
     pip install --no-cache-dir Flask flask-cors pandas fpdf2 reportlab numpy werkzeug Pillow gunicorn)

# Try to install svglib separately (optional, for SVG logo support)
# This may fail if pycairo dependencies are missing, but the app will still work
RUN pip install --no-cache-dir svglib>=1.5.1 || echo "Warning: svglib installation failed, SVG logo support will be disabled"

# Copy backend code
COPY backend/ /app/

# Copy fonts directory
COPY fonts/ /app/fonts/

# Copy logos from frontend directory (SVG for PDF generator, PNG for DOCX generator)
COPY frontend/logo_bw.svg /app/logo_bw.svg
COPY frontend/logo_bw.png /app/logo_bw.png

# Create directories for uploads and outputs
RUN mkdir -p /app/uploads /app/outputs

# Expose port
EXPOSE 5000

# Run with Gunicorn — gthread worker class
# --worker-class gthread  : threads instead of processes → shared memory (OnlyOffice sessions)
# --workers 1             : single process (sessions dict shared by all threads)
# --threads 4             : 4 concurrent requests — no blocking on slow generation
# --preload               : load app once before forking (avoids duplicate CleanupService)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--worker-class", "gthread", "--workers", "1", "--threads", "4", "--timeout", "120", "--preload", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
