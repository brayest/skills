# Error Handling and Resilience

## Error Categories

```
┌─────────────────────┬──────────────────────────────────────────┐
│ Category            │ Handling Strategy                         │
├─────────────────────┼──────────────────────────────────────────┤
│ Transient           │ Retry with exponential backoff + jitter  │
│ (throttling, timeout│                                          │
│  network blip)      │                                          │
├─────────────────────┼──────────────────────────────────────────┤
│ Permanent           │ Publish to error topic, commit offset,   │
│ (bad data, schema   │ route to DLQ for inspection              │
│  mismatch)          │                                          │
├─────────────────────┼──────────────────────────────────────────┤
│ Infrastructure      │ Consumer reconnect, SQS visibility       │
│ (broker down,       │ timeout returns message to queue          │
│  partition rebalance│                                          │
└─────────────────────┴──────────────────────────────────────────┘
```

---

## Retry Configuration

```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "base_delay": 1.0,          # seconds
    "max_delay": 10.0,          # seconds
    "exponential_base": 2,
    "jitter": True,             # Prevents thundering herd
}
```

### Implementation

```python
import asyncio
import random


async def retry_with_backoff(
    func,
    *args,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    jitter: bool = True,
    **kwargs,
):
    """Execute a function with exponential backoff retry.

    Raises the last exception if all attempts fail.
    """
    last_exception = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if attempt == max_attempts - 1:
                raise

            delay = min(base_delay * (2 ** attempt), max_delay)
            if jitter:
                delay = delay * (0.5 + random.random())

            logger.warning(
                f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                f"Retrying in {delay:.1f}s"
            )
            await asyncio.sleep(delay)

    raise last_exception
```

---

## Kafka Error Handling

### The Poison Pill Problem

A **poison pill** is a message that consistently fails processing. Without proper handling, it blocks the entire partition because the consumer never commits past it.

**Solution**: Always commit after error handling, even on failure.

### Kafka Consumer Error + Commit Strategy

```
Message received
  │
  ├── Processing succeeds
  │     └── commit offset → message won't be redelivered
  │
  ├── Processing fails (transient)
  │     └── retry with backoff → on final failure:
  │           ├── publish to error topic (with original message)
  │           └── commit offset → prevents poison pill
  │
  └── Processing fails (permanent / bad data)
        ├── publish to error topic (with original message)
        └── commit offset → prevents infinite redelivery
```

**Critical rule**: Always commit after handling errors. The error topic preserves the original message for debugging and recovery.

### Implementation

```python
async def handle_message(self, message_data: dict, kafka_msg) -> None:
    """Process a message with error handling and guaranteed commit."""
    try:
        await self._process(message_data)
        self.consumer.commit(kafka_msg)

    except TransientError as e:
        # Retry with backoff
        try:
            await retry_with_backoff(
                self._process,
                message_data,
                max_attempts=3,
            )
            self.consumer.commit(kafka_msg)
        except Exception as final_error:
            # All retries exhausted — publish error and commit
            await self._publish_error(
                message_data,
                error_type="transient_exhausted",
                error_msg=str(final_error),
            )
            self.consumer.commit(kafka_msg)

    except Exception as e:
        # Permanent failure — publish error and commit
        await self._publish_error(
            message_data,
            error_type="processing_failed",
            error_msg=str(e),
            stack_trace=traceback.format_exc(),
        )
        self.consumer.commit(kafka_msg)
```

### Error Publishing

```python
async def _publish_error(
    self,
    original_message: dict,
    error_type: str,
    error_msg: str,
    stack_trace: str = None,
) -> None:
    """Publish structured error event to the errors topic."""
    error_message = {
        "originalMessage": original_message,
        "stage": os.environ["SERVICE_NAME"],
        "errorType": error_type,
        "errorMessage": error_msg,
        "stackTrace": stack_trace,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": f"{os.environ['SERVICE_NAME']}-service",
    }

    entity_id = original_message.get("entity_id", "unknown")
    self.producer.publish("errors", error_message, entity_id)
```

### Kafka Consumer Error Types

```python
from confluent_kafka import KafkaError

def _handle_kafka_error(self, error):
    """Handle Kafka-level consumer errors."""
    code = error.code()

    if code == KafkaError._PARTITION_EOF:
        # Normal — end of partition, no action needed
        return

    if code == KafkaError.UNKNOWN_TOPIC_OR_PART:
        # Expected during startup while consumer joins group
        logger.warning("Waiting for topic/partition assignment (startup)")
        return

    if code == KafkaError.INCONSISTENT_GROUP_PROTOCOL:
        # Consumer group protocol mismatch
        logger.warning(f"Consumer group protocol error: {error}")
        return

    # All other errors
    logger.error(f"Consumer error: {error}")
```

---

## SQS Error Handling

### SQS Retry Strategy

```
Message received
  │
  ├── Processing succeeds
  │     └── delete_message() → removed from queue permanently
  │
  └── Processing fails
        └── DO NOT delete → message becomes invisible
              │
              │ (after visibility timeout expires)
              │
              ├── Receive count < max → message returns to queue
              │                         → reprocessed by any available worker
              │
              └── Receive count >= max → automatically moved to DLQ
                                        → available for inspection/replay
```

### Key Principle: Delete Only on Success

```python
try:
    result = await process_task(message_data)

    # SUCCESS: Delete the message
    sqs_client.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=receipt_handle,
    )

except Exception as e:
    logger.error(f"Task failed: {e}")
    # FAILURE: Do NOT delete — message returns to queue after visibility timeout
    # SQS handles retry automatically
```

### DLQ Configuration

Configure the DLQ redrive policy on the source queue:

```json
{
    "RedrivePolicy": {
        "deadLetterTargetArn": "arn:aws:sqs:us-east-1:123456789:task-dlq.fifo",
        "maxReceiveCount": 3
    }
}
```

After 3 failed processing attempts (visibility timeout expiry), the message automatically moves to the DLQ.

### DLQ Inspection

```python
def inspect_dlq(handler: TaskQueueHandler) -> None:
    """Inspect failed messages in the DLQ for debugging."""
    messages = handler.get_dlq_messages(max_messages=10)

    for msg in messages:
        logger.info(
            f"DLQ message: entity={msg['entity_id']}, "
            f"task={msg['task_name']}, "
            f"retries={msg['retry_count']}, "
            f"timestamp={msg['timestamp']}"
        )
```

---

## Error Isolation Patterns

### Kafka: Error Topic Preserves Context

When a Kafka message fails permanently:
1. Publish the **full original message** to the error topic
2. Include error type, message, stack trace, and service name
3. Commit the offset to unblock the partition

The error topic with 30-day retention provides:
- Post-mortem analysis of failures
- Manual replay capability
- Alerting on error rates

### SQS: Per-Task Error Isolation

When an SQS task fails:
1. The failed task returns to the queue independently
2. Other tasks for the same entity continue processing
3. After max retries, the failed task moves to the DLQ
4. The parent entity can still complete with partial results

This prevents a single failing task from blocking the entire entity's processing.
