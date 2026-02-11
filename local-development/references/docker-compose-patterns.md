# Docker Compose Patterns for Local Development

## Service Dependency & Health Checks

The critical pattern: never let a service start before its dependencies are truly ready. Docker's `depends_on` alone only waits for container start, not service readiness.

### PostgreSQL Health Check

```yaml
db:
  image: postgres:15-alpine
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 5s
    timeout: 5s
    retries: 5
```

### Dependent Service with Health Condition

```yaml
api:
  depends_on:
    db:
      condition: service_healthy  # Waits for healthcheck to pass
```

### Chained Dependencies

```yaml
ui:
  depends_on:
    - api        # Simple dependency (waits for start, not health)
api:
  depends_on:
    db:
      condition: service_healthy  # Health-checked dependency
```

Use `condition: service_healthy` for database dependencies. Use simple `depends_on` for service-to-service where the dependent service has its own retry logic.

## Volume Mount Strategies

### Code Hot-Reload (Bind Mount)

Mount source code for live changes without rebuilding:

```yaml
volumes:
  - ./api:/app          # Python API source
  - ./ui:/app           # UI source
```

### Data Persistence (Named Volume)

Persist database data across container restarts:

```yaml
volumes:
  - postgres_data:/var/lib/postgresql/data

volumes:   # Top-level declaration
  postgres_data:
```

### Anonymous Volumes (Dependency Isolation)

Prevent host bind mount from overwriting container-installed dependencies:

```yaml
volumes:
  - ./ui:/app           # Source code from host
  - /app/node_modules   # Anonymous volume — keeps container's installed modules
  - /app/.next          # Anonymous volume — keeps build cache
```

This pattern is essential for Node.js projects. Without the anonymous volume for `node_modules`, the host bind mount overwrites the container's installed packages (which may include platform-specific native binaries).

### Shared Volumes Between Services

Mount the same directory into multiple containers:

```yaml
api:
  volumes:
    - ./workspace:/app/workspace
ui:
  volumes:
    - ./workspace:/app/workspace
```

### Read-Only Mounts

For sensitive files that should never be modified by the container:

```yaml
volumes:
  - ~/.aws:/home/appuser/.aws:ro   # AWS credentials — read-only
```

## AWS Credential Sharing

**Principle: Never use access keys in environment variables or code.**

Mount the host's AWS credential files into the container:

```yaml
api:
  volumes:
    - ~/.aws:/home/appuser/.aws:ro
  environment:
    - AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
    - AWS_PROFILE=${AWS_PROFILE:-default}
```

The credential chain resolution order:
1. Environment variables (AWS_PROFILE selects the profile)
2. `~/.aws/credentials` file (mounted read-only)
3. `~/.aws/config` file (mounted read-only)

The mount target must match the home directory of the container user. If the Dockerfile creates `appuser` with home `/home/appuser`, mount to `/home/appuser/.aws`.

## Network Configuration

### Custom Bridge Network

```yaml
networks:
  app-network:
    driver: bridge
```

All services on the same network can reference each other by service name:
- API connects to DB via `db:5432` (not `localhost:5432`)
- UI makes server-side calls to API via `api:8000` (not `localhost:8000`)
- Client-side (browser) calls still use `localhost:8000`

### Environment Variable for API URL

```yaml
ui:
  environment:
    - NEXT_PUBLIC_API_URL=http://localhost:8000  # Browser-side calls
```

For server-side calls within Docker network, use the service name (`http://api:8000`).

## Environment Variable Patterns

### Precedence Chain

1. Shell environment variables (highest priority)
2. `docker compose` CLI `--env-file` flag
3. `.env` file in project root (compose reads automatically)
4. `environment:` block defaults in docker-compose.yml (lowest priority)

### Default Values in Compose

```yaml
environment:
  POSTGRES_USER: ${POSTGRES_USER:-postgres}      # From .env or default
  DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-postgres}@db:5432/${POSTGRES_DB:-app_db}
```

### .env File Pattern

- Commit `.env.example` as template (no secrets)
- Gitignore `.env` (local overrides with potential secrets)
- Setup script copies `.env.example` → `.env` if not exists

## Container Naming

```yaml
services:
  db:
    container_name: ${PROJECT_NAME}-db
  api:
    container_name: ${PROJECT_NAME}-api
  ui:
    container_name: ${PROJECT_NAME}-ui
```

Explicit names prevent Docker Compose from auto-generating names based on directory, making `docker logs`, `docker exec`, and other commands predictable.

## Port Mapping Conventions

| Service    | Container Port | Default Host Port |
|------------|---------------|-------------------|
| PostgreSQL | 5432          | 5432              |
| Python API | 8000          | 8000              |
| Node.js UI | 3000          | 3000              |
| Redis      | 6379          | 6379              |

Use variables for host ports to avoid conflicts when running multiple projects:

```yaml
ports:
  - "${API_PORT:-8000}:8000"
```
