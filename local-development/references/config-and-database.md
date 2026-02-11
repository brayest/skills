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

Run migrations before starting the application server:

```bash
#!/bin/bash
set -e

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

`exec` replaces the shell process with uvicorn, ensuring proper signal handling (SIGTERM reaches uvicorn directly, not the bash wrapper).

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
