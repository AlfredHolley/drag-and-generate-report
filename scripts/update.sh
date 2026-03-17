#!/bin/bash

# Script de mise à jour automatique sur le VPS
# Ce script est appelé par GitHub Actions après un push

set -e  # Exit on error

echo "🔄 Starting automatic update..."

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_DIR"

echo "📂 Current directory: $(pwd)"

# Pull latest changes from GitHub
echo "📥 Pulling latest changes from GitHub..."
git fetch origin

# Try main branch first, fallback to master
if git show-ref --verify --quiet refs/remotes/origin/main; then
    git reset --hard origin/main
elif git show-ref --verify --quiet refs/remotes/origin/master; then
    git reset --hard origin/master
else
    echo "❌ Neither 'main' nor 'master' branch found!"
    exit 1
fi

# Ensure .env exists (don't overwrite if it exists)
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📝 Creating .env file from .env.example..."
        cp .env.example .env
        echo "⚠️  WARNING: .env file was created from template. Please configure it!"
    else
        echo "⚠️  WARNING: .env.example not found. Creating minimal .env file..."
        cat > .env << 'EOF'
# Flask Configuration
FLASK_ENV=production

# File Storage Paths
UPLOAD_FOLDER=/app/uploads
OUTPUT_FOLDER=/app/outputs

# Cleanup Service Configuration
CLEANUP_INTERVAL=60
FILE_TIMEOUT=600
EOF
        echo "⚠️  WARNING: Minimal .env file created. Please configure it according to your needs!"
    fi
fi

# Ensure directories exist
echo "📁 Ensuring directories exist..."
mkdir -p backend/uploads backend/outputs
touch backend/uploads/.gitkeep backend/outputs/.gitkeep 2>/dev/null || true

# Ensure shared-proxy network exists (required by docker-compose.yml)
docker network inspect shared-proxy >/dev/null 2>&1 \
  || docker network create shared-proxy

# ── Smart restart: rebuild & restart only app services ───────────────────────
# OnlyOffice takes 2-3 min to start and rarely changes — we leave it running.
echo "🛑 Stopping app services (backend + nginx only)..."
docker compose stop backend nginx 2>/dev/null || docker-compose stop backend nginx 2>/dev/null || true

echo "🔨 Rebuilding backend image (with cache)..."
docker compose build backend 2>/dev/null || docker-compose build backend

echo "🚀 Starting app services..."
docker compose up -d --no-deps backend nginx 2>/dev/null \
  || docker-compose up -d --no-deps backend nginx

# Start OnlyOffice only if it is NOT already running
OO_RUNNING=$(docker compose ps onlyoffice --status running --quiet 2>/dev/null \
             || docker ps -q --filter "name=report-generator-onlyoffice" --filter "status=running" 2>/dev/null \
             || true)
if [ -z "$OO_RUNNING" ]; then
  echo "🚀 OnlyOffice not running — starting it..."
  docker compose up -d --no-deps onlyoffice 2>/dev/null \
    || docker-compose up -d --no-deps onlyoffice 2>/dev/null || true
else
  echo "✓ OnlyOffice already running — skipped restart."
fi

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo "🏥 Checking service health..."
MAX_RETRIES=5
RETRY_COUNT=0
HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost/api/health > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "  Retry $RETRY_COUNT/$MAX_RETRIES..."
    sleep 5
done

if [ "$HEALTHY" = true ]; then
    echo "✅ Backend is healthy!"
    echo ""
    echo "✅ Update complete!"
    exit 0
else
    echo "❌ Health check failed after $MAX_RETRIES retries"
    echo "📋 Check logs with: docker-compose logs backend"
    exit 1
fi
