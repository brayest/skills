# Production Operations

## 1. Graceful Shutdown & Flush Order

Evaluations and spans are buffered in memory. If the process exits without flushing, pending observability data is lost.

### Flush Function

```python
def flush_observability() -> None:
    """Flush all observability data — call during graceful shutdown."""
    if not _OBSERVABILITY_ENABLED:
        return

    # Step 1: Flush LLMObs evaluations and spans
    try:
        from ddtrace.llmobs import LLMObs
        LLMObs.flush()
        logger.info("LLMObs flushed successfully")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"LLMObs flush failed: {e}")

    # Step 2: Shutdown ddtrace tracer with timeout
    try:
        from ddtrace import tracer
        tracer.shutdown(timeout=5)
        logger.info("ddtrace tracer shutdown complete")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Tracer shutdown failed: {e}")
```

### Shutdown Sequence

The critical ordering: flush observability FIRST (while network is still available), then close connections.

```python
async def cleanup(self) -> None:
    """Application shutdown — order matters."""
    # 1. Flush observability (needs network to send data)
    flush_observability()

    # 2. Close message consumers
    if self.consumer:
        self.consumer.close()

    # 3. Flush message producers (send remaining messages)
    if self.producer:
        self.producer.flush(timeout=10)

    # 4. Close database connections
    if self.db_pool:
        await self.db_pool.close()
```

**Why this order:**
- `flush_observability()` sends buffered spans and evaluations to the Datadog Agent over the network
- If Kafka/DB connections close first, the network stack may be partially torn down
- Producer flush after observability ensures any error spans from the flush are captured

### Signal Handler Registration

```python
import signal

def handle_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT gracefully."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    flush_observability()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)
```

## 2. Noise Sampling

### Kafka Polling

**Problem:** Kafka consumers poll continuously (every 100ms–1s). Each poll generates a trace span, creating massive volumes of low-value traces that inflate storage cost.

**Solution:** Sample `kafka.consume` at 1% while keeping all business logic traces at 100%:

```yaml
DD_TRACE_SAMPLING_RULES: '[{"resource":"kafka.consume","sample_rate":0.01}]'
```

For multiple noisy resources:
```yaml
DD_TRACE_SAMPLING_RULES: '[{"resource":"kafka.consume","sample_rate":0.01},{"resource":"sqs.receivemessage","sample_rate":0.01}]'
```

### Health Check Endpoints

Health check probes generate traces every 10–30 seconds. These can be excluded entirely:

```yaml
DD_TRACE_SAMPLING_RULES: '[{"resource":"GET /health","sample_rate":0.0}]'
```

### What NOT to Sample

Never reduce sampling for:
- LLM extraction workflows (the core business logic)
- Error traces (DD automatically keeps 100% of errors)
- Evaluation submissions (these are the quality metrics)

## 3. Cost Optimization

### Evaluation Cost

| Cost Factor | Strategy |
|------------|---------|
| LLM-based evaluation calls | Hybrid recall: heuristic first, LLM only when heuristic < 0.7 (~20% of requests) |
| Trace volume | Sampling rules for high-frequency polling operations |
| Log volume | Log level management by environment |
| Span tag cardinality | Avoid high-cardinality tags (user IDs, request IDs as indexed tags) |

### Log Volume by Environment

| Logger | Development | Staging | Production |
|--------|------------|---------|------------|
| Application | DEBUG | INFO | INFO |
| Evaluations | DEBUG | INFO | INFO |
| botocore | WARNING | WARNING | WARNING |
| opensearch | WARNING | WARNING | WARNING |
| urllib3 | WARNING | WARNING | WARNING |
| RapidOCR | ERROR | ERROR | ERROR |

### Span Tag Cardinality

**Safe tags** (low cardinality): `service`, `env`, `version`, `model`, `field_name`, `aggregation_method`

**Avoid as tags** (high cardinality): `user_id`, `document_id`, `request_id`, `session_id`

High-cardinality values can go into span metadata/attributes (searchable but not indexed as metric dimensions).

## 4. Conflict Workarounds

### AWS SigV4 + HTTP Instrumentation

**Full details:** See `references/05-platform-integration-datadog.md` section 4.

**Quick fix checklist:**
- [ ] `DD_REQUESTS_DISTRIBUTED_TRACING=false` in environment
- [ ] `DD_URLLIB3_DISTRIBUTED_TRACING=false` in environment
- [ ] `Instruments.REQUESTS` and `Instruments.URLLIB3` in Traceloop's `block_instruments`

### ddtrace + OpenLLMetry Double-Patching

**Problem:** Both ddtrace and Traceloop may try to patch the same library (e.g., OpenAI SDK), creating duplicate spans.

**Solution:** Initialize ddtrace first, then Traceloop. Traceloop detects already-patched libraries and skips them:

```python
def init_observability(service_name, ml_app_name):
    _init_ddtrace(service_name, ml_app_name)    # First
    _init_openllmetry(service_name)              # Second — skips already-patched libs
```

### Botocore Instrumentation for Bedrock

Ensure `botocore` patching is enabled — this is what captures Bedrock LLM calls:

```python
from ddtrace import patch
patch(botocore=True)  # Required for Bedrock auto-instrumentation
```

Without this, Bedrock `converse()` and `invoke_model()` calls are invisible in traces.

## 5. Environment-Specific Configuration

| Setting | Development | Staging | Production |
|---------|------------|---------|------------|
| `DD_LLMOBS_ENABLED` | `0` or `1` | `1` | `1` |
| `DD_LLMOBS_AGENTLESS_ENABLED` | `1` (no local agent) | `0` | `0` |
| `DD_API_KEY` | Required (agentless) | From secret | From secret |
| Sampling rules | None (100% traces) | Production rules | Production rules |
| Recall threshold | `0.5` (trigger more LLM evals) | `0.7` | `0.7` |
| Log level | `DEBUG` | `INFO` | `INFO` |
| `DD_TRACE_ENABLED` | `false` (optional) | `true` | `true` |
| TRACELOOP_BASE_URL | Not set (disabled) | Agent endpoint | Agent endpoint |

### Development Without Observability

For local development where observability adds overhead:

```bash
# Simply don't set DD_LLMOBS_ENABLED (defaults to 0)
# The application runs identically — all decorators become no-ops
# All evaluation guards short-circuit at is_observability_enabled()
```

## 6. Monitoring the Observability Stack

### Startup Verification

Log observability status at startup to confirm initialization:

```python
def init_observability(service_name, ml_app_name):
    global _OBSERVABILITY_ENABLED

    if os.getenv("DD_LLMOBS_ENABLED", "0") != "1":
        logger.info("LLM Observability disabled (set DD_LLMOBS_ENABLED=1 to enable)")
        return

    _OBSERVABILITY_ENABLED = True
    _init_ddtrace(service_name, ml_app_name)
    _init_openllmetry(service_name)

    logger.info(
        "observability_initialized",
        extra={
            "ddtrace": True,
            "openllmetry": bool(os.getenv("TRACELOOP_BASE_URL")),
            "agentless": os.getenv("DD_LLMOBS_AGENTLESS_ENABLED") == "1",
            "service": service_name,
            "ml_app": ml_app_name
        }
    )
```

### Alert Conditions

| Condition | Severity | Meaning |
|-----------|----------|---------|
| `observability_initialized` not in startup logs | Warning | Observability failed to initialize |
| `LLMObs flush failed` in logs | Warning | Buffered evaluations may be lost |
| No traces in Datadog for > 5 min | Critical | Agent connectivity issue or init failure |
| Evaluation submission rate drops > 50% | Warning | Decorator or guard pattern may be broken |

## 7. Operational Checklist

### Initial Setup

- [ ] Initialization order verified: logging -> ddtrace -> traceloop -> imports
- [ ] `DD_LLMOBS_ENABLED` set in deployment configuration
- [ ] `TRACELOOP_BASE_URL` pointing to OTLP receiver (port 4318)
- [ ] `DD_TRACE_AGENT_URL` pointing to APM agent (port 8126)
- [ ] AWS SigV4 conflict mitigated (REQUESTS/URLLIB3 disabled)
- [ ] `ddtrace-run` wrapping the process command (or manual `patch()`)

### Verification

- [ ] Traces visible in Datadog APM within 60s of first request
- [ ] LLM spans show token usage and model_id
- [ ] Evaluation metrics appear in LLMObs UI
- [ ] Log lines contain `dd.trace_id` and `dd.span_id`
- [ ] Clicking a trace_id in logs navigates to the correct trace

### Production Readiness

- [ ] Graceful shutdown flushes all observability data before closing connections
- [ ] Kafka/SQS polling noise sampled at <= 1%
- [ ] Health check endpoints excluded from traces
- [ ] Noisy third-party loggers suppressed to WARNING
- [ ] `is_observability_enabled()` gating all evaluation submissions
- [ ] All decorator imports have `try/except ImportError` fallbacks
- [ ] Environment-specific configuration documented and validated
