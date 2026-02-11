# Deployment, Resource Optimization & Tuning

## Dockerfile Structure

```dockerfile
FROM python:3.11-slim

# System dependencies for Docling, OpenCV, OCR
# - gcc/g++: Compilation of native extensions
# - libgl1, libglib2.0-0, libsm6, libxext6, libxrender-dev: OpenCV dependencies
# - libgomp1: OpenMP for parallel CPU processing
# - poppler-utils: PDF rendering
# - tesseract-ocr: OCR support for scanned PDFs
RUN apt-get update && apt-get install -y \
    gcc g++ \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 \
    poppler-utils \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check --no-compile -r requirements.txt

# Pre-download HuggingFace tokenizer at build time (not runtime)
# Prevents race conditions when multiple Ray workers start simultaneously
RUN python -c "from transformers import AutoTokenizer; \
    AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2')"

COPY app/ ./app/

# Ray configuration (override at runtime via docker-compose or k8s)
ENV RAY_ENABLED=true
ENV RAY_NUM_DOCLING_WORKERS=4
ENV RAY_GPU_PER_WORKER=0.25
ENV RAY_CPU_PER_WORKER=1
# Opt into future Ray behavior for GPU env var handling (suppress FutureWarning)
ENV RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO=0

EXPOSE 8000

# Extended start-period: Ray initialization + model loading takes ~60-90s
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Docker Compose

### Production (with GPU)

```yaml
services:
  extraction-service:
    build: .
    shm_size: '8gb'                  # Ray object store requires >= 8GB
    environment:
      - RAY_ENABLED=true
      - RAY_NUM_DOCLING_WORKERS=4
      - RAY_GPU_PER_WORKER=0.25
      - RAY_CPU_PER_WORKER=1
    # GPU passthrough (requires NVIDIA Container Toolkit)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### Local Development (no GPU)

```yaml
services:
  extraction-service:
    build:
      dockerfile: Dockerfile.local
    shm_size: '8gb'                  # Still useful for testing Ray locally
    environment:
      - RAY_ENABLED=false            # Serial mode, no GPU
      - RAY_GPU_PER_WORKER=0         # Explicit: no GPU allocation
```

## Kubernetes Health Probes

```yaml
livenessProbe:
  httpGet:
    path: /health/live               # Fast: just confirms process is alive
    port: 8000
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready              # Checks Ray pool + dependencies initialized
    port: 8000
  initialDelaySeconds: 120           # Ray + model loading takes ~60-90s
  periodSeconds: 10
```

### Health Endpoint Pattern

```python
@app.get("/health/live")
async def liveness_check():
    """Process alive — fast check, no dependencies."""
    return {"status": "alive"}

@app.get("/health/ready")
async def readiness_check():
    """Service initialized and ready to handle requests."""
    if not initialization_complete:
        return JSONResponse(status_code=503, content={"status": "initializing"})

    return {
        "status": "ready",
        "ray_enabled": ray_enabled,
        "ray_workers": num_workers if ray_enabled else 0,
        "ray_gpu_per_worker": gpu_per_worker if ray_enabled else 0,
    }
```

## Resource Optimization

### GPU Memory

| Setting | Impact | Recommendation |
|---------|--------|----------------|
| `images_scale=2.0` | 4x memory per page vs 1.0 | Use 2.0 for accuracy, 1.0 if OOM |
| `RAY_GPU_PER_WORKER` | Determines GPU time-share | 0.25 for 4 workers, monitor utilization |
| `force_full_page_ocr` | OCR processes every page | Required for vector-rendered tables |
| `shm_size` | Ray object store size | Minimum 8GB for production; 16GB for large documents |

### CPU Memory

Each Ray worker loads its own copies of:
- Docling DocumentConverter with OCR models (~200MB)
- HuggingFace tokenizer (~50MB)
- RapidOCR ONNX models (~40MB, loaded on first OCR call)

**Total per worker**: ~300-400MB. With 4 workers: ~1.2-1.6GB for worker processes alone.

**Mitigation strategies:**
- Pre-download models at build time (Dockerfile) to avoid runtime download race conditions
- RapidOCR models download on first use (~500ms startup delay per worker). Acceptable because workers are long-lived actors.
- Account for worker memory when sizing container memory limits

### Shared Memory (Ray Object Store)

Ray uses `/dev/shm` (shared memory) for its Plasma object store. Default Docker shared memory is 64MB, which forces Ray to spill to disk (severe performance impact).

```yaml
shm_size: '8gb'
```

**Why 8GB**: Document processing results (text chunks, image bytes, metadata) pass through the object store. A single large PDF can produce 10-50MB of serialized results. With 4 workers processing concurrently, 8GB provides safe headroom.

### Serialization Best Practices

Ray serializes actor return values through the object store. Minimize serialization cost:

```python
# GOOD: Return plain dicts with native types
return {
    "nodes": [{"text": "...", "metadata": {"page": 5}}],
    "images": [{"bytes": b"...", "format": "png"}],
}

# BAD: Return framework objects (complex pickle, potential failures)
return {
    "nodes": llama_index_text_nodes,  # Pickle may fail or be slow
    "images": pil_image_objects,       # Large, complex objects
}
```

## Error Handling & Resilience

### Ray Actor Recovery

```python
ActorClass = DoclingWorkerActor.options(
    max_restarts=3,       # Restart crashed worker up to 3 times
    max_task_retries=2,   # Retry failed task on restarted worker
)
```

**Worker crash sequence:**

1. Worker process dies (OOM, segfault, native code crash)
2. Ray detects failure via heartbeat
3. Ray restarts the actor (re-runs `__init__`, reloads Docling models)
4. Failed task is retried on the restarted worker
5. If all retries exhausted: exception propagates to the caller

### Fail-Fast Document Processing

```python
# File must exist — raise immediately
path = Path(file_path)
if not path.exists():
    raise FileNotFoundError(f"Document not found: {file_path}")

# Conversion must succeed — raise immediately
result = converter.convert(str(path))
if result.document is None:
    raise ValueError(f"Conversion failed for: {file_path}")
```

No fallbacks, no silent defaults. Conversion failures must surface immediately.

### Image Extraction Resilience

Images are supplementary content. A failed image extraction logs a warning but does not fail the entire document:

```python
for idx, picture in enumerate(doc.pictures):
    try:
        pil_image = picture.get_image(doc)
        # ... process image
    except Exception as e:
        logger.warning(f"Failed to extract image {idx}: {e}")
        # Continue with remaining images
```

This is an intentional exception to fail-fast: losing one image should not discard an entire document's text and table chunks.

### Embedding Retry with Exponential Backoff

```python
import random

for attempt in range(max_retries):
    try:
        embeddings = await loop.run_in_executor(None, generate_embeddings)
        return embeddings
    except Exception as e:
        if attempt == max_retries - 1:
            raise  # Final attempt: fail loud
        delay = (2 ** attempt) + random.uniform(0, 1)  # Jitter prevents thundering herd
        await asyncio.sleep(delay)
```

### Graceful Shutdown

```python
# 1. Stop accepting new work (message consumer, etc.)
consumer.shutdown()

# 2. Cancel consumer task
consumer_task.cancel()

# 3. Kill Ray workers
worker_pool.shutdown()  # ray.kill() each worker

# 4. Shutdown Ray runtime
if ray.is_initialized():
    ray.shutdown()
```

**Limitation**: `ray.kill()` sends SIGKILL (immediate). In-flight tasks are interrupted without cleanup. For production, consider `ray.cancel()` with a grace period before `ray.kill()`.

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `RAY_ENABLED` | `true` | Enable/disable Ray parallel processing |
| `RAY_NUM_DOCLING_WORKERS` | `2` | Number of parallel Docling worker actors |
| `RAY_GPU_PER_WORKER` | `0.5` | Fractional GPU per worker (sum must be <= total GPUs) |
| `RAY_CPU_PER_WORKER` | `1` | CPU cores per worker |
| `CHUNK_MAX_TOKENS` | `512` | Max tokens per text chunk |
| `CHUNK_MERGE_PEERS` | `true` | Merge small consecutive chunks under same heading |
| `EMBEDDING_BATCH_SIZE` | `10` | Texts per embedding API call |

## Scaling Guide

| Scenario | Workers | GPU/Worker | CPUs | shm_size |
|----------|---------|-----------|------|----------|
| Local dev (no GPU) | 0 (serial) | 0 | 2 | 4gb |
| Single GPU, low volume | 2 | 0.50 | 4 | 8gb |
| Single GPU, high volume | 4 | 0.25 | 8 | 8gb |
| Multi-GPU (2x) | 8 | 0.25 | 16 | 16gb |
| Multi-GPU (4x) | 16 | 0.25 | 32 | 32gb |

## Performance Characteristics

| Pipeline Stage | Typical Latency | Bottleneck |
|---------------|----------------|------------|
| Docling conversion (with OCR) | 1-2s per page | GPU (OCR inference) |
| HybridChunker | <100ms per document | CPU (tokenization) |
| Table extraction | <50ms per document | CPU (markdown export) |
| Image extraction | <200ms per image | CPU (PIL conversion) |
| Embedding (batch of 10) | 200-300ms | Network (API latency) |
| Vector DB bulk index (batch of 50) | 500-800ms | Network (HTTP) |
| **Full pipeline (10-page PDF)** | **15-30s** | **Docling conversion** |
| **Full pipeline (100-page PDF)** | **120-240s** | **Docling conversion** |

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `docling` | >=2.64.0 | Core document extraction |
| `docling-core` | >=2.9.0 | Data models (DoclingDocument, DocChunk) |
| `ray[default]` | >=2.9.0 | Distributed computing framework |
| `onnxruntime-gpu` | ==1.22.0 | GPU OCR inference (pin: 1.23.x GPU discovery bug) |
| `transformers` | >=4.36.0 | HuggingFace tokenizer for HybridChunker |
| `llama-index-readers-docling` | >=0.3.0 | LlamaIndex DoclingReader |
| `llama-index-node-parser-docling` | >=0.4.0 | Structure-aware DoclingNodeParser |

**Pin `onnxruntime-gpu`**: Version 1.23.x has a GPU discovery bug that causes silent fallback to CPU. Always use 1.22.0 until the upstream fix is released.
