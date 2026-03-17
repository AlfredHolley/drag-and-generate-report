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

# Stop existing containers to free ports
echo "🛑 Stopping existing containers..."
docker-compose down || true

# Rebuild Docker images (using cache if possible)
# Only rebuild if requirements.txt or Dockerfile changed
echo "🔨 Rebuilding Docker images (with cache)..."
docker-compose build

# Start containers
echo "🚀 Starting containers..."
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
