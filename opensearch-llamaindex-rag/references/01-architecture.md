# System Architecture

> **Configuration for Your Project**
>
> Before implementing this section, ensure you've defined:
> - `{INDEXING_SERVICE}`: Your document processing service name (e.g., `document-ingestion`, `doc-processor`)
> - `{RETRIEVAL_SERVICE}`: Your extraction service name (e.g., `intelligent-extraction`, `field-extractor`)
> - `{ORCHESTRATION_SERVICE}`: Your API/orchestrator name (e.g., `main-api`, `gateway`)
> - `{INDEX_PREFIX}`: Your OpenSearch index prefix (e.g., `documents`, `contracts`, `records`)
> - `{TOPIC_EXTRACTION_REQUESTED}`: Kafka/SQS topic triggering indexing
> - `{TOPIC_EMBEDDINGS_COMPLETE}`: Topic signaling indexing completion
> - `{TOPIC_EXTRACTION_COMPLETE}`: Topic signaling extraction completion
>
> Replace these placeholders throughout the code examples below.

## Executive Summary

### Overview

This architecture implements a **dual-service RAG system** for extracting structured data from unstructured documents (PDFs, DOCX, PPTX). The system combines:

- **Docling**: Document structure preservation and layout analysis
- **LlamaIndex**: Chunking, embedding, and retrieval orchestration
- **OpenSearch**: Vector + lexical hybrid search with HNSW indexing
- **AWS Bedrock**: Titan V2 embeddings (1024-dim) and Claude for extraction

> **Apply to Your Domain**
>
> The architecture patterns apply to multiple domains:
> - **Legal contracts**: Extract party names, contract dates, clause types, obligations
> - **Medical records**: Extract diagnoses, medications, patient demographics, treatment plans
> - **Financial documents**: Extract account numbers, transaction details, compliance data
> - **Research papers**: Extract methodologies, findings, citations, conclusions
>
> Only the extracted fields change - the technical architecture remains the same.

### Key Metrics

| Metric | Value | Description |
|--------|-------|-------------|
| **Embedding Dimension** | 1024 | Bedrock Titan V2 output |
| **Chunk Size** | 512 tokens | ~2000 characters |
| **Max Retrieval** | 100 chunks | Before post-processing |
| **Final Context** | 10 text + 4 image chunks | Sent to LLM |
| **BM25 Threshold** | 0.5 | Minimum lexical relevance |
| **KNN Threshold** | 0.3 | Minimum semantic similarity |
| **Intersection Boost** | 2.0x | Score multiplier for dual-phase matches |
| **Indexing Batch Size** | 50 documents | Bulk indexing chunk size |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                  {ORCHESTRATION_SERVICE}                        │
│                    (Orchestration Layer)                        │
└────────────┬────────────────────────────────────────────────────┘
             │ Event: {TOPIC_EXTRACTION_REQUESTED}
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                  {INDEXING_SERVICE}                             │
│                  (Indexing Service)                             │
├─────────────────────────────────────────────────────────────────┤
│  1. Docling Extraction    → Document structure + layout        │
│  2. Hierarchical Chunking → 512-token semantic chunks          │
│  3. Bedrock Titan V2      → 1024-dim embeddings                │
│  4. OpenSearch Indexing   → Bulk index (batch: 50)             │
└────────────┬────────────────────────────────────────────────────┘
             │ Event: {TOPIC_EMBEDDINGS_COMPLETE}
             ↓
             │ OpenSearch Index: {INDEX_PREFIX}_{org}_{doc_id}
             │ - text (BM25)
             │ - chunk_vector (KNN 1024-dim HNSW)
             │ - metadata (15+ fields)
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                  {RETRIEVAL_SERVICE}                            │
│                 (Retrieval + Extraction)                        │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Hybrid Retrieval                                      │
│    - BM25 (multi_match, fuzzy)                                  │
│    - KNN (cosine similarity)                                    │
│    - Score combination (50/50 weighted)                         │
│                                                                 │
│  Phase 2: Post-Processing                                       │
│    - Page boost (+100 for critical pages)                       │
│    - Adjacent chunk expansion (context)                         │
│    - Image supplementation (visual evidence)                    │
│    - Final top-k selection                                      │
│                                                                 │
│  Phase 3: LLM Extraction                                        │
│    - Bedrock Claude (Sonnet/Haiku)                              │
│    - Structured output (JSON schema)                            │
│    - Validation + confidence scoring                            │
└────────────┬────────────────────────────────────────────────────┘
             │ Event: {TOPIC_EXTRACTION_COMPLETE}
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    DOWNSTREAM SYSTEMS                           │
│              (API Response / Database / Storage)                │
└─────────────────────────────────────────────────────────────────┘
```

## Service Responsibilities

### 1. {INDEXING_SERVICE} (Producer)

**Role**: Document ingestion, chunking, embedding, and indexing

**Key Components**:

- **DoclingProcessor**
  - Extracts document structure (tables, images, headers)
  - Preserves layout and hierarchy
  - Handles PDF, DOCX, PPTX formats
  - Location: `/{INDEXING_SERVICE}/app/docling_processor.py`

- **ChunkingPipeline**
  - 512-token semantic chunking via HybridChunker
  - Maintains document hierarchy metadata
  - Creates LlamaIndex TextNode objects
  - Location: `/{INDEXING_SERVICE}/app/chunking_pipeline.py`

- **EmbeddingService**
  - Bedrock Titan V2 integration
  - Handles large chunks (splits at 45k chars, averages embeddings)
  - Batch processing for efficiency
  - Location: `/{INDEXING_SERVICE}/app/embedding_service.py`

- **OpenSearchIndexer**
  - Creates per-document indexes
  - Bulk indexing (batch size: 50)
  - HNSW vector configuration
  - Location: `/{INDEXING_SERVICE}/app/opensearch_indexer.py`

**Data Flow**:
```python
PDF/DOCX → Docling → Chunks → Embeddings → OpenSearch Index
                                              ↓
                            Event: {TOPIC_EMBEDDINGS_COMPLETE}
```

**Trigger**: Listens to `{TOPIC_EXTRACTION_REQUESTED}` event

**Output**: Publishes `{TOPIC_EMBEDDINGS_COMPLETE}` event when indexing completes

### 2. {RETRIEVAL_SERVICE} (Consumer)

**Role**: Retrieval, context assembly, and field extraction

**Key Components**:

- **OpenSearchClient**
  - LlamaIndex OpensearchVectorStore integration
  - Hybrid search pipeline configuration
  - Direct IAM authentication (no STS)
  - Location: `/{RETRIEVAL_SERVICE}/infrastructure/storage/opensearch_client.py`

- **HybridRetriever**
  - Single-call native hybrid search
  - VectorStoreQueryMode.HYBRID
  - Score threshold filtering
  - Location: `/{RETRIEVAL_SERVICE}/domain/extraction/retrieval.py`

- **RetrievalPipeline**
  - Three-phase retrieval (BM25 + KNN + combination)
  - Custom intersection boost (2.0x)
  - Manual score normalization
  - Location: `/{RETRIEVAL_SERVICE}/domain/extraction/retrieval_pipeline.py`

- **Post-Processors**
  - PageBoostPostprocessor
  - AdjacentChunkExpander
  - ImageSupplementPostprocessor
  - FinalTopKSelector
  - Location: `/{RETRIEVAL_SERVICE}/domain/processing/postprocessors.py`

**Data Flow**:
```python
Event: {TOPIC_EMBEDDINGS_COMPLETE} → Retrieval → Post-Processing → LLM → Extraction
                                                                            ↓
                                              Event: {TOPIC_EXTRACTION_COMPLETE}
```

**Trigger**: Listens to `{TOPIC_EMBEDDINGS_COMPLETE}` event

**Output**: Publishes `{TOPIC_EXTRACTION_COMPLETE}` event with extracted fields

### 3. {ORCHESTRATION_SERVICE} (Coordinator)

**Role**: API gateway, workflow orchestration, client-facing interface

**Responsibilities**:
- Receives document upload requests from clients
- Triggers indexing pipeline via `{TOPIC_EXTRACTION_REQUESTED}`
- Tracks extraction progress across services
- Aggregates results from `{TOPIC_EXTRACTION_COMPLETE}`
- Returns structured extraction results to clients
- Handles authentication, authorization, rate limiting

**Example API Flow**:
```python
POST /api/v1/documents/extract
  ↓
Validate request → Store document in S3
  ↓
Publish {TOPIC_EXTRACTION_REQUESTED}
  ↓
Return 202 Accepted (job_id)
  ↓
... async processing ...
  ↓
Listen to {TOPIC_EXTRACTION_COMPLETE}
  ↓
Update job status → Notify client (webhook/polling)
```

## Data Flow

### Event-Driven Architecture

The system uses an **event-driven producer-consumer pattern** for decoupling services:

```
┌──────────────────┐
│   Client/User    │
└────────┬─────────┘
         │ HTTP POST
         ↓
┌──────────────────────────────────────────────┐
│ {ORCHESTRATION_SERVICE}                      │
├──────────────────────────────────────────────┤
│ 1. Upload document to S3                     │
│ 2. Create extraction job                     │
│ 3. Publish {TOPIC_EXTRACTION_REQUESTED}      │
└────────┬─────────────────────────────────────┘
         │ Event Bus (Kafka / SQS / EventBridge)
         ↓
┌──────────────────────────────────────────────┐
│ {INDEXING_SERVICE}                           │
├──────────────────────────────────────────────┤
│ 1. Download document from S3                 │
│ 2. Docling extraction                        │
│ 3. Chunk into 512-token segments             │
│ 4. Generate Titan V2 embeddings              │
│ 5. Bulk index to OpenSearch                  │
│ 6. Publish {TOPIC_EMBEDDINGS_COMPLETE}       │
└────────┬─────────────────────────────────────┘
         │ Event Bus
         ↓
┌──────────────────────────────────────────────┐
│ {RETRIEVAL_SERVICE}                          │
├──────────────────────────────────────────────┤
│ For each field to extract:                   │
│   1. Hybrid retrieval (BM25 + KNN)           │
│   2. Post-processing (boost, expand, images) │
│   3. LLM extraction (Claude)                 │
│   4. Validation + confidence scoring         │
│ 5. Publish {TOPIC_EXTRACTION_COMPLETE}       │
└────────┬─────────────────────────────────────┘
         │ Event Bus
         ↓
┌──────────────────────────────────────────────┐
│ {ORCHESTRATION_SERVICE}                      │
├──────────────────────────────────────────────┤
│ 1. Aggregate extracted fields                │
│ 2. Update job status                         │
│ 3. Notify client (webhook/API)               │
└──────────────────────────────────────────────┘
```

### Per-Document Index Strategy

**Pattern**: One OpenSearch index per document

**Index Naming**: `{INDEX_PREFIX}_{organization}_{doc_id}`

**Example**:
```python
# Document ID: doc_12345
# Organization: acme_corp
# Index name: documents_acme_corp_doc_12345

index_name = f"{INDEX_PREFIX}_{organization}_{doc_id}"
```

**Benefits**:
- **Multi-tenancy**: Isolate documents by organization/client
- **Security**: IAM policies per index, easier access control
- **Parallel processing**: Index multiple documents concurrently
- **Cleanup**: Delete individual indexes without affecting others
- **Debugging**: Inspect specific document's chunks in isolation

**Trade-offs**:
- More indexes to manage (but OpenSearch handles this well)
- Slight overhead per index (~1-2MB metadata)
- Not suitable for cross-document search (use global index for that)

> **Apply to Your Domain**
>
> Per-document indexing works well for:
> - **Contract management**: One index per contract (isolate by client)
> - **Medical records**: One index per patient (HIPAA compliance, isolation)
> - **Financial audits**: One index per company/year (compliance, retention)
>
> Use a global index when you need cross-document search:
> - "Find all contracts expiring in Q1 2026"
> - "Which patients have diagnosis code X?"
> - "List companies with revenue > $1M"

## Deployment Patterns

### Container Orchestration

#### AWS ECS (Fargate)

**Recommended for**:
- AWS-native deployments
- Auto-scaling based on SQS/Kafka queue depth
- Simplified operations (no cluster management)

**Example Task Definition** ({INDEXING_SERVICE}):
```json
{
  "family": "{INDEXING_SERVICE}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/{INDEXING_SERVICE}-task-role",
  "containerDefinitions": [{
    "name": "{INDEXING_SERVICE}",
    "image": "ACCOUNT.dkr.ecr.REGION.amazonaws.com/{INDEXING_SERVICE}:latest",
    "environment": [
      {"name": "OPENSEARCH_HOST", "value": "search-cluster.us-east-1.es.amazonaws.com"},
      {"name": "AWS_REGION", "value": "us-east-1"},
      {"name": "INDEX_PREFIX", "value": "documents"}
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/{INDEXING_SERVICE}",
        "awslogs-region": "us-east-1"
      }
    }
  }]
}
```

#### AWS EKS (Kubernetes)

**Recommended for**:
- Multi-cloud or hybrid deployments
- Advanced orchestration needs (GPU scheduling, complex scaling)
- Existing Kubernetes expertise

**Example Deployment** ({RETRIEVAL_SERVICE}):
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {RETRIEVAL_SERVICE}
spec:
  replicas: 3
  selector:
    matchLabels:
      app: {RETRIEVAL_SERVICE}
  template:
    metadata:
      labels:
        app: {RETRIEVAL_SERVICE}
    spec:
      serviceAccountName: {RETRIEVAL_SERVICE}-sa  # For IAM roles
      containers:
      - name: {RETRIEVAL_SERVICE}
        image: ACCOUNT.dkr.ecr.REGION.amazonaws.com/{RETRIEVAL_SERVICE}:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
        env:
        - name: OPENSEARCH_HOST
          value: "search-cluster.us-east-1.es.amazonaws.com"
        - name: AWS_REGION
          value: "us-east-1"
        - name: INDEX_PREFIX
          value: "documents"
```

#### Docker Compose (Local Development)

**Example** (all services):
```yaml
version: '3.8'

services:
  {INDEXING_SERVICE}:
    build: ./{INDEXING_SERVICE}
    environment:
      - OPENSEARCH_HOST=opensearch
      - AWS_REGION=us-east-1
      - INDEX_PREFIX=documents
    volumes:
      - ~/.aws:/root/.aws:ro  # AWS credentials for local testing
    depends_on:
      - opensearch
      - kafka

  {RETRIEVAL_SERVICE}:
    build: ./{RETRIEVAL_SERVICE}
    environment:
      - OPENSEARCH_HOST=opensearch
      - AWS_REGION=us-east-1
      - INDEX_PREFIX=documents
    volumes:
      - ~/.aws:/root/.aws:ro
    depends_on:
      - opensearch
      - kafka

  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      - KAFKA_BROKER_ID=1
      - KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181
      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092
    depends_on:
      - zookeeper

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      - ZOOKEEPER_CLIENT_PORT=2181
```

### Scaling Considerations

**{INDEXING_SERVICE}**:
- Scale based on `{TOPIC_EXTRACTION_REQUESTED}` queue depth
- CPU-intensive (Docling, chunking)
- Memory: 4-8GB per instance
- Target: < 100 messages in queue

**{RETRIEVAL_SERVICE}**:
- Scale based on `{TOPIC_EMBEDDINGS_COMPLETE}` queue depth
- I/O-intensive (OpenSearch queries, Bedrock API calls)
- Memory: 4-8GB per instance
- Concurrent field extractions (asyncio.gather)

**OpenSearch Cluster**:
- Horizontal scaling: Add nodes as document volume grows
- Node type: r6g.xlarge (4 vCPU, 32GB RAM)
- Target: < 500 documents per node, < 80% disk usage

---

**Version**: 2.0
**Last Updated**: 2026-02-10
**Status**: Production-tested dual-service architecture
