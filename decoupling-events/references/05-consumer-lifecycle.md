# Consumer Lifecycle Management

## Async Kafka Consumer with Worker Pool

The recommended pattern separates polling from processing using an `asyncio.Queue` for backpressure:

```python
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class AsyncKafkaService:
    """Service that consumes Kafka messages with concurrent async workers.

    Architecture:
    - Single poll loop reads from Kafka
    - asyncio.Queue buffers messages (backpressure)
    - N worker coroutines process messages concurrently
    - Each worker commits offset after processing
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=max_workers * 2)
        self.running = True
        self.consumer = None
        self.producer = None

    async def start(self):
        """Initialize Kafka clients and start polling + workers."""
        self._init_kafka_clients()

        workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_workers)
        ]

        polling = asyncio.create_task(self._poll_loop())
        await asyncio.gather(polling, *workers, return_exceptions=True)

    async def _poll_loop(self):
        """Poll Kafka and queue messages for workers.

        Backpressure: if the queue is full, this coroutine blocks until
        a worker frees a slot. This naturally slows down Kafka polling
        when workers are saturated.
        """
        while self.running:
            msg = self.consumer.poll(timeout=0.5)

            if msg is None:
                await asyncio.sleep(0.05)
                continue

            if msg.error():
                self._handle_kafka_error(msg.error())
                continue

            message_data = json.loads(msg.value().decode("utf-8"))

            # Blocks if queue is full — backpressure mechanism
            await self.task_queue.put({"data": message_data, "kafka_msg": msg})

    async def _worker(self, worker_id: int):
        """Worker coroutine that processes tasks from the internal queue.

        Each worker:
        1. Gets a task from the queue
        2. Processes it (calls _process)
        3. Commits the Kafka offset
        4. On failure: publishes error, still commits (prevents poison pill)
        """
        while self.running:
            try:
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if task is None:  # Shutdown sentinel
                break

            try:
                await self._process(task["data"])
                self.consumer.commit(task["kafka_msg"])
            except Exception as e:
                logger.error(f"Worker {worker_id} failed: {e}")
                await self._publish_error(task["data"], str(e))
                self.consumer.commit(task["kafka_msg"])  # Commit to prevent poison pill

    async def shutdown(self):
        """Graceful shutdown: drain queue, close connections."""
        self.running = False

        # Send shutdown sentinels to all workers
        for _ in range(self.max_workers):
            await self.task_queue.put(None)

        if self.producer:
            self.producer.flush(timeout=10)
        if self.consumer:
            self.consumer.close()
```

### Concurrency Model

```
Kafka Partition 0 ──┐
Kafka Partition 1 ──┤     ┌─────────────┐     ┌──────────┐
Kafka Partition 2 ──┼──►  │ Poll Loop   │──►  │ asyncio  │──► Worker 0
                    │     │ (single     │     │ Queue    │──► Worker 1
                    │     │  coroutine) │     │ (buffer) │──► Worker 2
                    │     └─────────────┘     └──────────┘──► Worker N
```

**Why this pattern works**:
- `confluent-kafka` poll is synchronous — runs in a single coroutine
- `asyncio.Queue` provides natural backpressure — poll blocks when workers are busy
- Workers process concurrently via `asyncio.gather`
- Each worker commits its own offset after processing

---

## SQS Polling Loop

For SQS-based task processing, a background polling coroutine:

```python
async def _sqs_polling_loop(self):
    """Background task for continuous SQS consumption.

    Processes one message at a time per loop iteration.
    Scale horizontally by running multiple containers.
    """
    while self.running:
        try:
            result = await self.sqs_handler.process_one(
                callback=self._process_task,
            )

            if result is None:
                # No messages available — brief backoff
                await asyncio.sleep(0.1)
            elif result["status"] == "completed":
                await self._on_task_complete(result)
            else:
                await self._on_task_failed(result)

        except Exception as e:
            logger.error(f"SQS polling error: {e}")
            await asyncio.sleep(1)  # Backoff on unexpected errors
```

---

## Combined Kafka + SQS Service

When a service consumes Kafka events and distributes tasks via SQS:

```python
class HybridService:
    """Service that consumes Kafka events and fans out work via SQS.

    Kafka consumer receives coarse-grained events.
    SQS handles fine-grained task distribution and retry.
    """

    def __init__(self):
        self.running = True
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=10)

    async def start(self):
        """Start all polling loops concurrently."""
        self._init_kafka_clients()
        self._init_sqs_client()

        tasks = [
            asyncio.create_task(self._kafka_polling()),
            asyncio.create_task(self._message_processor()),
            asyncio.create_task(self._sqs_polling()),
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _kafka_polling(self):
        """Poll Kafka and queue messages for processing."""
        while self.running:
            msg = self.consumer.poll(timeout=1.0)
            if msg is None:
                await asyncio.sleep(0.05)
                continue
            if msg.error():
                self._handle_kafka_error(msg.error())
                continue

            message_data = json.loads(msg.value().decode("utf-8"))
            await self.message_queue.put((msg, message_data))

    async def _message_processor(self):
        """Process Kafka messages: decompose into SQS tasks."""
        while self.running:
            try:
                kafka_msg, data = await asyncio.wait_for(
                    self.message_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            try:
                # Decompose into fine-grained tasks
                tasks = self._build_task_list(data)

                # Enqueue to SQS for parallel processing
                self.sqs_handler.enqueue_tasks(
                    entity_id=data["entity_id"],
                    tasks=tasks,
                    metadata={"organization": data.get("organization")},
                )

                self.consumer.commit(kafka_msg)

            except Exception as e:
                logger.error(f"Failed to process message: {e}")
                await self._publish_error(data, str(e))
                self.consumer.commit(kafka_msg)

    async def _sqs_polling(self):
        """Process SQS tasks (field-level work)."""
        while self.running:
            result = await self.sqs_handler.process_one(
                callback=self._process_single_task,
            )
            if result is None:
                await asyncio.sleep(0.1)
```

### Topic Routing

When subscribing to multiple Kafka topics, route messages by topic:

```python
async def _route_message(self, msg, data: dict) -> None:
    """Route a message to the appropriate handler based on topic."""
    topic = msg.topic()

    if topic == self.topics["stage_complete"]:
        await self._handle_stage_complete(data, msg)
    elif topic == self.topics["task_reprocess"]:
        await self._handle_task_reprocess(data, msg)
    elif topic == self.topics["cache_refresh"]:
        await self._handle_cache_refresh(data, msg)
    elif topic == self.topics["job_control"]:
        await self._handle_job_control(data, msg)
    else:
        logger.warning(f"Unknown topic: {topic}")
        self.consumer.commit(msg)
```

---

## FastAPI Lifespan Integration

Integrate consumer loops with FastAPI startup/shutdown:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start consumer on startup, shutdown on teardown."""
    # Startup
    logger.info("Starting service...")
    service = AsyncKafkaService()
    consumer_task = asyncio.create_task(service.start())

    yield

    # Shutdown
    logger.info("Shutting down service...")
    await service.shutdown()
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)
```

### Startup Sequence

1. FastAPI app starts
2. Lifespan creates the service and starts the consumer task
3. Consumer subscribes to topics and waits for partition assignment
4. Worker coroutines begin processing

### Shutdown Sequence

1. FastAPI receives SIGTERM
2. Lifespan sets `service.running = False`
3. Workers drain the asyncio queue
4. Producer flushes pending messages (10s timeout)
5. Consumer closes cleanly (commits final offsets)
6. FastAPI exits

---

## Backpressure Mechanisms

### Kafka Consumer Backpressure

```python
# Queue size = workers * 2 — allows buffering without unbounded growth
self.task_queue = asyncio.Queue(maxsize=max_workers * 2)

# poll_loop blocks on put() when queue is full
await self.task_queue.put(task)  # Blocks if full
```

When workers are saturated:
1. Queue fills up
2. `poll_loop` blocks on `queue.put()`
3. Kafka poll stops
4. Broker holds messages in the partition
5. When a worker finishes, queue accepts a new message, poll resumes

### SQS Consumer Backpressure

SQS has built-in backpressure:
- `MaxNumberOfMessages=1` — process one at a time
- `VisibilityTimeout` — message is invisible while being processed
- Scale by adding containers, not by increasing concurrency within a container

### Tuning Worker Count

| Workload Type | Recommended Workers | Rationale |
|---------------|-------------------|-----------|
| I/O-bound (API calls) | 8-16 | Async I/O can handle many concurrent requests |
| CPU-bound (ML inference) | Match CPU/GPU count | Workers compete for compute |
| Mixed (I/O + compute) | 4-8 | Balance between parallelism and resource contention |
| Ray integration | Match Ray worker count | 1:1 mapping to Ray actors |

---

## Partition Assignment Wait

During startup, wait for partition assignment before processing:

```python
async def _wait_for_partition_assignment(self, timeout: float = 30.0):
    """Wait for the consumer to receive partition assignments.

    This prevents errors during the startup phase when the consumer
    is joining the group but hasn't been assigned partitions yet.
    """
    start = time.time()

    while time.time() - start < timeout:
        partitions = self.consumer.assignment()
        if partitions:
            logger.info(f"Assigned {len(partitions)} partitions")
            return
        self.consumer.poll(timeout=0.5)
        await asyncio.sleep(0.5)

    raise RuntimeError(f"No partition assignment after {timeout}s")
```

---

## Graceful Shutdown Checklist

1. Set `self.running = False` to signal all loops
2. Send `None` sentinels to worker queues
3. Wait for in-flight tasks to complete (with timeout)
4. Flush the Kafka producer (10s timeout)
5. Close the Kafka consumer (commits final offsets)
6. Shutdown thread pool executors (if using `run_in_executor`)
7. Flush observability/tracing data
