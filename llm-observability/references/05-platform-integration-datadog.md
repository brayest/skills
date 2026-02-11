# Platform Integration: Datadog

Datadog-specific configuration for LLM Observability, APM traces, and log correlation. This reference complements the general architecture in `01-observability-architecture.md` with Datadog-specific details.

## 1. Environment Variables

### Core Observability

| Variable | Value | Purpose |
|----------|-------|---------|
| `DD_LLMOBS_ENABLED` | `1` | Master switch — enables LLM Observability |
| `DD_SERVICE` | `my-service` | Service name (unified service tagging) |
| `DD_ENV` | `production` | Environment tag |
| `DD_VERSION` | `2.1.0` | Version tag |
| `DD_LLMOBS_ML_APP` | `my-ml-app` | ML application name in LLMObs UI |
| `DD_TRACE_ENABLED` | `true` | Enable APM trace collection |
| `DD_LOGS_INJECTION` | `true` | Auto-inject trace IDs into logs |

### Agent Connectivity

| Variable | Value | Purpose |
|----------|-------|---------|
| `DD_AGENT_HOST` | `status.hostIP` (K8s) | DaemonSet agent on the same node |
| `DD_TRACE_AGENT_URL` | `http://$(DD_AGENT_HOST):8126` | APM trace receiver |
| `TRACELOOP_BASE_URL` | `http://$(DD_AGENT_HOST):4318` | OTLP receiver for OpenLLMetry traces |
| `DD_API_KEY` | (from secret) | Required for agentless mode only |
| `DD_SITE` | `datadoghq.com` | Datadog site/region |

### Distributed Tracing & Data Streams

| Variable | Value | Purpose |
|----------|-------|---------|
| `DD_DATA_STREAMS_ENABLED` | `true` | Kafka/SQS flow metrics |
| `DD_KAFKA_PROPAGATION_ENABLED` | `true` | Trace context propagation across Kafka messages |
| `DD_REQUESTS_DISTRIBUTED_TRACING` | `false` | **Disabled** — conflicts with AWS SigV4 signing |
| `DD_URLLIB3_DISTRIBUTED_TRACING` | `false` | **Disabled** — same SigV4 conflict |

### Cardinality & Sampling

| Variable | Value | Purpose |
|----------|-------|---------|
| `DD_TRACE_REMOVE_INTEGRATION_SERVICE_NAMES_ENABLED` | `true` | Reduce metric cardinality |
| `DD_TRACE_SAMPLING_RULES` | `[{"resource":"kafka.consume","sample_rate":0.01}]` | 1% sample on Kafka polling noise |

## 2. ddtrace-run Command Wrapper

`ddtrace-run` wraps the Python process for automatic instrumentation at the runtime level:

```bash
# Standard usage
ddtrace-run python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# For non-web services
ddtrace-run python main.py
```

**What `ddtrace-run` does:**
- Auto-patches all supported libraries before application code runs
- Enables trace collection without manual `patch()` calls
- Sets up the trace agent connection

**When to use `ddtrace-run` vs manual patching:**
- `ddtrace-run` — simpler, covers more libraries automatically, preferred for production
- Manual `patch()` — more control over which libraries are patched, useful when some instrumentations conflict

## 3. LLMObs Initialization

```python
from ddtrace import config, patch
from ddtrace.llmobs import LLMObs

# Patch boto3/botocore for Bedrock auto-instrumentation
patch(botocore=True, httpx=True)
config.service = "my-service"

# Enable LLM Observability
agentless = os.getenv("DD_LLMOBS_AGENTLESS_ENABLED", "0") == "1"
LLMObs.enable(
    ml_app="my-ml-app",           # Appears in DD LLMObs UI
    agentless_enabled=agentless    # True for local dev without DD Agent
)
```

### LLMObs.annotate() — Adding LLM Metadata

```python
LLMObs.annotate(
    input_data="Extract roofType from the document",
    output_data="wood_frame",
    metadata={
        "model": "anthropic.claude-sonnet",
        "temperature": 0.0,
        "max_tokens": 4096,
        "document_id": doc_id,
    }
)
```

### LLMObs.submit_evaluation() — Quality Metrics

```python
span = LLMObs.export_span()
if span:
    LLMObs.submit_evaluation(
        span=span,
        label="context_relevance",
        metric_type="score",      # "score" (float) or "categorical" (string)
        value=0.85
    )
```

## 4. AWS SigV4 Conflict Workaround

### Problem

When ddtrace or Traceloop instruments `requests` or `urllib3`, it injects distributed tracing headers (`x-datadog-trace-id`, `x-datadog-parent-id`) into HTTP requests. AWS SigV4 signing includes all headers in the signature calculation. The injected headers were not present when the signature was computed, causing signature mismatch errors.

### Symptoms

- `"not enough values to unpack"` errors from botocore
- OpenSearch requests failing with 403 authentication errors
- Intermittent failures on any AWS service using SigV4 (OpenSearch, S3, DynamoDB)

### Solution — Two Layers

**Layer 1: Environment variables** (blocks ddtrace's built-in HTTP patching):
```yaml
DD_REQUESTS_DISTRIBUTED_TRACING: "false"
DD_URLLIB3_DISTRIBUTED_TRACING: "false"
```

**Layer 2: Traceloop block_instruments** (blocks OpenLLMetry's HTTP patching):
```python
from traceloop.sdk.instruments import Instruments

blocked = {Instruments.REQUESTS, Instruments.URLLIB3}
Traceloop.init(app_name=service_name, block_instruments=blocked)
```

Both layers are needed — ddtrace and Traceloop instrument HTTP clients independently.

**What is preserved:** LLM-specific instrumentation (Bedrock, LlamaIndex, OpenAI) continues to work. Only generic HTTP client tracing is disabled.

## 5. Agentless Mode (Local Development)

For local development without a Datadog Agent running:

```yaml
# docker-compose.yml
environment:
  - DD_LLMOBS_ENABLED=1
  - DD_LLMOBS_AGENTLESS_ENABLED=1
  - DD_API_KEY=${DD_API_KEY}
  - DD_SITE=datadoghq.com
  - DD_SERVICE=my-service
  - DD_ENV=development
```

**Trade-offs:**
- Traces sent directly to Datadog API (no local agent needed)
- Higher latency per trace submission (network round-trip to Datadog)
- Requires `DD_API_KEY` in environment (never commit to version control)
- Not recommended for production (use the DaemonSet agent)

## 6. Kubernetes Deployment

### Helm Template Pattern

```yaml
spec:
  containers:
    - name: {{ .Chart.Name }}
      image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"

      # Wrap with ddtrace-run when observability is enabled
      {{- if .Values.observability.enabled }}
      command: ["ddtrace-run", "python", "-m", "uvicorn", "app.main:app",
                "--host", "0.0.0.0", "--port", "8000"]
      {{- end }}

      env:
        # Master switch
        - name: DD_LLMOBS_ENABLED
          value: "{{ if .Values.observability.enabled }}1{{ else }}0{{ end }}"

        {{- if .Values.observability.enabled }}
        # Unified service tagging
        - name: DD_SERVICE
          value: "{{ .Chart.Name }}"
        - name: DD_ENV
          value: "{{ .Values.settings.environment }}"
        - name: DD_VERSION
          value: "{{ .Values.image.tag }}"
        - name: DD_LLMOBS_ML_APP
          value: "{{ .Chart.Name }}"
        - name: DD_TRACE_ENABLED
          value: "true"
        - name: DD_LOGS_INJECTION
          value: "true"

        # SigV4 conflict prevention
        - name: DD_REQUESTS_DISTRIBUTED_TRACING
          value: "false"
        - name: DD_URLLIB3_DISTRIBUTED_TRACING
          value: "false"

        # Kafka / Data Streams
        - name: DD_DATA_STREAMS_ENABLED
          value: "true"
        - name: DD_KAFKA_PROPAGATION_ENABLED
          value: "true"

        # Cardinality control
        - name: DD_TRACE_REMOVE_INTEGRATION_SERVICE_NAMES_ENABLED
          value: "true"
        - name: DD_TRACE_SAMPLING_RULES
          value: '[{"resource":"kafka.consume","sample_rate":0.01}]'

        # Agent connectivity via DaemonSet
        - name: DD_AGENT_HOST
          valueFrom:
            fieldRef:
              fieldPath: status.hostIP
        - name: DD_TRACE_AGENT_URL
          value: "http://$(DD_AGENT_HOST):8126"
        - name: TRACELOOP_BASE_URL
          value: "http://$(DD_AGENT_HOST):4318"
        - name: DD_API_KEY
          valueFrom:
            secretKeyRef:
              name: datadog-secret
              key: api-key
              optional: true
        {{- end }}
```

### Key K8s Patterns

- **DaemonSet agent discovery** — `status.hostIP` resolves to the node's IP where the Datadog Agent DaemonSet runs
- **Conditional command** — `ddtrace-run` only wraps the process when `observability.enabled` is true
- **Optional API key** — `optional: true` prevents pod crash if the secret doesn't exist

## 7. Datadog Features Used

| Feature | Purpose |
|---------|---------|
| **APM Traces** | End-to-end request tracing with waterfall view |
| **LLM Observability** | LLM-specific traces: token usage, prompts, completions, evaluations |
| **Log Management** | Searchable JSON logs correlated with traces via `dd.trace_id` |
| **Data Streams Monitoring** | Kafka topic topology, consumer lag, message flow metrics |
| **Unified Service Tagging** | Single view connecting traces + logs + metrics per service |

## 8. Dependencies

```
# requirements.txt
ddtrace>=3.9.0
traceloop-sdk>=0.50.0
opentelemetry-api>=1.20.0
opentelemetry-sdk>=1.20.0
python-json-logger>=2.0.7
```
