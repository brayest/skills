---
name: docling-ray
description: This skill should be used when building document extraction pipelines that combine Docling for intelligent document parsing (PDF, DOCX, PPTX) with Ray for GPU-accelerated parallel processing. Provides architecture patterns, Ray actor design for Docling workers, fractional GPU allocation, HybridChunker configuration, async FastAPI integration, container deployment, and resource optimization strategies.
---

# Docling + Ray: Document Extraction with GPU-Accelerated Parallel Processing

Production-grade patterns for building document extraction pipelines that combine Docling for intelligent parsing with Ray for parallel GPU processing.

## When to Use

Apply this skill when:

- Building a document extraction service that processes PDF, DOCX, or PPTX files using Docling
- Parallelizing Docling document conversion across multiple workers with Ray
- Optimizing GPU utilization for OCR-heavy document processing
- Integrating Docling + Ray with an async web framework (FastAPI, Starlette)
- Configuring HybridChunker for RAG-optimized document chunking
- Deploying Docling + Ray in containers (Docker, Kubernetes)

## Architecture Overview

```
                    ┌──────────────────────────────────────────────────┐
   Input            │          Document Extraction Service (FastAPI)   │
   (S3, Upload,     │                                                  │
    Message Queue)  │  ┌──────────────┐    ┌──────────────┐           │
                    │  │ Ray Worker 1 │    │ Ray Worker 2 │  ...N     │
                    │  │  Docling     │    │  Docling     │           │
                    │  │  Chunker     │    │  Chunker     │           │
                    │  └──────┬───────┘    └──────┬───────┘           │
                    │         │  Fractional GPU    │                   │
                    │         └────────┬───────────┘                   │
                    │                  ▼                                │
                    │      ┌───────────────────────┐                   │
                    │      │   Main Async Process   │                   │
                    │      │  - Embedding generation │                  │
                    │      │  - Image VLM analysis   │                  │
                    │      │  - Vector DB indexing    │                  │
                    │      └───────────┬───────────┘                   │
                    └──────────────────┼───────────────────────────────┘
                                       ▼
                              Vector Database / Downstream Services
```

**Core principle**: Docling conversion (CPU+GPU heavy) runs in Ray actor processes. I/O-bound work (embedding API calls, vector DB indexing, image analysis) stays in the main async process.

## Key Principles

1. **Single conversion, multiple outputs** — Convert a document once with Docling, then extract text, tables, and images from the same `DoclingDocument`. Never re-convert for different content types.

2. **Deferred imports in Ray actors** — Import Docling and chunking modules inside actor `__init__`, not at module level. Each actor process loads its own model instances. Avoids wasting memory in the main process.

3. **Serialize to plain dicts** — Return plain Python dicts from Ray actors, not framework objects (LlamaIndex TextNode, PIL Image). Framework objects may fail pickle serialization through Ray's object store.

4. **Non-blocking async integration** — Never call `ray.get()` directly in async code. Use `asyncio.to_thread(ray.wait, [future], timeout=0.1)` polling pattern to keep the event loop responsive.

5. **Fractional GPU allocation** — Multiple Ray workers share a single GPU via fractional allocation (e.g., 4 workers x 0.25 GPU). Docling's GPU usage is bursty (OCR inference kernels between CPU preprocessing), making time-sharing efficient.

6. **Structure-aware chunking** — Use Docling's HybridChunker with a real tokenizer for token-accurate, structure-respecting chunk boundaries. Always chunk directly from the DoclingDocument (not re-reading the file).

## Reference Guide

| Topic | File | When to Consult |
|-------|------|-----------------|
| Docling setup & content extraction | `references/docling-configuration.md` | Configuring DocumentConverter, OCR options, extracting tables/images |
| Ray actors, GPU sharing, async | `references/ray-parallel-processing.md` | Designing worker actors, integrating with FastAPI, choosing GPU fractions |
| Chunking for RAG | `references/chunking-strategies.md` | Setting up HybridChunker, choosing token limits, metadata preservation |
| Deployment & tuning | `references/deployment-tuning.md` | Dockerfile setup, resource sizing, scaling, error handling, health checks |

## Quick Optimization Checklist

- `force_full_page_ocr=True` when documents contain vector-rendered tables
- `images_scale=2.0` for OCR accuracy (reduce to 1.5 if GPU memory constrained)
- Pre-download HuggingFace tokenizer in Dockerfile (avoid runtime download race)
- Pin `onnxruntime-gpu==1.22.0` (1.23.x has GPU discovery bug causing silent CPU fallback)
- Set container `shm_size >= 8gb` for Ray object store
- `log_to_driver=False` and `configure_logging=False` in `ray.init()` to preserve structured logging
- Health check start-period of 120s for Ray + model initialization
- Limit concurrent in-flight tasks to match Ray worker count
- Chunk directly from DoclingDocument (Pathway 2) to avoid double conversion
- Serialize Ray actor returns as plain dicts, not framework objects
- Use `asyncio.to_thread(ray.wait, ...)` for non-blocking async FastAPI integration
