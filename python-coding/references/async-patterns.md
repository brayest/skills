# Async/Await Patterns for Python Applications

## Producer-Consumer Pattern with asyncio.Queue

### Overview

Decouple message production from consumption using `asyncio.Queue` for buffering. This pattern prevents fast producers from overwhelming slow consumers and enables concurrent processing.

### Architecture

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│ Producer        │─ put ──▶│ Queue        │─ get ──▶│ Consumer        │
│ (Background     │         │ (asyncio)    │         │ (Background     │
│  Task)          │         │              │         │  Task)          │
└─────────────────┘         └──────────────┘         └─────────────────┘
```

### Implementation

**1. Initialize Queue in Async Context**

```python
class MessageService:
    def __init__(self):
        self.message_queue = None  # Don't create queue in __init__
        self.running = False
        self.producer_task = None
        self.consumer_task = None

    async def start(self):
        """Initialize queue when event loop is running."""
        # Create queue in async context
        self.message_queue = asyncio.Queue(maxsize=100)
        self.running = True

        # Start background tasks
        self.producer_task = asyncio.create_task(self._producer())
        self.consumer_task = asyncio.create_task(self._consumer())

        # Wait for tasks
        await asyncio.gather(self.producer_task, self.consumer_task)
```

**2. Producer Task**

```python
async def _producer(self):
    """Background task that produces messages."""
    while self.running:
        try:
            # Fetch message from source (database, API, etc.)
            message = await self.fetch_next_message()

            if message is None:
                await asyncio.sleep(0.1)  # Prevent tight loop
                continue

            # Enqueue message with timestamp for tracking
            await self.message_queue.put((message, time.time()))

        except asyncio.QueueFull:
            # Handle backpressure
            logger.warning("Queue full - dropping message")
            await asyncio.sleep(1)  # Back off

        except Exception as e:
            logger.error(f"Producer error: {e}")
            await asyncio.sleep(1)  # Back off on error
```

**3. Consumer Task**

```python
async def _consumer(self):
    """Background task that consumes messages."""
    while self.running:
        try:
            # Get message with timeout
            message, queued_time = await asyncio.wait_for(
                self.message_queue.get(),
                timeout=0.1
            )

            # Track queue delay
            queue_delay = time.time() - queued_time
            logger.debug(f"Processing after {queue_delay:.2f}s queue delay")

            # Process in separate task to avoid blocking
            task = asyncio.create_task(self._process_message(message))
            # Add cleanup callback
            task.add_done_callback(lambda t: logger.debug("Task complete"))

        except asyncio.TimeoutError:
            continue  # No message, keep waiting

        except Exception as e:
            logger.error(f"Consumer error: {e}")
            await asyncio.sleep(1)
```

### Benefits

- **Decoupling:** Producer and consumer run independently
- **Backpressure:** Queue size limits prevent memory explosion
- **Monitoring:** Queue depth indicates system health
- **Non-blocking:** Processing doesn't block production

---

## Background Task Management

### Creating and Tracking Tasks

```python
class TaskManager:
    def __init__(self):
        self.tasks: Set[asyncio.Task] = set()

    async def create_task(self, coro):
        """Create task and track it."""
        task = asyncio.create_task(coro)
        self.tasks.add(task)

        # Auto-remove when done
        task.add_done_callback(self.tasks.discard)

        return task

    async def wait_for_all(self, timeout: float = 30.0):
        """Wait for all tasks to complete."""
        if not self.tasks:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*self.tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"{len(self.tasks)} tasks did not complete in time")
            # Cancel remaining tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()
```

### Usage

```python
class BackgroundService:
    def __init__(self):
        self.task_manager = TaskManager()
        self.running = False

    async def process_items(self, items: List[Any]):
        """Process items concurrently."""
        for item in items:
            await self.task_manager.create_task(
                self._process_item(item)
            )

        # Wait for all to complete
        await self.task_manager.wait_for_all()

    async def _process_item(self, item: Any):
        """Process single item."""
        try:
            await asyncio.sleep(1)  # Simulate work
            logger.info(f"Processed {item}")
        except Exception as e:
            logger.error(f"Failed to process {item}: {e}")
```

---

## Async/Sync Bridge Pattern

### Challenge

Some libraries (boto3, DynamoDB, synchronous database drivers) are synchronous but need to be called from async code without blocking the event loop.

### Solution: ThreadPoolExecutor

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import boto3

class AsyncDynamoDBRepository:
    """Async wrapper for synchronous DynamoDB operations."""

    def __init__(self, table_name: str, max_workers: int = 20):
        # Create thread pool
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="dynamodb"
        )

        # Create synchronous client
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)

    async def get_item(self, key: dict) -> dict:
        """Async wrapper for get_item."""
        loop = asyncio.get_event_loop()

        # Run sync operation in thread pool
        response = await loop.run_in_executor(
            self.executor,
            lambda: self.table.get_item(Key=key)
        )

        return response.get('Item')

    async def put_item(self, item: dict) -> None:
        """Async wrapper for put_item."""
        loop = asyncio.get_event_loop()

        await loop.run_in_executor(
            self.executor,
            lambda: self.table.put_item(Item=item)
        )

    def cleanup(self):
        """Shutdown thread pool."""
        self.executor.shutdown(wait=True)
```

### Usage

```python
async def main():
    repository = AsyncDynamoDBRepository('my-table')

    try:
        # Use async interface
        item = await repository.get_item({'id': '123'})
        await repository.put_item({'id': '456', 'name': 'Test'})
    finally:
        # Clean up thread pool
        repository.cleanup()
```

### Important Considerations

- **Thread Safety:** Ensure sync operations are thread-safe
- **Resource Limits:** Set appropriate `max_workers` based on load
- **Cleanup:** Always shutdown executor to prevent resource leaks
- **Error Handling:** Exceptions raised in executor propagate to async code

---

## Graceful Shutdown Pattern

### Signal Handling

```python
import asyncio
import signal
import sys

class GracefulService:
    def __init__(self):
        self.running = False
        self.tasks: Set[asyncio.Task] = set()

    async def start(self):
        """Start service with signal handlers."""
        self.running = True

        # Register signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self.stop)

        try:
            await self.run()
        finally:
            await self.cleanup()

    def stop(self):
        """Signal handler - sets running flag."""
        logger.info("Shutdown signal received")
        self.running = False

    async def run(self):
        """Main service loop."""
        while self.running:
            await asyncio.sleep(1)

    async def cleanup(self):
        """Graceful cleanup sequence."""
        logger.info("Starting graceful shutdown...")

        # 1. Wait for active tasks
        if self.tasks:
            logger.info(f"Waiting for {len(self.tasks)} active tasks...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.tasks, return_exceptions=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("Tasks did not complete - cancelling")
                for task in self.tasks:
                    if not task.done():
                        task.cancel()

        # 2. Flush observability data
        from shared.observability import flush_observability
        flush_observability()

        # 3. Close network connections
        # (database, message queues, etc.)

        # 4. Shutdown thread pools
        # executor.shutdown(wait=True)

        logger.info("Shutdown complete")
```

### Usage

```python
async def main():
    service = GracefulService()
    await service.start()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Error Recovery with Exponential Backoff

### Pattern

Retry failed operations with increasing delays to avoid overwhelming failing services.

```python
import asyncio
import logging

async def exponential_backoff_retry(
    coro_func,
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """
    Retry coroutine with exponential backoff.

    Args:
        coro_func: Async function to retry
        max_retries: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch

    Returns:
        Result of coro_func

    Raises:
        Last exception if all retries fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await coro_func()

        except exceptions as e:
            last_exception = e

            if attempt == max_retries:
                logger.error(f"All retries exhausted: {e}")
                raise

            # Calculate delay: 1s, 2s, 4s, 8s, 16s, max 60s
            delay = min(base_delay * (2 ** attempt), max_delay)

            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                f"Retrying in {delay:.1f}s"
            )

            await asyncio.sleep(delay)

    raise last_exception
```

### Usage

```python
async def fetch_data_from_api():
    """Potentially failing API call."""
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.example.com/data') as resp:
            resp.raise_for_status()
            return await resp.json()

# Retry with exponential backoff
data = await exponential_backoff_retry(
    fetch_data_from_api,
    max_retries=5,
    exceptions=(aiohttp.ClientError, asyncio.TimeoutError)
)
```

### Circuit Breaker Pattern

For more sophisticated error handling:

```python
from datetime import datetime, timedelta

class CircuitBreaker:
    """Circuit breaker for failing services."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open

    async def call(self, coro_func):
        """Call function through circuit breaker."""
        # Check if circuit should close
        if self.state == 'open':
            if datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = 'half_open'
                self.failures = 0
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await coro_func()

            # Success - reset failures
            if self.state == 'half_open':
                self.state = 'closed'
            self.failures = 0

            return result

        except Exception as e:
            self.failures += 1
            self.last_failure_time = datetime.utcnow()

            # Open circuit if threshold exceeded
            if self.failures >= self.failure_threshold:
                self.state = 'open'
                logger.error("Circuit breaker opened")

            raise
```

---

## Task Lifecycle Management

### Concurrent Task Processing

```python
class ConcurrentProcessor:
    """Process items concurrently with controlled concurrency."""

    def __init__(self, max_concurrent: int = 10):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def process_batch(self, items: List[Any]):
        """Process batch with concurrency limit."""
        tasks = [
            self._process_with_semaphore(item)
            for item in items
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Separate successes from errors
        successes = [r for r in results if not isinstance(r, Exception)]
        errors = [r for r in results if isinstance(r, Exception)]

        logger.info(f"Processed {len(successes)} items, {len(errors)} errors")

        return successes, errors

    async def _process_with_semaphore(self, item: Any):
        """Process item with semaphore for concurrency control."""
        async with self.semaphore:
            return await self._process_item(item)

    async def _process_item(self, item: Any):
        """Process single item."""
        await asyncio.sleep(1)  # Simulate work
        return f"Processed {item}"
```

### Usage

```python
processor = ConcurrentProcessor(max_concurrent=10)
items = list(range(100))

successes, errors = await processor.process_batch(items)
```

---

## Async Context Managers

### Pattern

```python
class AsyncDatabaseConnection:
    """Async context manager for database connections."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.connection = None

    async def __aenter__(self):
        """Async entry - establish connection."""
        self.connection = await self._connect()
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async exit - close connection."""
        if self.connection:
            await self.connection.close()
        return False  # Don't suppress exceptions

    async def _connect(self):
        """Establish database connection."""
        await asyncio.sleep(0.1)  # Simulate connection
        return {"connected": True}
```

### Usage

```python
async def fetch_user(user_id: str):
    """Fetch user with automatic connection management."""
    async with AsyncDatabaseConnection("postgresql://...") as conn:
        # Connection automatically closed when block exits
        result = await conn.execute("SELECT * FROM users WHERE id = $1", user_id)
        return result
```

---

## Anti-Patterns to Avoid

### ❌ Blocking Operations in Async Code

```python
# ❌ BAD - Blocks event loop
async def bad_fetch():
    import requests  # Synchronous library
    response = requests.get('https://api.example.com')  # BLOCKS!
    return response.json()
```

**Solution:** Use async libraries or ThreadPoolExecutor

```python
# ✅ GOOD - Non-blocking
async def good_fetch():
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get('https://api.example.com') as resp:
            return await resp.json()
```

### ❌ Forgotten await

```python
# ❌ BAD - Returns coroutine object, doesn't execute
async def process():
    result = async_function()  # Missing await!
    return result
```

**Solution:** Always await coroutines

```python
# ✅ GOOD
async def process():
    result = await async_function()
    return result
```

### ❌ Creating Tasks Without Tracking

```python
# ❌ BAD - Task created but not tracked
async def bad_pattern():
    asyncio.create_task(background_work())
    # Task runs but no way to wait for it or handle errors
```

**Solution:** Track tasks and handle errors

```python
# ✅ GOOD
async def good_pattern():
    task = asyncio.create_task(background_work())
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    # Can wait for tasks before shutdown
```

### ❌ Not Handling CancelledError

```python
# ❌ BAD - Ignores cancellation
async def bad_cleanup():
    try:
        await long_operation()
    except Exception:
        pass  # Swallows CancelledError!
```

**Solution:** Handle cancellation explicitly

```python
# ✅ GOOD
async def good_cleanup():
    try:
        await long_operation()
    except asyncio.CancelledError:
        logger.info("Task cancelled - cleaning up")
        await cleanup()
        raise  # Re-raise to propagate cancellation
    except Exception as e:
        logger.error(f"Error: {e}")
```

---

## Performance Tips

### 1. Use uvloop for Production

```python
import asyncio
import uvloop

# Replace event loop with uvloop for 2-4x performance
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

async def main():
    # Your async code here
    pass

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Batch Operations

```python
# Instead of processing one at a time
for item in items:
    await process(item)  # Each awaits separately

# Batch process for better performance
await asyncio.gather(*[process(item) for item in items])
```

### 3. Use asyncio.TaskGroup (Python 3.11+)

```python
async def process_batch(items: List[Any]):
    """Process batch with TaskGroup."""
    async with asyncio.TaskGroup() as tg:
        for item in items:
            tg.create_task(process_item(item))
    # All tasks complete when exiting context
```

### 4. Set Appropriate Timeouts

```python
# Always set timeouts to prevent hanging
try:
    result = await asyncio.wait_for(
        slow_operation(),
        timeout=30.0
    )
except asyncio.TimeoutError:
    logger.error("Operation timed out")
```
