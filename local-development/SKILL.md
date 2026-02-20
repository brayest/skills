---
name: local-development
description: "This skill should be used when setting up or configuring local development environments using Docker Compose for projects with a Python API backend, UI frontend, and database. Provides production-grade patterns for service orchestration, one-command setup scripts, AWS credential handling, fail-fast configuration, and database migration automation."
---

# Local Development

Production-grade local development setup using Docker Compose to orchestrate a Python API, UI frontend, and database. All patterns prioritize fail-fast behavior, explicit configuration, and one-command bootstrap.

## When to Use

- Setting up a new project with API + UI + DB from scratch
- Adding Docker Compose to an existing project
- Configuring local AWS integration (Bedrock, S3, DynamoDB, etc.)
- Setting up database migrations for local development
- Troubleshooting Docker Compose service orchestration
- Adding a new service to an existing compose stack

## Core Principles

1. **Fail fast, fail loud** — No fallback values for required configuration. Missing env vars raise `ValidationError` at startup, not silent empty strings at runtime.
2. **No access keys** — AWS credentials shared via `~/.aws` mount (read-only). Region always explicit. Never store access keys in `.env`, environment variables, or code.
3. **One-command setup** — A single `./setup.sh` bootstraps everything: dependency checks, env file creation, container builds, database health polling, migrations, and service startup.
4. **Health-checked dependencies** — Services wait for dependencies to be truly ready (PostgreSQL `pg_isready`), not just container-started.
5. **Auto-migrations and seeding** — Database migrations and seed data run automatically in the API entrypoint before the server starts. Both must be idempotent. Reference data (domain definitions, topic structures) is embedded in the seed script — never depend on external files at runtime.
6. **Non-root containers** — API containers run as `appuser:1001`, never root.
7. **Hot-reload everything** — Source code mounted as bind volumes for live changes without rebuilding.

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   UI (:3000) │────▶│  API (:8000) │────▶│  DB (:5432)  │
│  Node/React  │     │ Python/Fast  │     │  PostgreSQL  │
│  bind mount  │     │ bind mount   │     │ named volume │
└─────────────┘     │ ~/.aws:ro    │     └─────────────┘
                     └─────────────┘
         ◀──── app-network (bridge) ────▶
```

- **DB** starts first, health-checked with `pg_isready`
- **API** starts after DB is healthy, runs migrations + seed in entrypoint, then starts server
- **UI** starts after API, connects via `localhost` (browser) or service name (SSR)

## How to Use This Skill

### Setting Up a New Project

To scaffold a new project with local development infrastructure:

1. Copy and adapt the template files from `assets/templates/`:
   - `docker-compose.yml` — 3-service orchestration
   - `setup.sh` — one-command bootstrap (make executable with `chmod +x`)
   - `env.example` — rename to `.env.example`, adjust variables
   - `api.Dockerfile` — rename to `api/Dockerfile`
   - `api.entrypoint.sh` — rename to `api/entrypoint.sh` (make executable)
   - `ui.Dockerfile` — rename to `ui/Dockerfile`

2. Replace placeholder values (`${PROJECT_NAME}`, ports, DB name) with project-specific values.

3. Add `.env` to `.gitignore`. Commit `.env.example` as the template.

4. For detailed Docker Compose patterns, consult `references/docker-compose-patterns.md`.

### Adding Docker Compose to an Existing Project

To containerize an existing project with separate `api/` and `ui/` directories:

1. Start with `assets/templates/docker-compose.yml` and adapt service definitions.
2. Add Dockerfiles to each service directory using the templates.
3. Create `setup.sh` from the template for one-command bootstrap.
4. Ensure the API entrypoint runs migrations and seeding before starting the server.

For volume mount strategies (hot-reload, node_modules isolation, data persistence), consult `references/docker-compose-patterns.md`.

### Configuring AWS Integration

To set up AWS service access (Bedrock, S3, etc.) in the local dev environment:

1. Mount `~/.aws` read-only into the API container: `~/.aws:/home/appuser/.aws:ro`
2. Set `AWS_DEFAULT_REGION` as a required environment variable (no default)
3. Set `AWS_PROFILE` as optional (defaults to credential chain discovery)
4. Validate AWS connectivity in the API health endpoint

The mount target path must match the container user's home directory. If using `appuser` with home `/home/appuser`, mount to `/home/appuser/.aws`.

### Setting Up Database with Migrations and Seeding

To configure PostgreSQL with Alembic migrations and automatic data seeding:

1. Use the PostgreSQL healthcheck pattern in docker-compose.yml
2. Configure SQLAlchemy engine with connection pooling (`pool_pre_ping=True`)
3. Set up Alembic with `DATABASE_URL` from environment (fail if missing)
4. Run migrations and seeding in the API entrypoint (every container start)
5. Use `ENTRYPOINT` + `CMD` pattern so `docker-compose command:` overrides the server command while entrypoint still runs migrations + seed
6. Seed scripts must be idempotent (clear-then-insert) and embed reference data directly — no external file dependencies at runtime
7. Use synchronous SQLAlchemy (`psycopg2`) for seed scripts, async (`asyncpg`) for the FastAPI app

For detailed configuration, session management, migration, and seeding patterns, consult `references/config-and-database.md`.

## Decision Guidance

### Database Selection

| Database   | When to Use |
|------------|-------------|
| PostgreSQL | Default choice. Relational data, JSONB support, robust ecosystem |
| Redis      | Caching, session storage, pub/sub. Add as a 4th service |
| DynamoDB   | AWS-native NoSQL. Use LocalStack for local dev |

### Python Framework

| Framework | When to Use |
|-----------|-------------|
| FastAPI   | Default for APIs. Async, auto-docs, Pydantic integration |
| Flask     | Simpler APIs, server-rendered templates |

### UI Framework

| Framework | When to Use |
|-----------|-------------|
| Next.js   | Default for React. SSR, App Router, API routes |
| Vite      | Lighter SPA without SSR needs |

### Migration Tool

| Tool    | When to Use |
|---------|-------------|
| Alembic | Default for SQLAlchemy. Autogenerate, version control |
| Raw SQL | Simple schemas that rarely change |

## Anti-Patterns

- **Access keys in `.env`** — Never. Use `~/.aws` mount with profiles.
- **Running as root** — Always create and switch to a non-root user in Dockerfiles.
- **No healthchecks** — API starts before DB is ready, causing connection errors on first requests.
- **Hardcoded connection strings** — Use environment variables loaded via Pydantic Settings.
- **No migrations** — Manual SQL or raw `CREATE TABLE` in code. Use Alembic.
- **`sleep 10` instead of health polling** — Fragile. Use `pg_isready` loop or healthcheck condition.
- **Fallback defaults for required config** — `database_url: str = "sqlite:///local.db"` masks misconfiguration. Fail at startup.
- **Mounting node_modules from host** — Breaks native binaries built for different OS. Use anonymous volumes.
- **Committing `.env`** — Commit `.env.example` only. Gitignore `.env`.
- **Runtime dependency on reference files** — Seed scripts that parse external files (exam guides, topic lists) at runtime break when those files aren't mounted. Embed reference data directly in the seed script; external files are for generation, not runtime.
- **Manual migration/seed commands** — Running `docker compose exec api alembic upgrade head` manually after startup. Use the entrypoint to automate this on every container start.
- **Hardcoded server command in entrypoint** — Use `exec "$@"` to pass through the `CMD`/`command:` override, not a hardcoded `exec uvicorn ...`. This lets docker-compose override the server command (e.g., `--reload`) while still running migrations.

## Quick Reference

### Common Commands

| Command | Description |
|---------|-------------|
| `./setup.sh` | One-command bootstrap (first time) |
| `docker compose up -d` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose down -v` | Stop and destroy volumes (full reset) |
| `docker compose logs -f api` | Follow API logs |
| `docker compose build api` | Rebuild API after dependency changes |
| `docker compose up -d --build api` | Rebuild and restart API |
| `docker compose exec api bash` | Shell into API container |
| `docker compose exec db psql -U postgres` | PostgreSQL shell |
| `docker compose exec api alembic revision --autogenerate -m "msg"` | New migration |
| `docker compose exec api alembic upgrade head` | Apply migrations |

### Default Ports

| Service | Port |
|---------|------|
| UI      | 3000 |
| API     | 8000 |
| DB      | 5432 |

### Project Layout

```
project/
├── api/
│   ├── app/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── config.py         # Pydantic Settings
│   │   ├── database.py       # SQLAlchemy setup
│   │   ├── models.py         # ORM models
│   │   └── seed/             # Seed scripts + bundled data
│   │       ├── seed_database.py  # Idempotent seed (embedded reference data)
│   │       └── generated_data.json  # Build-time generated content
│   ├── alembic/              # Migration versions
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── requirements.txt
├── ui/
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── setup.sh
├── .env.example
└── .gitignore
```

## Template Files

Ready-to-adapt templates are available in `assets/templates/`:

| File | Purpose |
|------|---------|
| `docker-compose.yml` | 3-service orchestration with health checks and AWS mount |
| `setup.sh` | One-command bootstrap script |
| `env.example` | Environment variable template (no secrets) |
| `api.Dockerfile` | Python 3.11 with non-root user |
| `api.entrypoint.sh` | Migration + seed + server startup (`exec "$@"` pass-through) |
| `ui.Dockerfile` | Node 20 with npm dev server |

## References

| Topic | File | Key Patterns |
|-------|------|--------------|
| Docker Compose | `references/docker-compose-patterns.md` | Health checks, volumes, networking, AWS mounts, env vars |
| Setup Automation | `references/setup-automation.md` | Script structure, health polling, teardown, common commands |
| Config & Database | `references/config-and-database.md` | Pydantic Settings, SQLAlchemy pooling, Alembic, seeding, health endpoints |
