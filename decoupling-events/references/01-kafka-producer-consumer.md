# Kafka Producer and Consumer Configuration

> **Configuration for Your Project**
>
> Before implementing, define:
> - `{SERVICE_NAME}`: Your service name (e.g., `extraction-service`, `order-processor`)
> - `{CONSUMER_GROUP}`: Kafka consumer group (e.g., `extraction-group`)
> - `{TOPIC_STAGE_N_COMPLETE}`: Pipeline stage completion topics
> - `{TOPIC_ERRORS}`: Centralized error topic
> - `{ENTITY_ID}`: Primary correlation ID (e.g., `doc_id`, `order_id`)

## Producer Implementation

An idempotent, SSL-enabled Kafka producer using confluent-kafka:

```python
from confluent_kafka import Producer
import json
import os
import socket
import uuid
from datetime import datetime, timezone


class EventProducer:
    """Kafka producer for inter-service event publishing.

    Uses idempotent delivery, all-replica acknowledgment, and snappy compression.
    Each instance gets a unique client ID for operational debugging.
    """

    def __init__(self):
        bootstrap_servers = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
        if not bootstrap_servers:
            raise EnvironmentError("KAFKA_BOOTSTRAP_SERVERS is required")

        service_name = os.environ["SERVICE_NAME"]
        client_id = f"{service_name}-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

        self.producer = Producer({
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": "SSL",
            "ssl.ca.location": os.getenv("SSL_CA_LOCATION", "/etc/ssl/certs/ca-certificates.crt"),
            "acks": "all",                    # All ISR replicas must acknowledge
            "enable.idempotence": True,        # Prevent duplicate messages
            "compression.type": "snappy",      # Efficient compression
            "client.id": client_id,
        })

        # Load topic names from environment — no hardcoded defaults
        self.topics = {
            "stage_complete": os.environ["KAFKA_TOPIC_STAGE_COMPLETE"],
            "errors": os.environ["KAFKA_TOPIC_ERRORS"],
        }

    def publish(self, topic_key: str, message: dict, partition_key: str) -> None:
        """Publish a message to a Kafka topic.

        Args:
            topic_key: Logical topic name (looked up in self.topics).
            message: Dict payload (JSON-serializable).
            partition_key: Key for partition routing (e.g., entity_id).

        Raises:
            KeyError: If topic_key not found in self.topics.
            RuntimeError: If flush times out or delivery fails.
        """
        topic = self.topics[topic_key]
        message_bytes = json.dumps(message).encode("utf-8")
        key_bytes = partition_key.encode("utf-8")

        headers = {
            "timestamp": str(datetime.now(timezone.utc).timestamp()).encode("utf-8"),
            "source": os.environ["SERVICE_NAME"].encode("utf-8"),
        }

        self.producer.produce(
            topic=topic,
            key=key_bytes,
            value=message_bytes,
            headers=headers,
        )

        remaining = self.producer.flush(timeout=5)
        if remaining > 0:
            raise RuntimeError(f"Failed to flush {remaining} messages to {topic}")

    def close(self) -> None:
        """Flush pending messages and close the producer."""
        self.producer.flush(timeout=10)
```

### Producer Configuration Explained

| Setting | Value | Why |
|---------|-------|-----|
| `acks: all` | All in-sync replicas acknowledge | Maximum durability — no data loss |
| `enable.idempotence: True` | Exactly-once at producer level | Prevents duplicates on retry |
| `compression.type: snappy` | Snappy compression | Fast compression with good ratio |
| `client.id: {service}-{host}-{uuid}` | Unique per instance | Operational debugging in broker logs |
| `security.protocol: SSL` | TLS/SSL | Required for AWS MSK |
| `flush(timeout=5)` | 5-second sync flush | Ensures delivery before returning |

### Singleton Pattern

Use a module-level singleton to avoid creating multiple producer instances:

```python
_producer_instance: EventProducer | None = None


def get_producer() -> EventProducer:
    """Get or create the singleton producer instance."""
    global _producer_instance
    if _producer_instance is None:
        _producer_instance = EventProducer()
    return _producer_instance


def close_producer() -> None:
    """Flush and close the singleton producer."""
    global _producer_instance
    if _producer_instance is not None:
        _producer_instance.close()
        _producer_instance = None
```

---

## Consumer Implementation

A manual-commit consumer with cooperative-sticky rebalancing:

```python
from confluent_kafka import Consumer, KafkaError
import json
import logging
import os
import socket
import uuid

logger = logging.getLogger(__name__)


class EventConsumer:
    """Kafka consumer with manual offset commit and cooperative rebalancing.

    Designed for long-running processing tasks with extended poll intervals.
    """

    def __init__(self, topics: list[str], consumer_group: str):
        bootstrap_servers = os.environ["KAFKA_BOOTSTRAP_SERVERS"]
        if not bootstrap_servers:
            raise EnvironmentError("KAFKA_BOOTSTRAP_SERVERS is required")

        client_id = f"{consumer_group}-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"

        self.consumer = Consumer({
            "bootstrap.servers": bootstrap_servers,
            "security.protocol": "SSL",
            "ssl.ca.location": os.getenv("SSL_CA_LOCATION", "/etc/ssl/certs/ca-certificates.crt"),
            "group.id": consumer_group,
            "client.id": client_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,           # Manual commit after processing
            "max.poll.interval.ms": 1800000,       # 30 min for long processing
            "session.timeout.ms": 45000,           # 45s failure detection
            "heartbeat.interval.ms": 15000,        # 1/3 of session timeout
            "fetch.min.bytes": 1,
            "fetch.wait.max.ms": 500,
            "partition.assignment.strategy": "cooperative-sticky",
        })

        self.consumer.subscribe(topics)
        self.running = True

    def poll_loop(self, handler):
        """Main polling loop. Calls handler(message_data, raw_msg) for each message.

        The handler is responsible for processing and committing:
        - On success: handler processes and calls self.consumer.commit(raw_msg)
        - On failure: handler publishes error and calls self.consumer.commit(raw_msg)
        """
        while self.running:
            msg = self.consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                self._handle_error(msg.error())
                continue

            message_data = json.loads(msg.value().decode("utf-8"))
            handler(message_data, msg)

    def _handle_error(self, error):
        """Handle Kafka consumer errors."""
        code = error.code()
        if code == KafkaError._PARTITION_EOF:
            return  # Normal — end of partition
        if code == KafkaError.UNKNOWN_TOPIC_OR_PART:
            logger.warning("Waiting for topic/partition assignment (startup)")
            return
        if code == KafkaError.INCONSISTENT_GROUP_PROTOCOL:
            logger.warning(f"Consumer group protocol error: {error}")
            return
        logger.error(f"Consumer error: {error}")

    def shutdown(self):
        """Signal the consumer to stop and close cleanly."""
        self.running = False
        self.consumer.close()
```

### Consumer Configuration Explained

| Setting | Value | Why |
|---------|-------|-----|
| `enable.auto.commit: False` | Manual commits | Commit only after successful processing |
| `auto.offset.reset: latest` | Start from latest | Skip historical backlog on new group |
| `max.poll.interval.ms: 1800000` | 30 minutes | Prevents timeout during long processing |
| `session.timeout.ms: 45000` | 45 seconds | Faster failure detection |
| `heartbeat.interval.ms: 15000` | 15 seconds | 1/3 of session timeout (recommended ratio) |
| `partition.assignment.strategy: cooperative-sticky` | Cooperative rebalancing | Minimal disruption during rebalances |
| `fetch.min.bytes: 1` | Minimum 1 byte | Respond immediately when data available |
| `fetch.wait.max.ms: 500` | 500ms max wait | Low latency message delivery |

---

## Topic Design

### Principles

| Principle | Rationale | Example |
|-----------|-----------|---------|
| **One topic per event type** | Clear ownership, independent scaling | `order-validated`, `payment-processed` |
| **Partition key = entity ID** | Related messages stay together | Key: `order_id`, `doc_id`, `user_id` |
| **Dedicated error topic** | Centralized error observability | `processing-errors` with 30-day retention |
| **DLQ topics per service** | Isolate unprocessable messages | `{service}-dlq` with extended retention |
| **Configurable via env vars** | Decouple topic names from code | `KAFKA_TOPIC_STAGE_COMPLETE` |

### Topic Configuration Tiers

```python
from confluent_kafka.admin import AdminClient, NewTopic

TOPIC_CONFIGS = {
    "standard": {
        "num_partitions": 3,
        "replication_factor": 3,
        "config": {
            "retention.ms": "604800000",       # 7 days
            "min.insync.replicas": "2",
            "compression.type": "snappy",
        },
    },
    "error": {
        "num_partitions": 1,
        "replication_factor": 3,
        "config": {
            "retention.ms": "2592000000",      # 30 days
            "min.insync.replicas": "1",
            "compression.type": "snappy",
        },
    },
    "dlq": {
        "num_partitions": 1,
        "replication_factor": 3,
        "config": {
            "retention.ms": "2592000000",      # 30 days
            "min.insync.replicas": "1",
            "compression.type": "snappy",
        },
    },
}
```

**Tier selection**:
- **Standard**: Regular pipeline event topics (3 partitions, 7-day retention, 2 ISR)
- **Error**: Centralized error topics (1 partition, 30-day retention, 1 ISR)
- **DLQ**: Dead letter queues (1 partition, 30-day retention, 1 ISR)

### Topic Auto-Creation at Startup

```python
def ensure_topics_exist(topics: dict[str, str], tier: str = "standard") -> None:
    """Create topics if they don't already exist.

    Call during service startup (e.g., FastAPI lifespan).
    """
    admin = AdminClient({
        "bootstrap.servers": os.environ["KAFKA_BOOTSTRAP_SERVERS"],
        "security.protocol": "SSL",
        "ssl.ca.location": os.getenv("SSL_CA_LOCATION", "/etc/ssl/certs/ca-certificates.crt"),
    })

    existing = set(admin.list_topics(timeout=10).topics.keys())
    config = TOPIC_CONFIGS[tier]

    new_topics = []
    for name, topic_value in topics.items():
        if topic_value not in existing:
            new_topics.append(NewTopic(
                topic_value,
                num_partitions=config["num_partitions"],
                replication_factor=config["replication_factor"],
                config=config["config"],
            ))

    if new_topics:
        futures = admin.create_topics(new_topics)
        for topic_name, future in futures.items():
            future.result()  # Raises on failure
            logger.info(f"Created topic: {topic_name}")
```

---

## AWS MSK Specifics

### SSL Configuration

AWS MSK requires SSL for client connections:

```python
{
    "security.protocol": "SSL",
    "ssl.ca.location": "/etc/ssl/certs/ca-certificates.crt",
}
```

- **Local development**: Mount AWS certificates via Docker volumes
- **Kubernetes**: Use the node's CA bundle or mount a ConfigMap with the CA certificate
- **No access keys**: MSK authentication uses IAM roles, not access keys

### Bootstrap Server Format

MSK bootstrap servers use port 9094 for TLS:

```
b-1.cluster.kafka.us-east-1.amazonaws.com:9094,
b-2.cluster.kafka.us-east-1.amazonaws.com:9094,
b-3.cluster.kafka.us-east-1.amazonaws.com:9094
```

Always configure via `KAFKA_BOOTSTRAP_SERVERS` environment variable — never hardcode.
