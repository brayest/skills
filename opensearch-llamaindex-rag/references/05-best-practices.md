# Best Practices

> **Configuration for Your Project**
>
> Before implementing this section, ensure you've defined:
> - `{INDEXING_SERVICE}`: Your document processing service name (e.g., `document-ingestion`, `doc-processor`)
> - `{RETRIEVAL_SERVICE}`: Your extraction service name (e.g., `intelligent-extraction`, `field-extractor`)
> - `{INDEX_PREFIX}`: Your OpenSearch index prefix (e.g., `documents`, `contracts`, `records`)
> - `{TOPIC_*}`: Your messaging topic names (Kafka topics, SQS queues, etc.)
>
> Replace these placeholders throughout the code examples below.

## 1. Authentication & Security

### Direct IAM Role (No STS Assumption)

**❌ Old Pattern (101-second delay)**:
```python
# Don't do this
sts_client = boto3.client('sts')
assumed_role = sts_client.assume_role(
    RoleArn="arn:aws:iam::123456789012:role/OpensearchRole",
    RoleSessionName="opensearch-session"
)
credentials = assumed_role['Credentials']
```

**✅ New Pattern (Direct IAM)**:
```python
# Use container's IAM role directly
from opensearchpy import AWSV4SignerAuth

region = os.getenv('AWS_REGION')
if not region:
    raise EnvironmentError("AWS_REGION environment variable required")

# Credentials from container's IAM role (ECS task role, EKS service account, etc.)
service = 'es'  # OpenSearch service name
credentials = boto3.Session().get_credentials()

awsauth = AWSV4SignerAuth(credentials, region, service)

client = OpenSearch(
    hosts=[{'host': opensearch_host, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection
)
```

**Benefits**:
- Eliminates 101-second STS delay
- Simpler code (no session management)
- Better security (no credential exposure)
- Automatic credential rotation

### Environment Variable Validation

**✅ Fail-fast pattern**:
```python
def get_opensearch_client_from_env() -> OpenSearch:
    """Create OpenSearch client from environment variables."""
    opensearch_host = os.getenv('OPENSEARCH_HOST')
    if not opensearch_host:
        raise EnvironmentError("OPENSEARCH_HOST environment variable is required")

    opensearch_port = os.getenv('OPENSEARCH_PORT', '443')
    region = os.getenv('AWS_REGION')
    if not region:
        raise EnvironmentError("AWS_REGION environment variable is required")

    # Continue with client creation...
```

**❌ Anti-pattern (silent defaults)**:
```python
# Don't do this
opensearch_host = os.getenv('OPENSEARCH_HOST', 'localhost')  # Silent fallback
region = os.getenv('AWS_REGION') or 'us-east-1'  # Dangerous assumption
```

## 2. Indexing Best Practices

### Batch Size Tuning

**Production-tested values**:
```python
# Good defaults
BATCH_SIZE_SMALL_CHUNKS = 50   # Chunks < 1KB (typical text chunks)
BATCH_SIZE_LARGE_CHUNKS = 20   # Chunks > 5KB (tables, long paragraphs)
BATCH_SIZE_WITH_IMAGES = 10    # Chunks with base64-encoded images

# Adjust based on:
# - Network latency (higher latency → larger batches)
# - Chunk size (smaller chunks → larger batches)
# - OpenSearch cluster size (larger cluster → larger batches)
# - Error tolerance (smaller batches → easier error isolation)
```

### Error Handling in Bulk Operations

**✅ Proper error handling**:
```python
from opensearchpy import helpers as opensearch_helpers

success, failed = opensearch_helpers.bulk(
    client,
    actions,
    raise_on_error=False,  # Get partial results
    max_retries=3,
    initial_backoff=2
)

if failed:
    # Log failed documents with context
    logger.error(
        f"Failed to index {len(failed)} chunks",
        extra={
            "index": index_name,
            "failed_ids": [f['index']['_id'] for f in failed],
            "errors": [f['index'].get('error') for f in failed]
        }
    )
    # Re-raise for visibility (don't swallow errors)
    raise IndexingError(f"Bulk indexing failed for {len(failed)} chunks")

logger.info(f"Successfully indexed {success} chunks")
```

### Memory Management for Large Documents

**⚠️ Current issue**: Loading entire document in memory
```python
# Current pattern (can cause OOM for large docs)
chunks = chunking_pipeline.chunk_docling_document(doc)  # 10k chunks
embeddings = await embedding_service.get_embeddings_batch(chunks)  # All in memory
await indexer.bulk_index_chunks(chunks, embeddings)
```

**✅ Better pattern (streaming)**:
```python
# Stream-based indexing (constant memory)
async for chunk_batch in chunking_pipeline.chunk_docling_document_stream(doc, batch_size=50):
    # Embed batch
    embeddings = await embedding_service.get_embeddings_batch(chunk_batch)

    # Index batch immediately
    await indexer.bulk_index_chunks(chunk_batch, embeddings)

    # Memory freed after each batch
```

## 3. Retrieval Best Practices

### Score Threshold Calibration

**Methodology**:
1. **Collect ground truth**: Sample 100 documents with known fields
2. **Run retrieval**: Execute on all samples, collect scores
3. **Analyze distribution**: Plot score distributions for correct/incorrect matches
4. **Set thresholds**: Choose values that maximize F1 score

**Example analysis**:
```python
# Score distribution analysis
Correct matches:
  BM25:  Mean=8.5,  Median=7.2,  Min=2.1,  Max=45.3
  KNN:   Mean=0.72, Median=0.68, Min=0.42, Max=0.95

Incorrect matches:
  BM25:  Mean=2.1,  Median=1.5,  Min=0.1,  Max=8.9
  KNN:   Mean=0.35, Median=0.32, Min=0.05, Max=0.58

Recommended thresholds:
  BM25: 0.5 (normalized) → filters 85% of incorrect matches
  KNN:  0.3              → filters 78% of incorrect matches
```

**Field-specific tuning**:
```python
# High-precision fields (identifiers, dates, codes)
{
    "bm25_score_threshold": 0.7,  # Stricter
    "knn_score_threshold": 0.5
}

# Fuzzy fields (descriptions, narratives, summaries)
{
    "bm25_score_threshold": 0.3,  # More permissive
    "knn_score_threshold": 0.2
}
```

### Choosing Between Retrieval Strategies

**Use HybridRetriever when**:
- ✅ Simple field extraction (no special boost logic needed)
- ✅ Performance is critical (single OpenSearch call)
- ✅ Standard hybrid search is sufficient
- ✅ Easier maintenance is preferred

**Use RetrievalPipeline when**:
- ✅ Need intersection boost (identify consensus matches)
- ✅ Debugging visibility is important (inspect BM25/KNN separately)
- ✅ Custom boost logic per field
- ✅ Willing to accept higher latency (2 calls)

**Recommendation**: Standardize on **HybridRetriever** for most fields, use **RetrievalPipeline** only when intersection boost significantly improves extraction accuracy.

## 4. Post-Processing Best Practices

### Post-Processor Execution Order

**Order matters**! Incorrect ordering can produce wrong results.

**✅ Correct order**:
```python
# 1. Boost critical chunks (affects ranking)
nodes = page_boost_processor.postprocess_nodes(nodes)

# 2. Expand context (adds adjacent chunks to top-ranked nodes)
nodes = adjacent_expander.postprocess_nodes(nodes)

# 3. Add visual evidence (supplements text with images)
nodes = image_supplement_processor.postprocess_nodes(nodes)

# 4. Final selection (limits total context size)
nodes = final_selector.postprocess_nodes(nodes)
```

**❌ Wrong order (AdjacentExpander before PageBoost)**:
```python
# Problem: Adjacent expander adds context for low-scored chunks
# Then page boost re-ranks, but adjacent chunks are already selected
nodes = adjacent_expander.postprocess_nodes(nodes)  # Wrong!
nodes = page_boost_processor.postprocess_nodes(nodes)
```

### Post-Processor Configuration

**Field-level config example**:
```python
{
    "field_name": "{FIELD_NAME}",

    # PageBoost config
    "page_boost": [0],  # Boost cover page

    # AdjacentExpander config (implicit)
    "include_adjacent": true,  # Enable context expansion

    # ImageSupplement config
    "visual_analysis": {
        "enabled": true,
        "max_images": 4
    },
    "image_priority": true,

    # FinalSelector config
    "final_top_k": 10  # Max text chunks
}
```

## 5. Observability & Monitoring

### Structured Logging

**✅ Logging with context**:
```python
import structlog

logger = structlog.get_logger(__name__)

# Log with structured context
logger.info(
    "hybrid_retrieval_complete",
    doc_id=doc_id,
    field_name=field_name,
    bm25_results=len(bm25_chunks),
    knn_results=len(knn_chunks),
    intersection_size=len(intersection_ids),
    final_chunks=len(final_nodes),
    duration_ms=duration
)
```

**Benefits**:
- Easy filtering in log aggregators (CloudWatch, Datadog)
- Queryable by specific fields
- Performance tracking over time

### Distributed Tracing

#### OpenLLMetry (Primary Recommendation)

**Implementation**:
```python
from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import task, workflow

# Initialize
Traceloop.init(
    app_name="{RETRIEVAL_SERVICE}",
    disable_batch=True  # Real-time tracing
)

# Trace workflows
@workflow(name="field_extraction")
async def extract_field(doc_id: str, field_name: str):
    # Traced automatically
    nodes = await retrieve(doc_id, field_name)
    result = await extract_with_llm(nodes, field_name)
    return result

# Trace tasks
@task(name="hybrid_retrieval")
async def retrieve(doc_id: str, field_name: str):
    # Each retrieval traced with duration, inputs, outputs
    return retriever.retrieve(doc_id, field_name)
```

**Trace data collected**:
- Request duration
- Input/output sizes
- LLM token usage
- Error rates
- Dependency calls (OpenSearch, Bedrock)

#### Alternative Tools

**LangSmith** (LangChain ecosystem):
```python
from langchain.callbacks import LangChainTracer
from langsmith import Client

client = Client(api_key=os.getenv("LANGSMITH_API_KEY"))
tracer = LangChainTracer(project_name="{RETRIEVAL_SERVICE}")

# Use with LlamaIndex callbacks
Settings.callback_manager = CallbackManager([tracer])
```

**Arize Phoenix** (open-source):
```python
from phoenix.trace.langchain import LangChainInstrumentor

# Auto-instrument LlamaIndex/LangChain
LangChainInstrumentor().instrument()
```

**Custom Instrumentation** (OpenTelemetry):
```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
span_processor = BatchSpanProcessor(OTLPSpanExporter())
trace.get_tracer_provider().add_span_processor(span_processor)

# Manual tracing
with tracer.start_as_current_span("hybrid_retrieval"):
    result = retriever.retrieve(doc_id, field_name)
```

**Monitoring alternatives to DataDog**:
- **Prometheus + Grafana**: Open-source metrics and dashboards
- **New Relic**: Full APM suite with AI monitoring
- **AWS CloudWatch**: Native AWS integration
- **Elastic APM**: Part of ELK stack

### Key Metrics to Track

**Retrieval Metrics**:
```python
metrics = {
    # Retrieval performance
    "retrieval.duration_ms": 250,
    "retrieval.bm25_results": 45,
    "retrieval.knn_results": 38,
    "retrieval.intersection_size": 12,
    "retrieval.final_chunks": 10,

    # Score distributions
    "retrieval.bm25_max_score": 12.5,
    "retrieval.bm25_avg_score": 5.2,
    "retrieval.knn_max_score": 0.88,
    "retrieval.knn_avg_score": 0.62,

    # Post-processing
    "postprocess.page_boosted_chunks": 2,
    "postprocess.adjacent_chunks_added": 3,
    "postprocess.images_added": 4,

    # Extraction
    "extraction.llm_duration_ms": 1500,
    "extraction.input_tokens": 8500,
    "extraction.output_tokens": 120,
    "extraction.confidence_score": 0.92
}
```

## 6. Configuration Management

### AppConfig Integration

**Centralized field configuration**:
```python
# Retrieved from AWS AppConfig
field_config = {
    "field_name": "{FIELD_NAME}",

    # Query patterns (multiple search strategies)
    "queries": {
        "exact": "specific query for exact matches",
        "pattern": "natural language query pattern",
        "fuzzy": "fuzzy matching query"
    },

    # LLM instructions
    "instructions": {
        "task": "Extract the specific information needed",
        "keywords": ["keyword1", "keyword2", "keyword3"],
        "examples": [
            {"input": "Example input text", "output": "expected_output"},
            {"input": "Another example", "output": "another_output"}
        ]
    },

    # Search terms (additional keywords)
    "keywords_search": ["related", "terms", "to", "search"],

    # Retrieval config
    "retrieval": {
        "bm25_score_threshold": 0.5,
        "knn_score_threshold": 0.3,
        "intersection_boost": 2.0,
        "max_bm25_results": 100,
        "max_knn_results": 100,
        "final_top_k": 10
    },

    # Post-processing config
    "page_boost": [0],  # Boost first page
    "include_adjacent": true,
    "visual_analysis": {
        "enabled": true,
        "max_images": 4
    },
    "image_priority": true,

    # Validation rules
    "validation": {
        "type": "enum",  # or "string", "number", "date"
        "allowed_values": ["value1", "value2", "value3"],
        "required": true
    }
}
```

**Benefits**:
- Centralized configuration (no code changes)
- A/B testing (field-level config changes)
- Fast iteration (tune thresholds without deployment)
- Audit trail (AppConfig versions)

---

**Version**: 2.0
**Last Updated**: 2026-02-10
**Status**: Production-tested patterns
