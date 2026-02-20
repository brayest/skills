#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding database..."
python -m app.infrastructure.seed.seed_database

echo "Starting application..."
exec "$@"
