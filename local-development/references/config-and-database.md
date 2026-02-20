# Configuration & Database Patterns

## Pydantic Settings (Fail-Fast Configuration)

Use `pydantic-settings` to load and validate environment variables at startup. No fallback values for required settings — the application must fail immediately if configuration is incomplete.

### Pattern

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required — raises ValidationError if missing
    database_url: str

    # Required for AWS
    aws_default_region: str
    aws_profile: str | None = None  # Optional, uses default credential chain

    # Application settings with sensible defaults
    debug: bool = False


def get_settings() -> Settings:
    """Raises ValidationError if required environment variables are missing."""
    return Settings()
```

### Key Decisions

- **Required fields**: No default value → `ValidationError` at startup if missing
- **Optional fields**: Use `str | None = None` for truly optional settings
- **Defaults**: Only for non-critical settings (`debug`, `log_level`)
- **`extra="ignore"`**: Silently skip unknown env vars (prevents noise)
- **`.env` support**: Reads `.env` file automatically, environment variables override

### FastAPI Integration

```python
from typing import Annotated
from fastapi import Depends

SettingsDep = Annotated[Settings, Depends(get_settings)]
```

## SQLAlchemy Engine & Connection Pooling

### Engine Configuration

```python
from sqlalchemy import create_engine

def get_engine(settings: Settings):
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,   # Validate connections before use
        pool_size=5,          # Maintained connections
        max_overflow=10,      # Extra connections under load
    )
```

- **`pool_pre_ping=True`**: Detects stale connections (essential for containerized DBs that restart)
- **`pool_size=5`**: Adequate for local development; increase for production
- **`max_overflow=10`**: Temporary connections beyond pool_size during bursts

### Session Factory

```python
from sqlalchemy.orm import Session, sessionmaker

def get_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = get_engine(settings)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
```

### Session Context Manager

```python
from collections.abc import Generator
from contextlib import contextmanager

@contextmanager
def get_db_session(settings: Settings) -> Generator[Session, None, None]:
    session_factory = get_session_factory(settings)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

Explicit rollback on exception, explicit close in finally. No silent error swallowing.

### FastAPI Dependency

```python
from typing import Annotated
from fastapi import Depends

def get_db(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Generator[Session, None, None]:
    with get_db_session(settings) as session:
        yield session

DbSession = Annotated[Session, Depends(get_db)]
```

Usage in routes:

```python
@router.get("/items")
async def list_items(db: DbSession):
    return db.query(Item).all()
```

## Alembic Migration Patterns

### Initialization

```bash
alembic init alembic
```

### Environment Configuration (`alembic/env.py`)

```python
import os
from alembic import context
from sqlalchemy import create_engine

# Load DATABASE_URL from environment — fail if missing
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL environment variable is required")

def run_migrations_online():
    engine = create_engine(database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

### Entrypoint Integration

Run migrations and seeding before starting the application server. Use `ENTRYPOINT` + `CMD` so docker-compose `command:` can override the server command while still running migrations.

**Dockerfile:**
```dockerfile
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**entrypoint.sh:**
```sh
#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Seeding database..."
python -m app.infrastructure.seed.seed_database

echo "Starting application..."
exec "$@"
```

Key patterns:
- **`exec "$@"`** passes through the `CMD` (or docker-compose `command:` override) as the final process. This replaces the shell with the actual server, ensuring proper signal handling (SIGTERM reaches uvicorn directly).
- **docker-compose override**: `command: ["uvicorn", "...", "--reload"]` replaces `CMD` but the entrypoint still runs migrations + seed first.
- **`/bin/sh`** not `/bin/bash` — slim images may not have bash.

### Database Seeding on Startup

Seed scripts run after migrations in the entrypoint. They must be **idempotent** — safe to run on every container start without duplicating data.

**Pattern: Clear-and-reseed (simple, idempotent)**
```python
"""Seed script — runs on every container start."""

from app.infrastructure.database import SessionLocal
from app.infrastructure import models

# Embed reference data directly — no external file dependencies at runtime.
# Reference files (exam guides, topic lists) are for generation only.
DOMAINS = [
    {"id": 1, "name": "Domain 1: Core Concepts", "weight": 30.0},
    {"id": 2, "name": "Domain 2: Implementation", "weight": 40.0},
    {"id": 3, "name": "Domain 3: Operations", "weight": 30.0},
]

def clear_existing_data(db):
    """Delete in reverse FK dependency order."""
    db.query(models.AnswerModel).delete()
    db.query(models.QuestionModel).delete()
    db.query(models.DomainModel).delete()
    db.commit()

def seed_domains(db):
    for domain in DOMAINS:
        db.add(models.DomainModel(**domain))
    db.commit()

def seed_questions(db):
    """Load from bundled JSON (generated at build time, not runtime)."""
    import json
    from pathlib import Path
    questions_file = Path(__file__).parent / "generated_data.json"
    with open(questions_file) as f:
        data = json.load(f)
    for q in data["questions"]:
        db.add(models.QuestionModel(**q))
    db.commit()

def main():
    db = SessionLocal()
    try:
        clear_existing_data(db)
        seed_domains(db)
        seed_questions(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
```

**Key principles:**
- **Embed reference data** — Domain names, topic structures, and other reference data that was derived from external files (exam guides, specifications) should be hardcoded in the seed script. The app should not depend on reference files at runtime.
- **Bundle generated data** — Generated JSON files (questions, content) are committed to the repo and copied into the Docker image. They are build artifacts, not runtime dependencies.
- **Synchronous SQLAlchemy** — Seed scripts use synchronous `SessionLocal` (psycopg2), not the async session used by FastAPI. Add both drivers to dependencies.
- **Clear-then-insert** — Delete all data in reverse FK order, then re-insert. Simple and idempotent. Acceptable for dev environments and applications with static seed data.
- **Verify after seeding** — Assert expected counts to catch data corruption early.

### Migration Commands

```bash
# Create a new migration
docker compose exec api alembic revision --autogenerate -m "add users table"

# Apply all pending migrations
docker compose exec api alembic upgrade head

# Rollback one migration
docker compose exec api alembic downgrade -1

# Show current migration state
docker compose exec api alembic current
```

## Health Check Patterns

### API Health Endpoint

```python
import boto3
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check():
    settings = get_settings()
    status = {"database": "unknown", "aws": "unknown"}

    # Database check
    try:
        with get_db_session(settings) as session:
            session.execute(text("SELECT 1"))
        status["database"] = "healthy"
    except Exception as e:
        status["database"] = f"unhealthy: {e}"

    # AWS check (if applicable)
    try:
        client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_default_region,
        )
        status["aws"] = "healthy"
    except Exception as e:
        status["aws"] = f"unhealthy: {e}"

    overall = "healthy" if all(v == "healthy" for v in status.values()) else "degraded"
    return {"status": overall, "services": status}
```

## ORM Model Pattern

```python
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```
