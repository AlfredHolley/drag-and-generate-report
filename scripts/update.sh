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
git reset --hard origin/main  # ou origin/master selon votre branche principale

# Ensure .env exists (don't overwrite if it exists)
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  WARNING: .env file was created from template. Please configure it!"
fi

# Ensure directories exist
echo "📁 Ensuring directories exist..."
mkdir -p backend/uploads backend/outputs
touch backend/uploads/.gitkeep backend/outputs/.gitkeep 2>/dev/null || true

# Rebuild and restart containers
echo "🔨 Rebuilding Docker images..."
docker-compose build --no-cache

echo "🔄 Restarting containers..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 15

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
