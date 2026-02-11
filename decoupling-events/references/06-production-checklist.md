# Production Checklist, Observability, and Configuration

## Health Check Endpoints

Every service with Kafka or SQS integration needs health check endpoints:

### Kafka Health

```python
@app.get("/kafka/health")
async def kafka_health():
    """Check Kafka connectivity, topic existence, and consumer lag."""
    try:
        admin = AdminClient({
            "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
            "security.protocol": "SSL",
            "ssl.ca.location": os.getenv("SSL_CA_LOCATION", "/etc/ssl/certs/ca-certificates.crt"),
        })

        cluster_metadata = admin.list_topics(timeout=5)
        existing_topics = set(cluster_metadata.topics.keys())
        expected_topics = set(service.topics.values())
        missing = expected_topics - existing_topics

        return {
            "status": "healthy" if not missing else "degraded",
            "bootstrap_servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
            "topics": service.topics,
            "existing_topics": sorted(existing_topics & expected_topics),
            "missing_topics": sorted(missing),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### SQS Health

```python
@app.get("/sqs/health")
async def sqs_health():
    """Check SQS queue depth and DLQ status."""
    try:
        status = sqs_handler.get_queue_status()

        result = {
            "status": "healthy",
            "messages_available": status["messages_available"],
            "messages_in_flight": status["messages_in_flight"],
            "messages_delayed": status["messages_delayed"],
        }

        if sqs_handler.dlq_url:
            dlq_attrs = sqs_handler.sqs_client.get_queue_attributes(
                QueueUrl=sqs_handler.dlq_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )["Attributes"]
            result["dlq_depth"] = int(dlq_attrs.get("ApproximateNumberOfMessages", 0))

        return result
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
```

### Combined Health

```python
@app.get("/health")
async def health():
    """Service-level health combining all dependencies."""
    return {
        "status": "healthy",
        "service": os.environ["SERVICE_NAME"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

---

## Monitoring Scripts

Build CLI monitoring tools for operational visibility:

### Kafka Monitor

```python
"""Kafka topic and consumer group monitoring tool.

Usage:
    python kafka_monitor.py --topics my-prefix- --show-messages 5
    python kafka_monitor.py --consumer-groups my-consumer-group
    python kafka_monitor.py --list-all-topics
"""

# Features:
# - List topics with partition details (leader, replicas, ISR)
# - Get topic configuration (retention, compression, min.insync.replicas)
# - Monitor consumer group lag (high/low water marks per partition)
# - Peek at recent messages (JSON-formatted payload display)
# - Print formatted topic summaries
```

### SQS Monitor

```python
"""SQS queue monitoring tool.

Usage:
    python sqs_monitor.py --profile my_profile --region us-east-1
    python sqs_monitor.py --watch  # Continuous monitoring every 10s
"""

# Features:
# - Queue metrics (available, in-flight, delayed messages)
# - Sample message inspection
# - DLQ monitoring and depth tracking
# - Retry count analysis
```

---

## Distributed Tracing

### Kafka Header Propagation

Tracing context propagates through Kafka headers automatically with instrumentation libraries:

```python
# ddtrace: Auto-patches confluent-kafka
# Install: pip install ddtrace
# Run: ddtrace-run python main.py

# OpenTelemetry: Auto-instrumentation for confluent-kafka
# Install: pip install opentelemetry-instrumentation-confluent-kafka
```

For manual propagation:

```python
headers = {
    "timestamp": str(datetime.now(timezone.utc).timestamp()).encode("utf-8"),
    "source": os.environ["SERVICE_NAME"].encode("utf-8"),
}

# ddtrace automatically injects trace headers when produce() is called
producer.produce(topic=topic, key=key, value=value, headers=headers)
```

### Structured Logging

Include correlation IDs in every log entry:

```python
logger.info(
    "Processing message",
    extra={
        "entity_id": entity_id,
        "stage": os.environ["SERVICE_NAME"],
        "duration_ms": processing_duration_ms,
        "topic": msg.topic(),
        "partition": msg.partition(),
        "offset": msg.offset(),
    },
)
```

---

## Environment Variable Convention

```bash
# ─── Kafka Connection ───
KAFKA_BOOTSTRAP_SERVERS=broker-1:9094,broker-2:9094,broker-3:9094
SSL_CA_LOCATION=/etc/ssl/certs/ca-certificates.crt

# ─── Kafka Topics (one env var per topic) ───
KAFKA_TOPIC_STAGE_1_COMPLETE=pipeline-stage-1-complete
KAFKA_TOPIC_STAGE_2_COMPLETE=pipeline-stage-2-complete
KAFKA_TOPIC_ERRORS=pipeline-processing-errors
KAFKA_TOPIC_DLQ=pipeline-service-dlq

# ─── Kafka Consumer ───
KAFKA_CONSUMER_GROUP=my-service-group
KAFKA_ENABLED=true

# ─── SQS Configuration ───
SQS_TASK_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/task-queue.fifo
SQS_DLQ_URL=https://sqs.us-east-1.amazonaws.com/123456789/task-dlq.fifo
USE_SQS_TASK_PROCESSING=true

# ─── Processing ───
MAX_RETRIES=3
RETRY_DELAY=5

# ─── Service Identity ───
SERVICE_NAME=my-service

# ─── AWS (IAM roles only — never access keys) ───
AWS_DEFAULT_REGION=us-east-1
```

### Conventions

- **Required variables**: Use `os.environ["VAR"]` (raises `KeyError` if missing)
- **Optional variables**: Use `os.getenv("VAR", default)` only when a true default exists
- **Feature flags**: `KAFKA_ENABLED=true`, `USE_SQS_TASK_PROCESSING=true` for gradual rollout
- **No access keys**: Local development uses `.aws` profiles; production uses IAM roles

### Secrets from Vault

For production deployments, load Kafka/SQS configuration from HashiCorp Vault before service startup. Vault populates environment variables, keeping secrets out of container images and config files.

---

## Production Checklist

### Kafka

- [ ] **Idempotent producer** — `enable.idempotence: True`
- [ ] **Acks all** — `acks: all` (all ISR replicas acknowledge)
- [ ] **Manual offset commit** — `enable.auto.commit: False`, commit only after processing
- [ ] **Cooperative-sticky rebalancing** — Minimizes partition reassignment
- [ ] **Extended max.poll.interval.ms** — Matches longest expected processing time
- [ ] **Unique client.id per instance** — Includes hostname + UUID
- [ ] **SSL/TLS enabled** — Required for MSK connections
- [ ] **Error topic** — 30-day retention for post-mortem analysis
- [ ] **DLQ topic per service** — Isolates unprocessable messages
- [ ] **Topic auto-creation at startup** — With appropriate partition/retention config
- [ ] **Health check endpoint** — Reports broker connectivity and topic existence
- [ ] **Snappy compression** — Efficient bandwidth usage
- [ ] **Graceful shutdown** — Flushes producer and closes consumer

### SQS

- [ ] **FIFO queue** — Ordered, exactly-once delivery
- [ ] **MessageGroupId per task** — Enables parallel processing across tasks
- [ ] **MessageDeduplicationId** — Prevents duplicate task processing
- [ ] **Visibility timeout** — Matches maximum task processing time
- [ ] **Long polling** — `WaitTimeSeconds=5`, reduces empty receives
- [ ] **Dead Letter Queue** — Configured with max receive count
- [ ] **Delete only on success** — Failed tasks return to queue automatically
- [ ] **Queue status monitoring** — Available/in-flight/delayed counts
- [ ] **DLQ inspection** — Retrieve failed tasks for debugging
- [ ] **IAM role-based access** — Never use access keys

### General

- [ ] **Feature flags** — `KAFKA_ENABLED`, `USE_SQS_TASK_PROCESSING` for gradual rollout
- [ ] **Structured JSON logging** — entity_id, stage, duration_ms in every log
- [ ] **Distributed tracing headers** — Propagated in Kafka headers
- [ ] **Job tracking** — Atomic counters in DynamoDB or similar for completion tracking
- [ ] **Monitoring scripts** — CLI tools for topic/queue inspection
- [ ] **Graceful shutdown** — Drain in-flight work before container termination
- [ ] **Health check endpoints** — For Kafka, SQS, and combined service health

---

## Architecture Decision Records

### ADR-1: Kafka for Inter-Service, SQS for Intra-Service

**Context**: Microservices need asynchronous communication with different guarantees at different layers.

**Decision**: Use Kafka (MSK) for inter-service event streaming and SQS FIFO for fine-grained task distribution within a service.

**Rationale**:
- Kafka provides durable, replayable event logs with consumer group fan-out
- SQS FIFO provides per-task retry, DLQ support, and message-group-level parallelism without partition constraints
- Combining both avoids overloading Kafka with high-cardinality task messages while preserving pipeline-level event ordering

### ADR-2: Manual Offset Commit

**Context**: Auto-commit can acknowledge messages before processing completes, causing data loss on failure.

**Decision**: Disable auto-commit. Commit offsets only after successful processing or error publishing.

**Rationale**: At-least-once delivery guarantee. Combined with idempotent producers and deduplication, this achieves effectively-exactly-once semantics.

### ADR-3: Always Commit After Error Handling

**Context**: Uncommitted messages on permanent failures become poison pills that block the partition forever.

**Decision**: On permanent failures, publish error to error topic, then commit the offset.

**Rationale**: Error topic preserves the original message for debugging. Committing prevents the partition from being blocked. The error topic + DLQ provides the recovery path.

### ADR-4: SQS Visibility Timeout Over Kafka Retry Topics

**Context**: Long-running tasks (LLM calls, ML inference) need retry capability.

**Decision**: Use SQS visibility timeout for task-level retry instead of Kafka retry topics.

**Rationale**: SQS natively handles retry by returning messages to the queue after visibility timeout. This is simpler than maintaining separate retry topics with delay logic in Kafka, and supports automatic DLQ escalation after max retries.
