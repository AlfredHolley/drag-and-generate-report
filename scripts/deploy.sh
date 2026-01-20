#!/bin/bash

# Script de déploiement pour VPS Hostinger
# Usage: ./scripts/deploy.sh

set -e  # Exit on error

echo "🚀 Starting deployment..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your configuration before continuing."
    if [ -t 0 ]; then  # Check if running interactively
        echo "Press Enter to continue after editing .env..."
        read
    fi
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p backend/uploads backend/outputs
touch backend/uploads/.gitkeep backend/outputs/.gitkeep

# Build and start containers
echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting containers..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check health
echo "🏥 Checking service health..."
if curl -f http://localhost/api/health > /dev/null 2>&1; then
    echo "✅ Backend is healthy!"
else
    echo "⚠️  Backend health check failed. Check logs with: docker-compose logs backend"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Useful commands:"
echo "  - View logs: docker-compose logs -f"
echo "  - Stop services: docker-compose down"
echo "  - Restart services: docker-compose restart"
echo "  - View status: docker-compose ps"
echo ""
echo "🌐 Application should be available at: http://localhost"
echo ""
