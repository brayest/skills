# Setup Script Automation

## Script Structure

A setup script automates the entire local development bootstrap into one command. The script follows a strict sequence: validate → configure → build → start → migrate → verify.

### Skeleton

```bash
#!/bin/bash
set -e  # Exit immediately on any error

# 1. Dependency validation
# 2. Credential checks
# 3. Environment file setup
# 4. Container build
# 5. Database startup + health polling
# 6. Migration execution
# 7. Full service startup
# 8. Output summary
```

## Dependency Validation

Check for required tools before attempting anything:

```bash
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose is not installed"
    exit 1
fi
```

## AWS Credential Check

Warn (don't fail) if credentials are missing — some projects may not need AWS:

```bash
if [ ! -f ~/.aws/credentials ] && [ ! -f ~/.aws/config ]; then
    echo "Warning: No AWS credentials found in ~/.aws/"
    echo "AWS-dependent services will not work without credentials configured."
fi
```

## Environment File Setup

```bash
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi
```

Never overwrite an existing `.env` — it may contain intentional local overrides.

## Database Health Polling

Start the database first and poll until ready, rather than using a fixed sleep:

```bash
docker compose up -d db

echo "Waiting for database to be ready..."
until docker compose exec db pg_isready -U postgres > /dev/null 2>&1; do
    sleep 1
done
echo "Database is ready!"
```

This is more reliable than `sleep 10` because database startup time varies by machine.

## Migration Execution

Run migrations as a one-off command before starting the full stack:

```bash
docker compose run --rm api alembic upgrade head
```

`--rm` removes the temporary container after migration completes.

### Setup vs Entrypoint Migrations

| Approach | When to Use |
|----------|-------------|
| In `setup.sh` | First-time setup, ensures DB schema exists before any service starts |
| In `entrypoint.sh` | Every container start, catches schema changes during development |
| Both | Recommended — setup handles first-time, entrypoint handles ongoing |

When using both, `alembic upgrade head` is idempotent — running it twice is safe.

## Output Summary

End the script with actionable information:

```bash
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
```

## Common Operations

### Teardown

```bash
# Stop services, keep data
docker compose down

# Stop services, destroy data (full reset)
docker compose down -v
```

### Rebuild After Dependency Changes

```bash
# Rebuild a specific service
docker compose build api

# Rebuild and restart
docker compose up -d --build api
```

### Database Reset

```bash
docker compose down -v          # Destroy volume
docker compose up -d db         # Restart DB
# Wait for health...
docker compose run --rm api alembic upgrade head  # Re-run migrations
```

### Log Inspection

```bash
docker compose logs -f api      # Follow API logs
docker compose logs -f db       # Follow DB logs
docker compose logs --tail=50   # Last 50 lines from all services
```

### Shell Access

```bash
docker compose exec api bash         # Shell into running API container
docker compose exec db psql -U postgres  # PostgreSQL shell
```
