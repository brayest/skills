# Message Design Patterns

## Standard Message Envelope

Every message across Kafka and SQS follows a consistent envelope structure. This enables cross-service correlation, multi-tenancy routing, and operational debugging.

### Kafka Event Messages

```python
{
    # Identity — required on every message
    "entity_id": "uuid-v4",                   # Primary correlation ID
    "timestamp": "2026-01-15T10:30:00Z",      # Event time (ISO-8601 UTC)

    # Context — routing and multi-tenancy
    "organization": "tenant-name",             # Multi-tenancy routing
    "domain": "domain-name",                   # Domain/subdomain context

    # Payload — event-specific (varies by topic)
    "source_key": "s3://bucket/path/file.pdf", # For trigger events
    "result_key": "s3://bucket/output/result",  # For completion events
    "metrics": {                                # Processing stats
        "processing_duration_ms": 1250,
        "items_processed": 42,
    },

    # Tracing
    "source_service": "service-name",          # Originating service
}
```

### SQS Task Messages

```python
{
    # Identity
    "entity_id": "uuid-v4",                   # Parent entity correlation ID
    "task_name": "specific-task",             # Individual task identifier
    "timestamp": "2026-01-15T10:30:00Z",      # Enqueue time (ISO-8601 UTC)

    # Task configuration
    "task_config": {                           # Task-specific parameters
        "top_k": 10,
        "threshold": 0.7,
    },

    # Context
    "metadata": {
        "organization": "tenant-name",
        "domain": "domain-name",
    },

    # Processing state
    "retry_count": 0,                          # Current retry attempt
    "total_tasks": 42,                         # Total tasks in this batch
}
```

### Completion Event Messages

Published when a pipeline stage finishes:

```python
{
    "entity_id": "uuid-v4",
    "timestamp": "2026-01-15T10:32:15Z",
    "source_service": "stage-2-service",

    # Results location
    "bucket": "output-bucket",
    "output_key": "results/entity-id/output.json",

    # Processing metrics
    "items_processed": 105,
    "processing_duration_s": 30.97,
    "verification_status": "READY",

    # Context passthrough
    "organization": "tenant-name",
    "domain": "domain-name",
}
```

### Error Event Messages

Published to the centralized error topic:

```python
{
    "originalMessage": { ... },               # Full original message for debugging
    "stage": "service-name",                  # Which service failed
    "errorType": "processing_failed",         # Error category
    "errorMessage": "Detailed error text",    # Human-readable description
    "stackTrace": "...",                       # Optional stack trace
    "timestamp": "2026-01-15T10:33:00Z",
    "service": "service-name-service",
}
```

---

## Kafka Headers

Use headers for out-of-band metadata that consumers may want without deserializing the message body:

```python
headers = {
    "timestamp": str(datetime.now(timezone.utc).timestamp()).encode("utf-8"),
    "source": os.environ["SERVICE_NAME"].encode("utf-8"),
}
```

### Distributed Tracing Integration

Kafka headers propagate distributed tracing context:

```python
# ddtrace auto-patches confluent-kafka and injects/extracts trace headers
# OpenTelemetry auto-instrumentation does the same

# Manual header injection (if auto-instrumentation is not available):
headers = {
    "timestamp": str(utc_timestamp).encode("utf-8"),
    "source": service_name.encode("utf-8"),
    "trace_id": current_trace_id.encode("utf-8"),
    "span_id": current_span_id.encode("utf-8"),
}
```

### SQS Message Attributes

SQS uses MessageAttributes (not headers) for metadata filtering:

```python
MessageAttributes={
    "entity_id": {"StringValue": entity_id, "DataType": "String"},
    "task_name": {"StringValue": task_name, "DataType": "String"},
    "organization": {"StringValue": organization, "DataType": "String"},
}
```

These enable:
- Filtering messages by attribute in receive calls
- Operational visibility without deserializing message bodies
- CloudWatch metric dimensions

---

## Partition Key Strategy

The partition key determines which Kafka partition receives the message. Related messages sharing a partition key are guaranteed to arrive in order and be processed by the same consumer.

| Event Type | Partition Key | Rationale |
|------------|---------------|-----------|
| Entity processing | `entity_id` | All events for an entity hit the same partition |
| Task reprocessing | `{entity_id}_{task_name}` | Task-level affinity |
| Cache invalidation | `cache_refresh_{unix_timestamp}` | Spread across partitions (no ordering needed) |
| Job control (cancel/pause) | `job_control_{entity_id}_{action}` | Entity-level affinity |
| Broadcast events | Random or round-robin | Even distribution |

### Key Composition Patterns

```python
# Entity-level affinity (most common)
key = entity_id

# Task-level affinity
key = f"{entity_id}_{task_name}"

# Temporal spread (no ordering needed)
key = f"event_type_{int(datetime.now(timezone.utc).timestamp())}"

# Action-scoped affinity
key = f"control_{entity_id}_{action}"
```

### When Ordering Matters

- **Same entity, different stages**: Use `entity_id` as key — ensures extraction-complete arrives after extraction-started
- **Same entity, independent tasks**: Use `{entity_id}_{task_name}` — tasks can be processed out of order
- **Global events (cache refresh, config change)**: Use timestamp-based keys — spread load across partitions

---

## Message Serialization

### JSON Serialization Standard

All messages use JSON with UTF-8 encoding:

```python
# Serialize
message_bytes = json.dumps(message).encode("utf-8")
key_bytes = partition_key.encode("utf-8")

# Deserialize
message_data = json.loads(msg.value().decode("utf-8"))
```

### Safe Serialization for Complex Objects

When messages may contain Pydantic models or custom objects:

```python
def safe_json_dumps(obj: Any, indent: int | None = None) -> str:
    """JSON serialization that handles Pydantic models and custom objects."""
    if hasattr(obj, "model_dump"):      # Pydantic v2
        return json.dumps(obj.model_dump(), indent=indent)
    elif hasattr(obj, "dict"):          # Pydantic v1
        return json.dumps(obj.dict(), indent=indent)
    elif isinstance(obj, dict):
        return json.dumps(obj, indent=indent, default=str)
    else:
        return json.dumps(obj, indent=indent, default=str)
```

### Timestamp Convention

All timestamps use UTC ISO-8601 format:

```python
from datetime import datetime, timezone

timestamp = datetime.now(timezone.utc).isoformat()
# Output: "2026-01-15T10:30:00.123456+00:00"
```
