# Structured Logging & Trace Correlation

## 1. JSON Logging Setup

Container-based LLM applications must emit structured JSON logs to stdout. This enables log aggregation platforms (Datadog, Grafana Loki, CloudWatch) to parse, index, and query log fields.

### Base Configuration

```python
import os
import sys
import socket
import logging
from datetime import datetime, timezone
from pythonjsonlogger import jsonlogger

SERVICE_NAME = os.getenv('DD_SERVICE', 'my-service')
ENVIRONMENT = os.getenv('DD_ENV', os.getenv('ENVIRONMENT', 'development'))
VERSION = os.getenv('DD_VERSION', os.getenv('VERSION', '1.0.0'))
HOSTNAME = socket.gethostname()
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


def configure_logging(level: str = None) -> None:
    """Configure root logger — call ONCE at startup BEFORE other imports."""
    log_level = level or LOG_LEVEL

    handler = logging.StreamHandler(sys.stdout)  # stdout for containers
    handler.setFormatter(TracingJsonFormatter('%(timestamp)s %(level)s %(message)s'))

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()  # Prevent duplicate handlers
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ['opensearch', 'urllib3', 'botocore', 'boto3', 'httpx',
                   'RapidOCR', 'transformers', 'torch']:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger that inherits from the configured root."""
    return logging.getLogger(name)
```

### Key Design Decisions

- **stdout, not files** — containers capture stdout; the orchestration platform (K8s, ECS) routes it to the log pipeline
- **Root logger configuration** — all module loggers inherit formatting automatically
- **Clear handlers** — prevents duplicate log lines when `configure_logging()` is called during tests
- **Noisy logger suppression** — third-party libraries (botocore, urllib3, torch) generate verbose output that pollutes log search

## 2. Trace-Log Correlation

The critical feature: every log line includes `trace_id` and `span_id` from the active trace span. This enables clicking from a log line to its parent trace (and vice versa) in the observability platform.

### Datadog-Compatible Formatter

```python
class TracingJsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter with trace correlation and platform-compatible fields."""

    # Python log levels to Datadog-expected lowercase format
    LEVEL_MAP = {
        'DEBUG': 'debug',
        'INFO': 'info',
        'WARNING': 'warn',      # Datadog expects 'warn', not 'warning'
        'ERROR': 'error',
        'CRITICAL': 'critical',
    }

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)

        # Platform-expected field names
        log_record['level'] = self.LEVEL_MAP.get(record.levelname, record.levelname.lower())
        log_record.pop('levelname', None)  # Remove Python's uppercase levelname

        # ISO 8601 timestamp
        log_record['timestamp'] = datetime.fromtimestamp(
            record.created, tz=timezone.utc
        ).isoformat()

        # Unified service tagging (Datadog convention, but useful everywhere)
        log_record['service'] = SERVICE_NAME
        log_record['env'] = ENVIRONMENT
        log_record['version'] = VERSION
        log_record['hostname'] = HOSTNAME
        log_record['logger'] = record.name

        # Trace correlation
        self._add_trace_context(log_record)

    def _add_trace_context(self, log_record):
        """Inject trace_id and span_id from the active span."""
        try:
            from ddtrace import tracer
            span = tracer.current_span()
            if span:
                log_record['dd.trace_id'] = str(span.trace_id)
                log_record['dd.span_id'] = str(span.span_id)
        except ImportError:
            pass
        except Exception:
            pass
```

### Generic OpenTelemetry Alternative

For platforms other than Datadog (Grafana, Honeycomb, Jaeger), use the standard OTEL trace context:

```python
def _add_trace_context(self, log_record):
    """Generic OTEL trace correlation — works with any OTEL-compatible platform."""
    try:
        from opentelemetry import trace
        span = trace.get_current_span()
        if span and span.is_recording():
            context = span.get_span_context()
            log_record['trace_id'] = format(context.trace_id, '032x')
            log_record['span_id'] = format(context.span_id, '016x')
    except ImportError:
        pass
    except Exception:
        pass
```

### Choosing Between Formatters

| Platform | Trace Fields | Level Format |
|----------|-------------|-------------|
| Datadog | `dd.trace_id`, `dd.span_id` | `warn` (lowercase) |
| Grafana / OTEL | `trace_id`, `span_id` (hex) | `WARNING` (standard) |
| CloudWatch | Either works | Either works |

Both formatters are safe to use together — the `try/except ImportError` ensures only the available one activates.

## 3. Log Output Format

Every log line becomes a structured JSON object:

```json
{
  "timestamp": "2026-02-10T15:30:45.123456+00:00",
  "level": "info",
  "message": "Extraction complete for field: roofType",
  "service": "my-service",
  "env": "production",
  "version": "2.1.0",
  "hostname": "pod-abc123",
  "logger": "domain.extraction.batch_extractor",
  "dd.trace_id": "1234567890123456789",
  "dd.span_id": "9876543210987654321",
  "field_name": "roofType",
  "confidence": 0.92,
  "chunks_count": 8
}
```

This enables:
- **Filtering** by `service`, `env`, `field_name`, `logger`
- **Correlation** by clicking `dd.trace_id` to jump to the trace
- **Aggregation** by `confidence` ranges, `chunks_count` distributions
- **Alerting** on `level: error` with `service: my-service`

## 4. Unified Service Tagging

Three fields that must be consistent across logs, traces, and metrics:

| Field | Source | Purpose |
|-------|--------|---------|
| `service` | `DD_SERVICE` env var | Groups all telemetry for one service |
| `env` | `DD_ENV` env var | Separates dev/staging/production |
| `version` | `DD_VERSION` env var | Tracks behavior changes across deploys |

These three tags power the unified service view in Datadog (and similar features in other platforms). Set them once in environment variables and inject into every log record.

## 5. What to Log in LLM Applications

### Include

```python
logger.info("extraction_complete", extra={
    "document_id": doc_id,
    "field_name": field_name,
    "model": "anthropic.claude-sonnet",
    "input_tokens": 8500,
    "output_tokens": 120,
    "latency_ms": 1500,
    "confidence": 0.92,
    "chunks_count": 8,
    "aggregation_method": "SINGLE",
    "extractions_count": 2,
    "final_value": final_value  # Only if not PII
})
```

**Essential fields for LLM observability:**
- `document_id` / `request_id` — correlate across operations
- `field_name` / `query` — what was being extracted/queried
- `model` — which LLM model was used
- `input_tokens`, `output_tokens` — cost tracking
- `latency_ms` — performance monitoring
- `confidence` — extraction quality signal
- `chunks_count` — retrieval volume

### Avoid

- **Full prompt text** — large, may contain PII, inflates log storage cost
- **Full LLM response text** — same concerns as prompts
- **Raw embeddings** — very large arrays with no diagnostic value in logs
- **Sensitive user data** — PII, credentials, personal information
- **High-cardinality identifiers as log fields** — user IDs as indexed fields explode cardinality; use them as part of the message instead

### Logging Evaluation Scores

Log evaluation submissions at `debug` level for development and `info` for key metrics:

```python
# Debug: all evaluations (verbose, useful in dev)
logger.debug(f"Evaluation: context_relevance={relevance:.3f} ({len(chunks)} chunks)")

# Info: aggregated results (useful in production dashboards)
logger.info(
    "field_extraction_result",
    extra={
        "field_name": field_name,
        "confidence": overall_confidence,
        "semantic_validation": validation_result,
        "agreement_pattern": agreement,
    }
)
```

## 6. Noisy Logger Suppression

Third-party libraries generate verbose logs that clutter search and inflate cost:

```python
# In configure_logging()
logging.getLogger('opensearch').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('botocore').setLevel(logging.WARNING)
logging.getLogger('boto3').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

# GPU/ML libraries (especially noisy)
logging.getLogger('RapidOCR').setLevel(logging.ERROR)    # Plain text breaks JSON parsing
logging.getLogger('transformers').setLevel(logging.WARNING)
logging.getLogger('torch').setLevel(logging.WARNING)
```

**Why RapidOCR is set to ERROR:** Some libraries emit non-JSON plain text to stdout, which breaks structured log parsing. Setting them to ERROR prevents this while still capturing actual errors.
