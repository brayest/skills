# SQS FIFO Task Distribution

> **Configuration for Your Project**
>
> Before implementing, define:
> - `{QUEUE_URL}`: SQS FIFO queue URL for task distribution
> - `{DLQ_URL}`: SQS dead letter queue URL
> - `{ENTITY_ID}`: Primary correlation ID (e.g., `doc_id`, `order_id`)
> - `{TASK_NAME}`: Individual task identifier (e.g., `field_name`, `step_name`)

## When to Use SQS

Use SQS FIFO queues when a single Kafka event triggers multiple independent subtasks that benefit from:

- **Per-task retry** — Failed tasks automatically return to the queue
- **Error isolation** — One task failure doesn't block others
- **Parallel processing** — Multiple containers process different tasks simultaneously
- **DLQ escalation** — Unprocessable tasks land in a dead letter queue after max retries

## Task Queue Handler

```python
import boto3
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class TaskQueueHandler:
    """SQS FIFO queue handler for fine-grained task distribution.

    Uses MessageGroupId for parallel processing across tasks and
    MessageDeduplicationId for exactly-once delivery.
    """

    def __init__(self, sqs_client, queue_url: str, dlq_url: str = None):
        if not sqs_client:
            raise ValueError("SQS client is required")
        if not queue_url:
            raise ValueError("Queue URL is required")

        self.sqs_client = sqs_client
        self.queue_url = queue_url
        self.dlq_url = dlq_url
        self.visibility_timeout = 900  # 15 minutes for long-running tasks

    def enqueue_tasks(self, entity_id: str, tasks: list[dict], metadata: dict) -> int:
        """Enqueue multiple tasks for parallel processing.

        Args:
            entity_id: Parent entity ID (e.g., doc_id, order_id).
            tasks: List of task dicts, each with at least a "name" key.
            metadata: Shared metadata for all tasks (e.g., organization, tenant).

        Returns:
            Number of tasks successfully enqueued.

        Raises:
            ClientError: If SQS send_message fails.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        enqueued = 0

        for task in tasks:
            task_name = task["name"]
            message_body = {
                "entity_id": entity_id,
                "task_name": task_name,
                "task_config": task.get("config", {}),
                "metadata": metadata,
                "timestamp": timestamp,
                "retry_count": 0,
                "total_tasks": len(tasks),
            }

            self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(message_body),
                MessageGroupId=f"{entity_id}-{task_name}",
                MessageDeduplicationId=f"{entity_id}-{task_name}-{timestamp}",
                MessageAttributes={
                    "entity_id": {"StringValue": entity_id, "DataType": "String"},
                    "task_name": {"StringValue": task_name, "DataType": "String"},
                },
            )
            enqueued += 1

        logger.info(f"Enqueued {enqueued}/{len(tasks)} tasks for entity {entity_id}")
        return enqueued

    async def process_one(
        self,
        callback: Callable[..., Awaitable[Any]],
        **callback_kwargs,
    ) -> dict | None:
        """Receive and process a single task from the queue.

        Args:
            callback: Async function to process the task. Receives
                entity_id, task_name, task_config, metadata as kwargs.
            **callback_kwargs: Additional kwargs passed to callback.

        Returns:
            Result dict with status ("completed" or "failed"), or None if queue is empty.
        """
        response = self.sqs_client.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,                           # Long polling
            VisibilityTimeout=self.visibility_timeout,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )

        messages = response.get("Messages", [])
        if not messages:
            return None

        message = messages[0]
        receipt_handle = message["ReceiptHandle"]
        body = json.loads(message["Body"])

        entity_id = body["entity_id"]
        task_name = body["task_name"]

        try:
            result = await callback(
                entity_id=entity_id,
                task_name=task_name,
                task_config=body.get("task_config", {}),
                metadata=body.get("metadata", {}),
                **callback_kwargs,
            )

            # Delete only on success — failure returns message to queue
            self.sqs_client.delete_message(
                QueueUrl=self.queue_url,
                ReceiptHandle=receipt_handle,
            )

            return {
                "entity_id": entity_id,
                "task_name": task_name,
                "result": result,
                "status": "completed",
            }

        except Exception as e:
            logger.error(f"Task {task_name} failed for {entity_id}: {e}")
            # Message returns to queue after visibility timeout for automatic retry
            return {
                "entity_id": entity_id,
                "task_name": task_name,
                "error": str(e),
                "status": "failed",
            }

    def get_queue_status(self) -> dict:
        """Get current queue metrics for monitoring."""
        attrs = self.sqs_client.get_queue_attributes(
            QueueUrl=self.queue_url,
            AttributeNames=["All"],
        )["Attributes"]

        return {
            "messages_available": int(attrs.get("ApproximateNumberOfMessages", 0)),
            "messages_in_flight": int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0)),
            "messages_delayed": int(attrs.get("ApproximateNumberOfMessagesDelayed", 0)),
        }

    def get_dlq_messages(self, max_messages: int = 10) -> list[dict]:
        """Retrieve failed messages from DLQ for inspection.

        Messages are received with a short visibility timeout (30s) for
        inspection without permanent consumption.
        """
        if not self.dlq_url:
            logger.warning("No DLQ configured")
            return []

        response = self.sqs_client.receive_message(
            QueueUrl=self.dlq_url,
            MaxNumberOfMessages=max_messages,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
            VisibilityTimeout=30,
        )

        results = []
        for msg in response.get("Messages", []):
            body = json.loads(msg["Body"])
            results.append({
                "entity_id": body.get("entity_id"),
                "task_name": body.get("task_name"),
                "retry_count": body.get("retry_count", 0),
                "timestamp": body.get("timestamp"),
                "receipt_handle": msg["ReceiptHandle"],
            })
        return results
```

## Initialization Pattern

```python
import boto3
import os

# Initialize SQS client — IAM roles only, never access keys
sqs_client = boto3.client("sqs", region_name=os.environ["AWS_DEFAULT_REGION"])

queue_url = os.environ["SQS_TASK_QUEUE_URL"]
dlq_url = os.getenv("SQS_DLQ_URL")

handler = TaskQueueHandler(
    sqs_client=sqs_client,
    queue_url=queue_url,
    dlq_url=dlq_url,
)
```

---

## SQS Design Principles

### MessageGroupId Strategy

```
MessageGroupId = f"{entity_id}-{task_name}"
```

This is the critical design decision for parallel processing:

- **Each task gets its own message group** — SQS delivers from different groups to different consumers simultaneously
- **Same task for same entity stays ordered** — Retries of the same task are processed sequentially
- **Cross-entity parallelism** — Tasks for different entities process in parallel

**Example**: Processing 42 fields for a document:
```
MessageGroup: doc-123-yearBuilt    → Container 1
MessageGroup: doc-123-roofType     → Container 2
MessageGroup: doc-123-sprinklered  → Container 3
MessageGroup: doc-456-yearBuilt    → Container 1 (parallel with doc-123 tasks)
```

### MessageDeduplicationId Strategy

```
MessageDeduplicationId = f"{entity_id}-{task_name}-{timestamp}"
```

Prevents duplicate task enqueue within the 5-minute SQS deduplication window.

### Delete-Only-On-Success

```
Processing succeeds → delete_message() → removed from queue
Processing fails   → DO NOT delete → returns to queue after visibility timeout
                                    → DLQ after max receive count
```

This is the core retry mechanism. Never delete on failure.

### Visibility Timeout

Set to the maximum expected task processing time (e.g., 900s = 15 minutes for LLM/ML tasks):

| Task Type | Recommended Timeout |
|-----------|-------------------|
| Fast API calls | 60s |
| Database operations | 120s |
| LLM inference | 300-900s |
| ML model processing | 600-900s |
| Multi-step pipeline | 900s |

### Long Polling

```python
WaitTimeSeconds=5  # 5 seconds
```

Reduces empty `receive_message` calls and SQS API costs. The consumer blocks for up to 5 seconds waiting for messages before returning empty.

---

## SQS IAM Permissions

Required IAM permissions for the service role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sqs:SendMessage",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueAttributes",
                "sqs:GetQueueUrl"
            ],
            "Resource": [
                "arn:aws:sqs:*:*:{queue-name-pattern}.fifo"
            ]
        }
    ]
}
```

---

## Parallel Processing Model

```
SQS FIFO Queue
  │
  ├── MessageGroup: entity-1-task-A ──► Container 1
  ├── MessageGroup: entity-1-task-B ──► Container 2
  ├── MessageGroup: entity-2-task-A ──► Container 1
  └── MessageGroup: entity-2-task-C ──► Container 3
```

SQS automatically distributes messages from different message groups to different consumers. No custom load balancing needed.

## Cost Considerations

SQS FIFO pricing (US-East-1):
- **$0.50 per 1M requests** after 1M free per month
- A typical pipeline with 40 tasks per entity and 1,000 entities/month = 40,000 requests/month
- **Cost: ~$0.02/month** — well within free tier

The cost of SQS is negligible compared to the operational benefits of per-task retry and error isolation.
