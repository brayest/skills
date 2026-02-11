# Observability Architecture

## 1. Dual-Stack Tracing Model

LLM applications operate at two levels that require different instrumentation:

```
┌─────────────────────────────────────────────────────────┐
│                    Application Code                      │
│                                                          │
│   @workflow / @task / @agent decorators                  │
│   Evaluation submissions                                 │
│   Structured JSON logging                                │
└──────────┬──────────────────┬───────────────┬───────────┘
           │                  │               │
    ┌──────▼──────┐   ┌──────▼──────┐  ┌─────▼──────┐
    │  Provider    │   │  Framework  │  │  Structured │
    │  Tracer      │   │  Tracer     │  │  Logs       │
    │             │   │             │  │             │
    │ Patches:    │   │ Instruments:│  │ Fields:     │
    │ - boto3     │   │ - LlamaIndex│  │ - trace_id  │
    │ - botocore  │   │ - LangChain │  │ - span_id   │
    │ - httpx     │   │ - Agents    │  │ - service   │
    │ - requests  │   │ - Retrievers│  │ - env       │
    └──────┬──────┘   └──────┬──────┘  └─────┬──────┘
           │                  │               │
     APM Agent           OTLP Receiver    Log Pipeline
           │                  │               │
           └──────────┬───────┘               │
                      ▼                       ▼
              Observability Platform (unified via trace_id)
```

### Why Two Tracers?

| Layer | Tracer | What It Captures | How |
|-------|--------|-----------------|-----|
| **Provider** | ddtrace, OpenAI SDK instrumentation | Raw LLM API calls: tokens, latency, model_id, errors | Monkey-patches SDK clients (boto3, httpx) at import time |
| **Framework** | OpenLLMetry (Traceloop SDK) | Orchestration: agent loops, retriever calls, query engines, chains | Auto-instruments LlamaIndex/LangChain via OpenTelemetry |

Neither layer alone covers the full stack. The provider tracer captures individual LLM calls but misses orchestration context. The framework tracer captures the workflow but misses raw API details (token counts, model parameters). Together they produce a single correlated trace.

## 2. Initialization Order

**This is the single most critical implementation detail.** Both tracers work by monkey-patching target libraries at the Python module level. If the target library (boto3, LlamaIndex) is imported before the tracer initializes, the patching has no effect — and no error is raised.

### Correct Order

```python
# main.py — initialization sequence

# Step 1: Configure logging FIRST (before any logger is created)
from myapp.logging_config import configure_logging
configure_logging()

# Step 2: Initialize provider tracer (patches boto3, botocore, httpx)
from myapp.observability import init_observability
init_observability(
    service_name="my-service",
    ml_app_name="my-ml-app"
)

# Step 3: NOW import libraries that will be auto-patched
import boto3
from llama_index.core import VectorStoreIndex
from myapp.routes import router
```

### Anti-Pattern: Importing Before Initializing

```python
# WRONG — boto3 imported before patching
import boto3                          # Already loaded unpatched
from myapp.observability import init_observability
init_observability(...)               # Too late — patching has no effect
```

This fails silently. The application works, but no LLM calls appear in traces. This is one of the hardest bugs to debug because there is no error.

## 3. What Gets Auto-Instrumented

| Library | Patching Source | What Is Captured |
|---------|----------------|-----------------|
| boto3 / botocore | ddtrace `patch(botocore=True)` | Bedrock InvokeModel, Converse; S3, SQS, DynamoDB operations |
| httpx | ddtrace `patch(httpx=True)` | HTTP client calls with method, URL, status |
| requests / urllib3 | ddtrace (built-in) | HTTP calls — **but may conflict with AWS SigV4** (see production operations) |
| LlamaIndex | OpenLLMetry (Traceloop) | Query engines, retrievers, node postprocessors, agents |
| LangChain | OpenLLMetry (Traceloop) | Chain execution, LLM calls, tool usage, agent loops |
| OpenAI / Anthropic SDKs | OpenLLMetry (Traceloop) | Direct API calls, streaming, tool use |

## 4. Feature Flag Pattern

Observability must be opt-in and gated behind a module-level flag. This prevents errors in environments without a tracing agent (local dev, CI/CD, tests).

```python
"""
Observability initialization module.

Combines provider tracer (ddtrace) + framework tracer (OpenLLMetry).
Disabled by default — set DD_LLMOBS_ENABLED=1 to enable.
"""
import os
import logging

logger = logging.getLogger(__name__)

_OBSERVABILITY_ENABLED = False


def is_observability_enabled() -> bool:
    """Check before any evaluation or span operations."""
    return _OBSERVABILITY_ENABLED


def init_observability(service_name: str, ml_app_name: str) -> None:
    """Initialize hybrid observability stack with opt-in control."""
    global _OBSERVABILITY_ENABLED

    if os.getenv("DD_LLMOBS_ENABLED", "0") != "1":
        logger.info("LLM Observability disabled (set DD_LLMOBS_ENABLED=1 to enable)")
        return

    _OBSERVABILITY_ENABLED = True
    _init_provider_tracer(service_name, ml_app_name)
    _init_framework_tracer(service_name)


def _init_provider_tracer(service_name: str, ml_app_name: str) -> None:
    """Initialize ddtrace — patches boto3, botocore, httpx."""
    try:
        from ddtrace import config, patch
        from ddtrace.llmobs import LLMObs

        patch(botocore=True, httpx=True)
        config.service = service_name

        agentless = os.getenv("DD_LLMOBS_AGENTLESS_ENABLED", "0") == "1"
        LLMObs.enable(ml_app=ml_app_name, agentless_enabled=agentless)

        logger.info(f"Provider tracer enabled: service={service_name}, ml_app={ml_app_name}")
    except ImportError:
        logger.warning("ddtrace not installed — provider auto-instrumentation disabled")
    except Exception as e:
        logger.error(f"Failed to initialize provider tracer: {e}")


def _init_framework_tracer(service_name: str) -> None:
    """Initialize OpenLLMetry — patches LlamaIndex, LangChain."""
    try:
        from traceloop.sdk import Traceloop
        from traceloop.sdk.instruments import Instruments

        base_url = os.getenv("TRACELOOP_BASE_URL")
        if not base_url:
            logger.info("TRACELOOP_BASE_URL not set — framework tracing disabled")
            return

        # Block HTTP client instrumentation to avoid conflicts with
        # AWS SigV4 signature generation (OpenSearch, S3, etc.)
        blocked = {Instruments.REQUESTS, Instruments.URLLIB3}

        Traceloop.init(
            app_name=service_name,
            disable_batch=False,
            block_instruments=blocked
        )

        logger.info(f"Framework tracer enabled: app={service_name}, endpoint={base_url}")
    except ImportError:
        logger.warning("traceloop-sdk not installed — framework tracing disabled")
    except Exception as e:
        logger.error(f"Failed to initialize framework tracer: {e}")
```

### Key Design Decisions

- **Default disabled** (`DD_LLMOBS_ENABLED` defaults to `"0"`) — opt-in, not opt-out
- **Module-level flag** — checked via `is_observability_enabled()` instead of re-reading env vars on every call
- **Graceful ImportError handling** — service runs identically with or without tracing dependencies installed
- **Blocking HTTP instrumentations** — `REQUESTS` and `URLLIB3` blocked to prevent AWS SigV4 conflicts (see `references/06-production-operations.md`)

## 5. Data Flow

```
Application Code
    │
    ├─ @workflow / @task decorators create spans
    │    └─ Evaluations attached to spans via submit_evaluation()
    │
    ├─ boto3.client("bedrock-runtime").converse()
    │    └─ Auto-traced by ddtrace: tokens, model_id, latency
    │
    ├─ LlamaIndex retriever.retrieve()
    │    └─ Auto-traced by OpenLLMetry: query, results, relevance
    │
    └─ logger.info("extraction_complete", extra={...})
         └─ JSON log with dd.trace_id + dd.span_id
              └─ Correlated with traces in observability platform
```

## 6. Dependencies

```
# Provider tracer (Datadog APM + LLM Observability)
ddtrace>=3.9.0

# Framework tracer (OpenLLMetry for LlamaIndex/LangChain)
traceloop-sdk>=0.50.0
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0

# Structured logging
python-json-logger>=2.0.7
```
