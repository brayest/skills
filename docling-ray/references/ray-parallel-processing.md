# Ray Parallel Processing for Docling

## Why Ray for Docling

1. **Python GIL** — Docling is CPU-bound (layout analysis, OCR preprocessing). Multiple threads cannot parallelize CPU work due to the GIL. Ray actors run in separate processes, bypassing the GIL entirely.

2. **GPU sharing** — OCR inference requires GPU. Ray's fractional GPU allocation allows multiple workers to share one physical GPU without manual CUDA context management.

3. **Memory isolation** — Each actor has its own DocumentConverter with loaded models. No shared mutable state, no locking needed.

4. **Fault tolerance** — If a worker crashes (OOM, segfault from native C/C++ code), Ray restarts it automatically without affecting other workers or the main process.

## Actor Design

```python
import os
import logging
from typing import Dict, Any

import ray

@ray.remote
class DoclingWorkerActor:
    """
    Ray actor for Docling document processing.

    Each actor runs in its own process with its own DocumentConverter
    and chunking pipeline instances, ensuring isolation and thread-safety.
    """

    def __init__(
        self,
        enable_ocr: bool = True,
        enable_table_structure: bool = True,
        max_tokens: int = 512,
        merge_peers: bool = True,
    ):
        # Configure logging in worker process (separate from main)
        configure_logging()

        # Deferred imports: each process loads its own instances
        # Importing at module level would load models in the main process (wasted memory)
        from document_processor import DoclingProcessor
        from chunking_pipeline import ChunkingPipeline

        self.processor = DoclingProcessor(
            enable_ocr=enable_ocr,
            enable_table_structure=enable_table_structure,
        )
        self.chunker = ChunkingPipeline(
            max_tokens=max_tokens,
            merge_peers=merge_peers,
        )

        self.worker_id = os.getpid()
        logger.info(f"DoclingWorkerActor initialized (PID: {self.worker_id})")

    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Process document: convert once, extract all content types.
        Returns plain dicts (not framework objects) for safe Ray serialization.
        """
        # Single conversion
        doc = self.processor.convert_document(file_path)

        # Extract all content types from the same DoclingDocument
        nodes = self.chunker.chunk_document(doc)
        tables = self.processor.extract_tables(doc)
        images = self.processor.extract_images(doc)

        # Serialize to plain dicts for Ray object store transport
        # Framework objects (TextNode, PIL Image) may fail pickle serialization
        node_data = [
            {"text": n.text, "metadata": self.chunker.get_metadata(n)}
            for n in nodes
        ]

        return {
            "nodes": node_data,
            "tables": tables,         # Already plain dicts
            "images": images,         # bytes are Ray-serializable
            "node_count": len(nodes),
            "table_count": len(tables),
            "image_count": len(images),
        }

    def health_check(self) -> Dict[str, Any]:
        return {"worker_id": self.worker_id, "status": "healthy"}
```

### Critical Actor Patterns

| Pattern | Explanation |
|---------|-------------|
| **Imports inside `__init__`** | Each Ray actor is a separate Python process. Importing at module level loads models in the main process (wasted memory). Deferred imports ensure models load only in worker processes. |
| **`configure_logging()` per worker** | Ray workers are separate processes. Without explicit logging setup, they use Ray's default (plain text), breaking structured JSON logging. |
| **Serialize to plain dicts** | LlamaIndex `TextNode` objects use complex inheritance. Ray's object store serializes via pickle, which can fail on framework objects. Convert to dicts before returning. |
| **Return images as `bytes`** | PIL Image objects don't serialize cleanly across Ray. Convert to PNG bytes in the worker, transport as bytes through the object store. |

## Worker Pool

```python
from typing import List, Dict, Any, Optional

class RayWorkerPool:
    """
    Manages a pool of DoclingWorkerActor instances.
    Provides round-robin worker selection for load balancing.
    """

    def __init__(
        self,
        num_workers: int = 2,
        gpu_per_worker: float = 0.5,
        cpu_per_worker: int = 1,
        **docling_kwargs,
    ):
        self.num_workers = num_workers
        self.gpu_per_worker = gpu_per_worker
        self.cpu_per_worker = cpu_per_worker
        self.docling_kwargs = docling_kwargs
        self.workers: List[ray.actor.ActorHandle] = []
        self._next_worker = 0

    def initialize(self):
        """Create worker actors with configured resource allocation."""
        ActorClass = DoclingWorkerActor.options(
            num_gpus=self.gpu_per_worker,
            num_cpus=self.cpu_per_worker,
            max_restarts=3,       # Auto-restart crashed workers
            max_task_retries=2,   # Retry failed tasks on restarted worker
        )

        self.workers = [
            ActorClass.remote(**self.docling_kwargs)
            for _ in range(self.num_workers)
        ]

    def get_worker(self) -> ray.actor.ActorHandle:
        """Round-robin worker selection."""
        if not self.workers:
            raise RuntimeError("Worker pool not initialized. Call initialize() first.")

        worker = self.workers[self._next_worker]
        self._next_worker = (self._next_worker + 1) % self.num_workers
        return worker

    def process_documents_parallel(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Submit all documents and wait for all results."""
        futures = []
        for file_path in file_paths:
            worker = self.get_worker()
            future = worker.process_document.remote(file_path)
            futures.append(future)

        return ray.get(futures)

    def health_check(self) -> List[Dict[str, Any]]:
        if not self.workers:
            return []
        futures = [w.health_check.remote() for w in self.workers]
        return ray.get(futures)

    def shutdown(self):
        """Shutdown all worker actors."""
        for worker in self.workers:
            try:
                ray.kill(worker)
            except Exception as e:
                logger.warning(f"Error killing worker: {e}")
        self.workers = []
        self._next_worker = 0
```

## Fractional GPU Allocation

Ray allows fractional GPU assignment — the key to maximizing GPU utilization:

```
4 workers x 0.25 GPU = 1 physical GPU fully utilized
2 workers x 0.50 GPU = 1 physical GPU fully utilized
```

Ray manages time-sharing on the GPU. Workers alternate GPU access at the CUDA operation level. This works because Docling's GPU usage is **bursty** (OCR inference kernels with CPU preprocessing between them).

### Choosing the Right Fraction

| Workers | GPU/Worker | Total GPU | Trade-off |
|---------|-----------|-----------|-----------|
| 2 | 0.50 | 1.0 | Lower concurrency, more GPU per OCR batch |
| 4 | 0.25 | 1.0 | Higher concurrency, slight GPU contention on large pages |
| 8 | 0.125 | 1.0 | Maximum concurrency, significant GPU contention |

**Recommendation**: Start with `4 workers x 0.25 GPU`. Docling's OCR operations are short-lived, so contention is low. Monitor GPU utilization and adjust.

## Ray Initialization

```python
import logging
import ray

if not ray.is_initialized():
    ray.init(
        num_cpus=4,
        num_gpus=1,
        include_dashboard=False,      # No overhead from unused dashboard
        log_to_driver=False,          # Prevent workers forwarding stdout to main
        configure_logging=False,      # Don't override application's JSON logging
        logging_level=logging.WARNING # Suppress verbose Ray internals
    )
```

**Logging suppression is critical**: Without `log_to_driver=False` and `configure_logging=False`, Ray overrides the application's structured JSON logging with its own plain-text format. This breaks log aggregation in centralized logging systems.

## Non-Blocking Async Integration

Ray's `ray.get()` is blocking. In an async web framework (FastAPI, Starlette), blocking the event loop prevents handling other requests. Use cooperative polling:

```python
import asyncio

async def wait_for_ray_result(future, timeout: float = 0.1):
    """Non-blocking wait for Ray future."""
    import ray
    while True:
        # ray.wait with timeout: non-blocking check
        ready, _ = await asyncio.to_thread(ray.wait, [future], timeout=timeout)
        if ready:
            return ray.get(ready[0])
        # Yield control back to event loop
        await asyncio.sleep(0)
```

**How it works:**

1. `asyncio.to_thread(ray.wait, ...)` moves the blocking call to a thread pool
2. `timeout=0.1` means each check takes max 100ms
3. `await asyncio.sleep(0)` yields to the event loop between checks
4. Other web requests continue processing while waiting for Ray results

**Comparison:**

```python
# BAD: Blocks the entire event loop — all other requests stall
result = ray.get(future)

# GOOD: Cooperative polling — other requests continue
result = await wait_for_ray_result(future)
```

## Processing Patterns

### Stream Processing (Message Queue)

Submit one document per message, wait asynchronously:

```python
async def process_message(doc_id: str, file_path: str):
    worker = worker_pool.get_worker()
    future = worker.process_document.remote(file_path)
    result = await wait_for_ray_result(future)
    # Continue with embeddings, indexing in main process...
```

### Batch Processing

Submit all documents, wait for all results:

```python
def process_batch(file_paths: list[str]):
    return worker_pool.process_documents_parallel(file_paths)
```

## Work Division: Ray Workers vs Main Process

| Operation | Where | Why |
|-----------|-------|-----|
| Docling conversion (OCR, layout) | Ray worker | CPU+GPU bound, benefits from parallelism |
| Chunking (HybridChunker) | Ray worker | Tightly coupled with conversion output |
| Table extraction | Ray worker | Reads from same DoclingDocument in memory |
| Image extraction (PIL to bytes) | Ray worker | Avoids serializing PIL objects across processes |
| Embedding generation | Main process | API calls (async I/O), not CPU bound |
| Image VLM/multimodal analysis | Main process | API calls (async I/O), shared client |
| Vector DB indexing | Main process | Bulk HTTP calls, async |
| Cloud storage uploads | Main process | API calls (async I/O) |
| Event publishing | Main process | Lightweight I/O |

**Rationale**: CPU/GPU work goes to Ray workers. I/O-bound work (API calls, network) stays in the main async process where `asyncio` handles concurrency efficiently.

## Concurrency Control

Limit concurrent in-flight tasks to match the number of Ray workers:

```python
max_concurrent_tasks = num_workers if ray_enabled else 1
```

This prevents queuing more documents than workers can handle, avoiding memory buildup from pending Ray futures in the object store.

## Serial Fallback

When Ray is disabled (local development, debugging), fall back to serial processing:

```python
if ray_enabled and worker_pool:
    return await process_with_ray(doc_id, file_path)

# Serial fallback: process in main process
doc = processor.convert_document(file_path)
nodes = chunker.chunk_document(doc)
tables = processor.extract_tables(doc)
```

**When to use serial mode:**
- Local development (no GPU available)
- Debugging (simpler stack traces, no cross-process issues)
- Low-volume environments where parallelism overhead is not justified

## Lifecycle Management

### Application Startup (FastAPI Lifespan)

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    # Initialize Ray
    if ray_enabled:
        ray.init(num_cpus=4, num_gpus=1, include_dashboard=False,
                 log_to_driver=False, configure_logging=False,
                 logging_level=logging.WARNING)

        worker_pool = RayWorkerPool(
            num_workers=num_workers,
            gpu_per_worker=gpu_per_worker,
            cpu_per_worker=cpu_per_worker,
            enable_ocr=True,
            enable_table_structure=True,
            max_tokens=chunk_max_tokens,
            merge_peers=True,
        )
        worker_pool.initialize()
    else:
        # Serial mode: initialize in main process
        processor = DoclingProcessor(enable_ocr=True, enable_table_structure=True)
        chunker = ChunkingPipeline(max_tokens=chunk_max_tokens, merge_peers=True)

    yield

    # Shutdown
    if worker_pool:
        worker_pool.shutdown()
    if ray.is_initialized():
        ray.shutdown()
```

### Graceful Shutdown

```python
# 1. Stop accepting new work (message consumer, etc.)
# 2. Kill Ray workers (ray.kill sends SIGKILL — immediate)
worker_pool.shutdown()
# 3. Shutdown Ray runtime
ray.shutdown()
```

**Limitation**: `ray.kill()` sends SIGKILL, not SIGTERM. In-flight tasks are interrupted without cleanup. For production, consider `ray.cancel()` with a grace period before `ray.kill()`.
