# Production Engineering Patterns for Python Applications

## Structured JSON Logging

### Overview

Structured logging outputs logs as JSON objects instead of plain text, enabling powerful querying, filtering, and correlation in log aggregation systems (DataDog, CloudWatch, Elasticsearch).

### Setup with python-json-logger

**Install:**
```bash
pip install python-json-logger
```

**Basic Configuration:**

```python
# shared/logging_config.py
import os
import sys
import socket
import logging
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger

# Configuration from environment
SERVICE_NAME = os.getenv('SERVICE_NAME', 'my-service')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
VERSION = os.getenv('VERSION', '1.0.0')
HOSTNAME = socket.gethostname()
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with service context."""

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO 8601
        log_record['timestamp'] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()

        # Add service context
        log_record['service'] = SERVICE_NAME
        log_record['environment'] = ENVIRONMENT
        log_record['version'] = VERSION
        log_record['hostname'] = HOSTNAME
        log_record['logger'] = record.name

        # Normalize log level
        log_record['level'] = record.levelname.lower()


def configure_logging(level: str = None):
    """Configure root logger with JSON formatting."""
    log_level = level or LOG_LEVEL

    # Create handler outputting to stdout
    handler = logging.StreamHandler(sys.stdout)

    # Use custom formatter
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(level)s %(message)s'
    )
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()  # Remove existing handlers
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)
```

**Usage:**

```python
# main.py - Configure ONCE at startup
from shared.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

# Any module
from shared.logging_config import get_logger
logger = get_logger(__name__)

logger.info("User registered", extra={
    'user_id': '123',
    'email': 'user@example.com'
})
```

**Output:**

```json
{
  "timestamp": "2026-02-10T15:30:45.123Z",
  "level": "info",
  "message": "User registered",
  "service": "my-service",
  "environment": "production",
  "version": "1.2.3",
  "hostname": "pod-abc123",
  "logger": "app.users",
  "user_id": "123",
  "email": "user@example.com"
}
```

### Benefits

- **Structured querying:** Search by `user_id`, `environment`, etc.
- **Performance analysis:** Filter by `duration_ms > 1000`
- **Environment separation:** Filter by `environment:production`
- **Correlation:** Link logs to traces via correlation IDs

---

## Distributed Tracing Integration

### Overview

Distributed tracing tracks requests across multiple services, showing complete request flow, latencies, and dependencies.

### DataDog APM Integration

**Install:**
```bash
pip install ddtrace
```

**Initialize Tracing:**

```python
# shared/observability.py
import os
from ddtrace import tracer, config

def init_observability(service_name: str, ml_app_name: str = None):
    """
    Initialize DataDog tracing.

    MUST be called BEFORE importing libraries to be auto-instrumented
    (boto3, requests, aiohttp, etc.)
    """
    # Configure tracer
    config.service = service_name
    config.env = os.getenv('DD_ENV', 'development')
    config.version = os.getenv('DD_VERSION', '1.0.0')

    # Enable specific integrations
    config.boto = {'service_name': f'{service_name}-aws'}
    config.aiohttp = {'trace_query_string': True}

    # LLM observability (if using LLM libraries)
    if ml_app_name:
        from traceloop.sdk import Traceloop
        Traceloop.init(
            app_name=ml_app_name,
            disable_batch=True
        )

    return tracer


def flush_observability():
    """Flush traces before shutdown."""
    try:
        from ddtrace import tracer
        tracer.shutdown(timeout=5)
    except Exception:
        pass
```

**Usage in main.py:**

```python
# main.py
# 1. Configure logging FIRST
from shared.logging_config import configure_logging
configure_logging()

# 2. Initialize tracing BEFORE other imports
from shared.observability import init_observability
init_observability(service_name="my-service")

# 3. NOW import libraries (will be auto-instrumented)
import boto3
import aiohttp
from llama_index import ...

# Your application code
```

### Trace Correlation in Logs

```python
# shared/logging_config.py
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Add trace correlation
        self._add_trace_context(log_record)

    def _add_trace_context(self, log_record):
        """Add DataDog trace correlation fields."""
        try:
            from ddtrace import tracer
            span = tracer.current_span()
            if span:
                log_record['dd.trace_id'] = str(span.trace_id)
                log_record['dd.span_id'] = str(span.span_id)
        except (ImportError, Exception):
            pass
```

Now logs automatically include trace IDs for correlation!

### Custom Spans

```python
from ddtrace import tracer

@tracer.wrap(service="my-service", resource="process_user")
async def process_user(user_id: str):
    """Process user with custom span."""
    # Automatically traced
    pass

# Or manual spans
async def complex_operation():
    with tracer.trace("database.query", service="my-service"):
        result = await db.execute_query()

    with tracer.trace("external.api", service="my-service"):
        data = await api_client.fetch()

    return result
```

---

## Fail-Fast Error Handling

### Philosophy

Errors should fail immediately and loudly, never silently. No default fallbacks that mask problems.

### Pattern: Explicit Validation

```python
# ❌ BAD - Silent fallback
database_url = os.getenv('DATABASE_URL') or 'sqlite:///:memory:'

# ✅ GOOD - Fail fast
database_url = os.getenv('DATABASE_URL')
if not database_url:
    raise ValueError("DATABASE_URL environment variable is required")
```

### Pattern: No Try-Except-Pass

```python
# ❌ BAD - Swallows errors
try:
    result = process_data()
except Exception:
    pass  # Silent failure!

# ✅ GOOD - Explicit error handling
try:
    result = process_data()
except ValueError as e:
    logger.error(f"Invalid data: {e}")
    raise  # Re-raise after logging
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

### Pattern: Validation at Boundaries

```python
from pydantic import BaseModel, Field, field_validator

class UserInput(BaseModel):
    """Validate input at system boundaries."""

    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    age: int = Field(..., ge=0, le=150)

    @field_validator('email')
    @classmethod
    def validate_email_domain(cls, v):
        """Additional email validation."""
        if not v.endswith(('@company.com', '@partner.com')):
            raise ValueError("Email must be from allowed domain")
        return v

# Usage
def create_user(data: dict):
    """Validation fails fast if data invalid."""
    user_input = UserInput(**data)  # Raises ValidationError if invalid
    # Continue with validated data
```

### Error Publishing Pattern

For microservices, publish errors to dedicated error topic/queue for monitoring:

```python
async def handle_error(
    original_message: dict,
    error_type: str,
    error_msg: str,
    stack_trace: str = None
):
    """Publish error for centralized monitoring."""
    error_event = {
        "original_message": original_message,
        "error_type": error_type,
        "error_message": error_msg,
        "stack_trace": stack_trace,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": SERVICE_NAME,
        "environment": ENVIRONMENT
    }

    # Publish to error topic/queue
    await error_publisher.publish(error_event)

    # Also log
    logger.error(f"Error published: {error_type} - {error_msg}")
```

---

## Configuration Management

### 12-Factor App Configuration

All configuration via environment variables, never hardcoded.

**Configuration Class:**

```python
# shared/config.py
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment."""

    # Service
    service_name: str = Field(default="my-service", alias="SERVICE_NAME")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")  # Required
    database_pool_size: int = Field(default=10, alias="DATABASE_POOL_SIZE")

    # AWS
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    s3_bucket: str = Field(..., alias="S3_BUCKET")  # Required

    # Optional features
    enable_tracing: bool = Field(default=True, alias="ENABLE_TRACING")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    class Config:
        case_sensitive = False
        env_file = ".env"  # Load from .env file in development


# Create singleton
settings = Settings()
```

**Usage:**

```python
from shared.config import settings

# Use throughout application
database = Database(settings.database_url)
s3_client = boto3.client('s3', region_name=settings.aws_region)

if settings.enable_tracing:
    init_observability()
```

### HashiCorp Vault Integration

For secrets management:

```python
# infrastructure/config/vault_client.py
import os
import hvac

def initialize_vault_secrets():
    """Load secrets from Vault into environment."""
    vault_addr = os.getenv('VAULT_ADDR')
    vault_role = os.getenv('VAULT_ROLE')
    vault_path = os.getenv('VAULT_PATH')

    if not vault_addr:
        return True  # Vault disabled

    # Authenticate with Kubernetes service account
    with open('/var/run/secrets/kubernetes.io/serviceaccount/token') as f:
        jwt = f.read()

    client = hvac.Client(url=vault_addr)
    auth_response = client.auth.kubernetes.login(
        role=vault_role,
        jwt=jwt
    )

    # Fetch secrets
    secret = client.secrets.kv.v2.read_secret_version(
        path=vault_path
    )

    # Inject into environment
    for key, value in secret['data']['data'].items():
        os.environ[key] = value

    return True
```

**Usage in main:**

```python
# main.py
async def main():
    # 1. Initialize Vault secrets FIRST
    from infrastructure.config.vault_client import initialize_vault_secrets
    initialize_vault_secrets()

    # 2. NOW load settings (secrets available in environment)
    from shared.config import settings

    # 3. Start application
    await app.start()
```

---

## Resource Cleanup Patterns

### Proper Cleanup Sequence

```python
class Application:
    def __init__(self):
        self.database = None
        self.message_queue = None
        self.thread_pool = None
        self.tasks = set()

    async def start(self):
        """Start application."""
        # Initialize resources
        self.database = await Database.connect()
        self.message_queue = MessageQueue()
        self.thread_pool = ThreadPoolExecutor(max_workers=10)

        # Run application
        try:
            await self.run()
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Cleanup in proper order."""
        logger.info("Starting graceful shutdown...")

        # 1. Complete in-flight work
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        # 2. Flush observability data BEFORE closing connections
        from shared.observability import flush_observability
        flush_observability()

        # 3. Close application connections
        if self.message_queue:
            await self.message_queue.close()

        if self.database:
            await self.database.disconnect()

        # 4. Shutdown thread pools
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)

        logger.info("Shutdown complete")
```

### Context Manager Pattern

```python
class ManagedResource:
    """Resource with automatic cleanup."""

    async def __aenter__(self):
        """Acquire resource."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release resource."""
        await self.disconnect()
        return False  # Don't suppress exceptions

# Usage
async def process():
    async with ManagedResource() as resource:
        await resource.do_work()
    # Automatically cleaned up
```

---

## Observability Best Practices

### Health Check Endpoints

```python
# For FastAPI
from fastapi import APIRouter, status

router = APIRouter()

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": VERSION
    }

@router.get("/health/ready")
async def readiness_check():
    """Detailed readiness check."""
    checks = {
        "database": await check_database(),
        "message_queue": await check_message_queue(),
        "cache": await check_cache()
    }

    all_healthy = all(checks.values())
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks
    }
```

### Performance Metrics

```python
import time
from functools import wraps

def track_performance(operation_name: str):
    """Decorator to track operation performance."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()

            try:
                result = await func(*args, **kwargs)

                duration_ms = (time.time() - start) * 1000
                logger.info(
                    f"Operation completed: {operation_name}",
                    extra={
                        "operation": operation_name,
                        "duration_ms": duration_ms,
                        "success": True
                    }
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                logger.error(
                    f"Operation failed: {operation_name}",
                    extra={
                        "operation": operation_name,
                        "duration_ms": duration_ms,
                        "success": False,
                        "error": str(e)
                    }
                )
                raise

        return wrapper
    return decorator

# Usage
@track_performance("user_registration")
async def register_user(email: str):
    # Automatically tracked
    pass
```

### Custom Metrics

```python
from datadog import statsd

# Increment counter
statsd.increment('user.registered', tags=[f'environment:{ENVIRONMENT}'])

# Track duration
with statsd.timed('database.query.duration', tags=['query:users']):
    await database.execute_query()

# Gauge for current value
statsd.gauge('queue.depth', message_queue.qsize())
```

---

## Security Best Practices

### Never Log Sensitive Data

```python
# ❌ BAD - Logs password
logger.info(f"User login: {email}, password: {password}")

# ✅ GOOD - Mask sensitive data
logger.info(f"User login: {email}")
```

### Input Validation

```python
from pydantic import BaseModel, field_validator

class APIRequest(BaseModel):
    """Validate all API inputs."""

    email: str
    age: int

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Prevent injection attacks."""
        if '<' in v or '>' in v or ';' in v:
            raise ValueError("Invalid email format")
        return v.lower()
```

### Rate Limiting

```python
from datetime import datetime, timedelta
from collections import defaultdict

class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Remove old requests
        self.requests[key] = [
            ts for ts in self.requests[key]
            if ts > cutoff
        ]

        # Check limit
        if len(self.requests[key]) >= self.max_requests:
            return False

        # Record request
        self.requests[key].append(now)
        return True

# Usage
rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

async def api_endpoint(user_id: str):
    if not rate_limiter.is_allowed(user_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    # Process request
```

---

## Production Checklist

### Before Deploying to Production

- [ ] **Logging configured** - Structured JSON logs to stdout
- [ ] **Tracing enabled** - DataDog APM or equivalent
- [ ] **Health checks** - `/health` and `/health/ready` endpoints
- [ ] **Graceful shutdown** - Signal handlers and cleanup
- [ ] **Error handling** - Fail-fast, no silent failures
- [ ] **Configuration** - All config via environment variables
- [ ] **Secrets management** - Vault or equivalent, no hardcoded secrets
- [ ] **Resource cleanup** - Proper shutdown sequence
- [ ] **Input validation** - Validate at boundaries with Pydantic
- [ ] **Rate limiting** - Protect against abuse
- [ ] **Monitoring** - Metrics and alerts configured
- [ ] **Security review** - No sensitive data in logs
- [ ] **Performance testing** - Load tested for expected traffic
- [ ] **Documentation** - README with setup and deployment instructions
