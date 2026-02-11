# Configuration Reference

> **Configuration for Your Project**
>
> Before implementing this section, ensure you've defined:
> - `{INDEXING_SERVICE}`: Your document processing service name (e.g., `document-ingestion`, `doc-processor`)
> - `{RETRIEVAL_SERVICE}`: Your extraction service name (e.g., `intelligent-extraction`, `field-extractor`)
> - `{INDEX_PREFIX}`: Your OpenSearch index prefix (e.g., `documents`, `contracts`, `records`)
> - `{TOPIC_*}`: Your messaging topic names (Kafka topics, SQS queues, etc.)
>
> Replace these placeholders throughout the code examples below.

## Configuration Templates

### Embedding Configuration

```python
EMBEDDING_CONFIG = {
    "model_name": "amazon.titan-embed-text-v2:0",
    "region": "us-east-1",
    "dimension": 1024,
    "normalize": True,  # Cosine similarity requires normalized vectors
    "batch_size": 25,   # Bedrock batch embedding limit
    "max_text_length": 45000,  # Safe limit (actual: 50k)
    "chunk_overlap": 4500      # 10% overlap for large texts
}
```

### OpenSearch Index Configuration

```python
INDEX_CONFIG = {
    "settings": {
        "index": {
            "knn": True,
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "refresh_interval": "1s"
        }
    },
    "knn_vector": {
        "dimension": 1024,
        "method": {
            "name": "hnsw",
            "space_type": "cosinesimil",
            "engine": "lucene",
            "parameters": {
                "ef_construction": 512,  # Build quality (higher = better recall)
                "m": 16                  # Graph connectivity (16 is production-tested)
            }
        }
    }
}
```

### Retrieval Configuration

```python
RETRIEVAL_CONFIG = {
    # Hybrid search
    "max_results": 100,
    "min_score": 0.4,  # Normalized hybrid score threshold

    # BM25 specific
    "bm25_score_threshold": 0.5,
    "bm25_fuzziness": "AUTO",
    "bm25_operator": "or",

    # KNN specific
    "knn_score_threshold": 0.3,
    "knn_k": 100,

    # Custom combination (RetrievalPipeline only)
    "intersection_boost": 2.0,
    "bm25_normalization_divisor": 10.0,  # ⚠️ Heuristic (should be improved)

    # Post-processing
    "final_top_k": 10,
    "page_boost_amount": 100.0,
    "adjacent_chunks_before": 1,
    "adjacent_chunks_after": 1,
    "max_images": 4
}
```

### LLM Extraction Configuration

```python
EXTRACTION_CONFIG = {
    "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "temperature": 0.0,  # Deterministic extraction
    "max_tokens": 2048,
    "top_p": 1.0,

    # Retry configuration
    "max_retries": 3,
    "retry_backoff": 2.0,

    # Validation
    "require_confidence": True,
    "min_confidence": 0.7,

    # Prompt configuration
    "system_prompt_template": "You are an expert at extracting {field_name} from documents...",
    "few_shot_examples": 3  # Include N examples from field config
}
```

## Environment Variables

### Required Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `OPENSEARCH_HOST` | OpenSearch cluster endpoint | `search-cluster.us-east-1.es.amazonaws.com` | Yes |
| `OPENSEARCH_PORT` | OpenSearch port | `443` | Yes |
| `AWS_REGION` | AWS region for OpenSearch and Bedrock | `us-east-1` | Yes |
| `INDEX_PREFIX` | Prefix for OpenSearch indexes | `documents` | Yes |

### Optional Environment Variables

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `OPENSEARCH_TIMEOUT` | Query timeout in seconds | `30` | Increase for large indexes |
| `BATCH_SIZE_SMALL` | Batch size for small chunks | `50` | Tune based on network latency |
| `BATCH_SIZE_LARGE` | Batch size for large chunks | `20` | Chunks > 5KB |
| `BATCH_SIZE_IMAGES` | Batch size with images | `10` | Base64-encoded images |
| `MAX_RETRIES` | OpenSearch retry attempts | `3` | For transient failures |
| `LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG` for troubleshooting |

### Example .env File

```bash
# OpenSearch configuration
OPENSEARCH_HOST=search-cluster.us-east-1.es.amazonaws.com
OPENSEARCH_PORT=443
AWS_REGION=us-east-1
INDEX_PREFIX=documents

# Embedding configuration
EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
EMBEDDING_DIMENSION=1024

# Retrieval configuration
BM25_THRESHOLD=0.5
KNN_THRESHOLD=0.3
INTERSECTION_BOOST=2.0
FINAL_TOP_K=10

# LLM configuration
LLM_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
LLM_TEMPERATURE=0.0
LLM_MAX_TOKENS=2048

# Performance tuning
BATCH_SIZE_SMALL=50
BATCH_SIZE_LARGE=20
BATCH_SIZE_IMAGES=10
OPENSEARCH_TIMEOUT=30

# Observability
LOG_LEVEL=INFO
TRACING_ENABLED=true
```

## Performance Tuning

### Latency Breakdown

**Typical field extraction timeline**:
```
Total: ~3500ms
├─ Message processing: 50ms
├─ Config retrieval: 100ms (cached after first call)
├─ OpenSearch retrieval: 250ms
│  ├─ BM25 query: 120ms
│  └─ KNN query: 130ms (if using RetrievalPipeline)
├─ Post-processing: 80ms
│  ├─ Page boost: 5ms
│  ├─ Adjacent expansion: 50ms (additional OpenSearch calls)
│  ├─ Image supplement: 10ms
│  └─ Final selection: 15ms
├─ LLM extraction: 2800ms
│  ├─ Prompt assembly: 50ms
│  ├─ Bedrock API call: 2500ms (model inference)
│  └─ Response parsing: 250ms
└─ Result publishing: 50ms
```

**Optimization priorities**:
1. **LLM latency (80% of time)**: Use Claude Haiku for simple fields
2. **Retrieval (7% of time)**: Use HybridRetriever (single call) instead of RetrievalPipeline
3. **Adjacent expansion (1-2% of time)**: Disable for fields that don't need context

### Cost Calculator

#### Embedding Costs

```python
def calculate_embedding_cost(num_chunks: int, tokens_per_chunk: int = 512) -> float:
    """
    Calculate embedding cost for Bedrock Titan V2.

    Args:
        num_chunks: Number of chunks to embed
        tokens_per_chunk: Average tokens per chunk

    Returns:
        Cost in USD
    """
    TITAN_V2_PRICE_PER_1K_TOKENS = 0.0001

    total_tokens = num_chunks * tokens_per_chunk
    cost = (total_tokens / 1000) * TITAN_V2_PRICE_PER_1K_TOKENS

    return round(cost, 4)

# Example: 100-page document
# Chunks: ~250 chunks × 512 tokens = 128k tokens
# Cost: 128 × $0.0001 = $0.0128 per document
```

#### LLM Extraction Costs

```python
def calculate_extraction_cost(
    num_fields: int,
    avg_input_tokens: int = 8500,
    avg_output_tokens: int = 120,
    model: str = "sonnet"
) -> dict:
    """
    Calculate LLM extraction cost per document.

    Args:
        num_fields: Number of fields to extract
        avg_input_tokens: Average input tokens per field (10 chunks + images + prompt)
        avg_output_tokens: Average output tokens (JSON response)
        model: "sonnet", "haiku", or "opus"

    Returns:
        Dict with cost breakdown
    """
    PRICING = {
        "sonnet": {"input": 3.00, "output": 15.00},
        "haiku": {"input": 0.25, "output": 1.25},
        "opus": {"input": 15.00, "output": 75.00}
    }

    prices = PRICING[model]

    # Cost per field
    input_cost_per_field = (avg_input_tokens / 1_000_000) * prices["input"]
    output_cost_per_field = (avg_output_tokens / 1_000_000) * prices["output"]
    cost_per_field = input_cost_per_field + output_cost_per_field

    # Total cost
    total_cost = cost_per_field * num_fields

    return {
        "cost_per_field": round(cost_per_field, 4),
        "total_cost": round(total_cost, 4),
        "model": model,
        "num_fields": num_fields
    }

# Example: 20 fields with Sonnet
# Cost per field: (8.5k × $3 + 0.12k × $15) / 1M = $0.0273
# Total: 20 × $0.0273 = $0.546 per document

# Cost reduction with Haiku (simple fields like dates, IDs):
# Cost per field: (8.5k × $0.25 + 0.12k × $1.25) / 1M = $0.0023
# Savings: ~90% reduction for simple fields
```

#### Total Document Processing Cost

```python
def calculate_total_document_cost(
    num_chunks: int = 250,
    num_fields: int = 20,
    simple_fields: int = 5,  # Use Haiku
    complex_fields: int = 15  # Use Sonnet
) -> dict:
    """
    Calculate total cost to process one document.

    Returns:
        Dict with cost breakdown
    """
    # Embedding cost (one-time)
    embedding_cost = calculate_embedding_cost(num_chunks)

    # Extraction costs
    haiku_cost = calculate_extraction_cost(simple_fields, model="haiku")["total_cost"]
    sonnet_cost = calculate_extraction_cost(complex_fields, model="sonnet")["total_cost"]
    extraction_cost = haiku_cost + sonnet_cost

    total_cost = embedding_cost + extraction_cost

    return {
        "embedding_cost": embedding_cost,
        "haiku_extraction_cost": haiku_cost,
        "sonnet_extraction_cost": sonnet_cost,
        "total_extraction_cost": extraction_cost,
        "total_cost": round(total_cost, 4),
        "cost_per_field": round(extraction_cost / num_fields, 4)
    }

# Example output:
# {
#     "embedding_cost": 0.0128,
#     "haiku_extraction_cost": 0.0115,
#     "sonnet_extraction_cost": 0.4095,
#     "total_extraction_cost": 0.421,
#     "total_cost": 0.4338,
#     "cost_per_field": 0.021
# }
```

### Scaling Decision Matrix

| Metric | Threshold | Action | Notes |
|--------|-----------|--------|-------|
| **OpenSearch Disk Usage** | > 80% | Add cluster nodes | Distribute indexes across more nodes |
| **Documents per Node** | > 500 | Scale horizontally | Add more r6g.xlarge nodes |
| **Query Latency** | > 500ms | Optimize queries or upgrade nodes | Consider r6g.2xlarge for more CPU |
| **Concurrent Extractions** | > 100 | Add {RETRIEVAL_SERVICE} instances | Scale ECS tasks / K8s pods |
| **Message Queue Lag** | > 1000 msgs | Scale both services | Add producers and consumers |
| **Memory Usage** | > 85% | Implement streaming or add RAM | Prevent OOM crashes |
| **Cost per Document** | > $1.00 | Use Haiku for simple fields | 40-90% cost reduction |

## Troubleshooting

### Common Issues

#### Issue 1: Low Retrieval Recall

**Symptoms**: Relevant chunks not being retrieved

**Diagnosis**:
```python
# Check score distributions
logger.info(
    "retrieval_analysis",
    bm25_scores=[node.score for node in bm25_nodes],
    knn_scores=[node.score for node in knn_nodes]
)

# Inspect filtered chunks
logger.info(
    f"Filtered {len(all_nodes) - len(filtered_nodes)} nodes below threshold",
    threshold=min_score
)
```

**Solutions**:
1. **Lower thresholds**: Reduce `bm25_score_threshold` or `knn_score_threshold`
2. **Adjust query**: Add more keywords to `keywords_search`
3. **Fix embeddings**: Ensure query embedding matches chunk embedding model
4. **Check filters**: Verify `docId` filter is correct

#### Issue 2: High Latency

**Symptoms**: Retrieval taking > 500ms

**Diagnosis**:
```python
import time

start = time.time()
bm25_results = opensearch_client.search(...)
bm25_duration = time.time() - start

start = time.time()
knn_results = opensearch_client.search(...)
knn_duration = time.time() - start

logger.info(f"BM25: {bm25_duration}ms, KNN: {knn_duration}ms")
```

**Solutions**:
1. **Use HybridRetriever**: Single call instead of two phases
2. **Reduce k**: Lower `max_knn_results` from 100 to 50
3. **Disable adjacent expansion**: Adds extra OpenSearch calls
4. **Check cluster health**: OpenSearch cluster may be under-resourced

#### Issue 3: Poor Extraction Accuracy

**Symptoms**: LLM extracting wrong values despite correct chunks

**Diagnosis**:
```python
# Log final context sent to LLM
logger.debug(
    "llm_context",
    chunks=[node.text[:100] for node in final_nodes],  # First 100 chars
    chunk_scores=[node.score for node in final_nodes],
    image_count=len([n for n in final_nodes if n.metadata['chunk_type'] == 'image'])
)
```

**Solutions**:
1. **Check context relevance**: Are top chunks actually relevant?
2. **Add page boost**: If field is on known page (e.g., cover page)
3. **Increase top-k**: Raise `final_top_k` from 10 to 15
4. **Improve prompt**: Add more few-shot examples to field config
5. **Use better model**: Switch from Haiku to Sonnet for complex fields

#### Issue 4: Memory Issues (OOM)

**Symptoms**: Service crashes during indexing of large documents

**Diagnosis**:
```python
import tracemalloc

tracemalloc.start()

# ... indexing code ...

current, peak = tracemalloc.get_traced_memory()
logger.info(f"Memory usage: current={current/1024/1024}MB, peak={peak/1024/1024}MB")
tracemalloc.stop()
```

**Solutions**:
1. **Implement streaming**: Index in batches instead of all at once
2. **Reduce batch size**: Lower from 50 to 20
3. **Increase container memory**: Allocate more RAM to ECS task/K8s pod
4. **Process fewer concurrent documents**: Limit concurrency

## Future Improvements

### 1. Score Normalization

**Current issue**: Manual BM25 normalization using magic constant (`/10.0`)

**Improvement**:
```python
# Option A: Use OpenSearch min_max processor (preferred)
# Already available in hybrid-search-pipeline

# Option B: Percentile-based normalization
from scipy import stats

def normalize_bm25_scores(scores: List[float]) -> List[float]:
    """Normalize BM25 scores using percentile ranks."""
    return [stats.percentileofscore(scores, s) / 100.0 for s in scores]
```

### 2. Adaptive Thresholding

**Current**: Static thresholds per field

**Improvement**: Dynamic thresholds based on score distribution
```python
def adaptive_threshold(scores: List[float], target_recall: float = 0.9) -> float:
    """Calculate threshold to achieve target recall."""
    sorted_scores = sorted(scores, reverse=True)
    cutoff_idx = int(len(sorted_scores) * target_recall)
    return sorted_scores[cutoff_idx]
```

### 3. Retrieval Consolidation

**Current**: Two parallel implementations (HybridRetriever + RetrievalPipeline)

**Recommendation**: Standardize on HybridRetriever, add intersection boost as optional post-processor
```python
class IntersectionBoostPostprocessor(BaseNodePostprocessor):
    """Apply boost to chunks found in both BM25 and KNN (requires dual-retrieval run)."""
    # Implementation that works with single hybrid call
    # Track which chunks appear in both result sets via metadata
```

### 4. Streaming Indexing

**Current**: Load entire document in memory before indexing

**Improvement**:
```python
async def stream_index_document(doc_path: str, index_name: str):
    """Stream-based indexing for large documents."""
    async for chunk_batch in chunking_pipeline.chunk_stream(doc_path, batch_size=50):
        embeddings = await embedding_service.get_embeddings_batch(chunk_batch)
        await indexer.bulk_index_chunks(index_name, chunk_batch, embeddings)
        # Memory freed after each batch
```

### 5. Query Expansion

**Current**: Static queries from field config

**Improvement**: LLM-based query expansion
```python
async def expand_query(field_name: str, base_query: str) -> List[str]:
    """Use LLM to generate query variations."""
    prompt = f"Generate 5 search query variations for extracting {field_name}: {base_query}"
    variations = await llm.generate(prompt)
    return [base_query] + variations
```

### 6. Hybrid Index Strategy

**Current**: Per-document indexes ({INDEX_PREFIX}_{org}_{doc_id})

**Consideration**: Hybrid approach (global + per-document)
```python
# Global index for cross-document search
global_index = "{INDEX_PREFIX}_global"

# Per-document for isolated retrieval
doc_index = f"{INDEX_PREFIX}_{org}_{doc_id}"

# Use case: "Find all documents matching criteria" → global index
# Use case: "Extract field from specific document" → per-document index
```

## Summary

This RAG architecture implements production-grade hybrid search combining:

**Strengths**:
- ✅ Sophisticated dual-path retrieval (BM25 + KNN)
- ✅ Rich metadata preservation (Docling integration)
- ✅ Custom post-processors for domain-specific logic
- ✅ Fail-fast error handling (no silent defaults)
- ✅ Comprehensive observability (structured logging + distributed tracing)
- ✅ Field-level configuration (centralized config management)

**Key Metrics**:
- Latency: ~3.5s per field extraction
- Cost: $0.02-0.55 per document (model-dependent)
- Accuracy: Tunable via thresholds and post-processing
- Scalability: Horizontal scaling for both indexing and retrieval

---

**Version**: 2.0
**Last Updated**: 2026-02-10
**Status**: Production-tested configuration templates
