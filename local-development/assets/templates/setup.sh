#!/bin/bash
set -e

echo "==================================="
echo "Project Setup"
echo "==================================="

# --- Dependency Checks ---

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi

# --- AWS Credentials Check ---

if [ ! -f ~/.aws/credentials ] && [ ! -f ~/.aws/config ]; then
    echo "Warning: No AWS credentials found in ~/.aws/"
    echo "AWS-dependent services will not work without credentials configured."
fi

# --- Environment Setup ---

if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# --- Build & Start ---

echo ""
echo "Building containers..."
docker compose build

echo ""
echo "Starting database..."
docker compose up -d db

echo "Waiting for database to be ready..."
until docker compose exec db pg_isready -U postgres > /dev/null 2>&1; do
    sleep 1
done
echo "Database is ready!"

echo ""
echo "Running database migrations..."
docker compose run --rm api alembic upgrade head

echo ""
echo "Starting all services..."
docker compose up -d

echo ""
echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "Services available at:"
echo "  - UI:       http://localhost:3000"
echo "  - API:      http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo ""
echo "Useful commands:"
echo "  docker compose up       - Start all services"
echo "  docker compose down     - Stop all services"
echo "  docker compose logs -f  - View logs"
echo ""
