# Indexing Strategy

> **Configuration for Your Project**
>
> Before implementing this section, ensure you've defined:
> - `{INDEXING_SERVICE}`: Your document processing service name (e.g., `document-ingestion`, `doc-processor`)
> - `{INDEX_PREFIX}`: Your OpenSearch index prefix (e.g., `documents`, `contracts`, `records`)
>
> Replace these placeholders throughout the code examples below.

## Document Processing Pipeline

The indexing pipeline transforms unstructured documents into searchable, semantically-aware chunks stored in OpenSearch.

**Pipeline Overview**:
```
PDF/DOCX/PPTX
  ↓
1. Docling Extraction → Structure + layout preservation
  ↓
2. Hierarchical Chunking → 512-token semantic chunks
  ↓
3. Embedding Generation → Bedrock Titan V2 (1024-dim)
  ↓
4. OpenSearch Index Creation → HNSW + BM25 configuration
  ↓
5. Bulk Indexing → Batch indexing (batch_size=50)
  ↓
OpenSearch Index: {INDEX_PREFIX}_{organization}_{doc_id}
```

## Step 1: Docling Extraction

**Location**: `/{INDEXING_SERVICE}/app/docling_processor.py`

**Purpose**: Preserve document structure and layout information

```python
from docling.document_converter import DocumentConverter

# Load with structure preservation
converter = DocumentConverter()
result = converter.convert("document.pdf")

# Extract:
# - Text with hierarchy (headings, paragraphs)
# - Tables with structure
# - Images with captions
# - Metadata (pages, positions)
```

**Key Features**:
- Layout-aware parsing (columns, headers, footers)
- Table structure preservation (rows, columns, cells)
- Image extraction with position metadata
- Page-level segmentation

## Step 2: Hierarchical Chunking

**Location**: `/{INDEXING_SERVICE}/app/chunking_pipeline.py`

**Configuration**:
```python
from llama_index.core.node_parser import DoclingNodeParser
from docling.chunking import HybridChunker
from transformers import AutoTokenizer

# Token-aware chunker
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
chunker = HybridChunker(
    tokenizer=tokenizer,
    max_tokens=512,        # Target chunk size
    merge_peers=True       # Consolidate small adjacent chunks
)

node_parser = DoclingNodeParser(chunker=chunker)
```

**Chunking Strategy**:
- **Token-based**: Ensures chunks fit embedding model limits
- **Semantic boundaries**: Splits at sentence/paragraph breaks
- **Hierarchy preservation**: Maintains section headers in metadata
- **Merge peers**: Combines small chunks to maximize context

**Metadata Structure**:
```python
{
    "docId": "abc123",                    # Document identifier
    "organization": "client_name",         # Tenant/org
    "page": 5,                            # Page number (0-indexed)
    "chunk_id": "abc123_chunk_42",        # Unique chunk ID
    "section_header": "Section Title",     # Current section
    "doc_items": [...],                   # Docling structural elements
    "doc_items_label": "paragraph",       # Element type (paragraph, table, image)
    "chunk_type": "text",                 # text | table | image
    "position": {"x": 100, "y": 200},     # Layout position (coordinates)
    "s3_path": "s3://...",                # Image location (if applicable)
    "image_width": 800,                   # Image dimensions
    "image_height": 600,
    "source_format": "pdf",               # Original format (pdf, docx, pptx)
    "created_at": "2026-02-10T12:00:00Z"  # Indexing timestamp
}
```

### Adapting to Your Document Types

#### Legal Contracts

**Chunking considerations**:
- Preserve clause boundaries (split at numbered sections)
- Maintain signature blocks as complete units
- Keep exhibit references with surrounding context

**Metadata additions**:
```python
{
    "clause_number": "5.2.3",
    "clause_type": "indemnification",
    "party_context": "seller_obligations",
    "is_signature_page": true
}
```

#### Medical Records

**Chunking considerations**:
- Respect section boundaries (History, Diagnosis, Treatment)
- Keep lab results tables intact
- Preserve prescription lists as single chunks

**Metadata additions**:
```python
{
    "record_section": "diagnosis",  # history, diagnosis, treatment, labs
    "record_date": "2026-01-15",
    "provider_name": "Dr. Smith",
    "is_table": true  # Lab results, vitals
}
```

#### Financial Documents

**Chunking considerations**:
- Keep transaction tables together
- Preserve account summary sections
- Maintain signature blocks for checks

**Metadata additions**:
```python
{
    "statement_section": "transactions",  # summary, transactions, notes
    "account_number": "****1234",
    "transaction_count": 15,
    "is_signature": true
}
```

## Step 3: Embedding Generation

**Location**: `/{INDEXING_SERVICE}/app/embedding_service.py`

**Service**: Bedrock Titan V2

```python
from llama_index.embeddings.bedrock import BedrockEmbedding

embed_model = BedrockEmbedding(
    model_name="amazon.titan-embed-text-v2:0",
    region_name="us-east-1",
    profile_name=None  # Uses IAM role from container
)

# Generate embedding
embedding = embed_model.get_text_embedding(chunk.text)
# Returns: List[float] with 1024 dimensions, normalized
```

**Handling Large Chunks**:
```python
def get_embedding(self, text: str) -> List[float]:
    """Generate embedding for text, handling Titan's 50k char limit."""
    if len(text) <= 45000:
        return self.embed_model.get_text_embedding(text)

    # Split with overlap
    chunks = self._split_text_into_chunks(
        text,
        max_length=45000,
        overlap=4500  # 10% overlap
    )

    # Embed each chunk
    chunk_embeddings = [
        self.embed_model.get_text_embedding(chunk)
        for chunk in chunks
    ]

    # Average embeddings (maintains cosine similarity properties)
    return self._average_embeddings(chunk_embeddings)
```

**Why Averaging Works**:
- Preserves semantic directionality
- Maintains cosine similarity relationships
- Better than truncation (no information loss)
- Standard practice for long-text embeddings

**Alternative Embedding Models**:
```python
# OpenAI (text-embedding-3-large)
from llama_index.embeddings.openai import OpenAIEmbedding
embed_model = OpenAIEmbedding(model="text-embedding-3-large")  # 3072 dimensions

# Cohere (embed-english-v3.0)
from llama_index.embeddings.cohere import CohereEmbedding
embed_model = CohereEmbedding(model_name="embed-english-v3.0")  # 1024 dimensions

# Hugging Face (local model)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-large-en-v1.5")  # 1024 dimensions
```

## Step 4: OpenSearch Index Creation

**Location**: `/{INDEXING_SERVICE}/app/opensearch_indexer.py`

**Index Settings**:
```python
INDEX_SETTINGS = {
    "settings": {
        "index": {
            "knn": True,                    # Enable k-NN plugin
            "number_of_shards": 1,          # Single shard (per-document index)
            "number_of_replicas": 0,        # No replicas (cost optimization)
            "refresh_interval": "1s"        # Fast refresh for real-time search
        }
    },
    "mappings": {
        "properties": {
            "text": {
                "type": "text",
                "analyzer": "standard"      # BM25 lexical search
            },
            "chunk_vector": {
                "type": "knn_vector",
                "dimension": 1024,          # Titan V2 dimension
                "method": {
                    "name": "hnsw",         # Hierarchical Navigable Small World
                    "space_type": "cosinesimil",  # Cosine similarity metric
                    "engine": "lucene",     # Lucene engine (vs. nmslib)
                    "parameters": {
                        "ef_construction": 512,   # Index build quality
                        "m": 16                   # Graph connections per node
                    }
                }
            },
            "metadata": {
                "properties": {
                    "docId": {"type": "keyword", "doc_values": True},
                    "page": {"type": "integer"},
                    "chunk_id": {"type": "keyword"},
                    "section_header": {"type": "text"},
                    "chunk_type": {"type": "keyword"},
                    # ... (15+ metadata fields)
                }
            }
        }
    }
}
```

**HNSW Parameters Explained**:
- **ef_construction (512)**: Higher = better recall, slower indexing
  - 128: Fast indexing, lower recall (~90%)
  - 512: Production balance (~95% recall)
  - 1024: Best recall (~98%), slow indexing
- **m (16)**: Number of bidirectional links per layer
  - 8: Less memory, lower recall
  - 16: Production balance (recommended)
  - 32: Better recall, more memory
- **cosinesimil**: Matches Titan V2 embeddings (normalized vectors)
  - Use `l2` for unnormalized embeddings
  - Use `innerproduct` for dot product similarity

**Index Naming Convention**:
```python
index_name = f"{INDEX_PREFIX}_{organization}_{doc_id}"
# Example: documents_acme_corp_abc123
# Example: contracts_client_a_doc_456
# Example: medical_records_patient_789
```

**Why Per-Document Indexes**:
- Document-level isolation (security, multi-tenancy)
- Easy deletion (drop entire index when document deleted)
- Avoid global index scaling issues (millions of chunks)
- Parallel processing (independent indexes)
- Tenant-specific retention policies

**When to Use Global Index**:
- Cross-document search ("find all contracts expiring in Q1")
- Small number of documents (< 1000)
- Single-tenant applications
- Shared knowledge base

## Step 5: Bulk Indexing

**Location**: `/{INDEXING_SERVICE}/app/opensearch_indexer.py`

**Implementation**:
```python
from opensearchpy import helpers as opensearch_helpers

async def bulk_index_chunks(
    client: OpenSearch,
    index_name: str,
    chunks: List[Dict],
    batch_size: int = 50
):
    """Bulk index chunks in batches for efficiency."""
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]

        actions = [
            {
                "_index": index_name,
                "_id": chunk["metadata"]["chunk_id"],
                "_source": {
                    "text": chunk["text"],
                    "chunk_vector": chunk["embedding"],
                    "metadata": chunk["metadata"]
                }
            }
            for chunk in batch
        ]

        success, failed = opensearch_helpers.bulk(
            client,
            actions,
            raise_on_error=False,  # Continue on partial failures
            max_retries=3,
            initial_backoff=2
        )

        if failed:
            logger.error(f"Failed to index {len(failed)} chunks: {failed}")
            raise IndexingError(f"Bulk indexing failed for {len(failed)} chunks")
```

**Batch Size Tuning**:
- **50 documents**: Good balance for most cases (~25-50KB per request)
- **20 documents**: For large chunks (> 5KB each) or tables with images
- **10 documents**: For image chunks (base64-encoded, ~100KB each)
- Too small (< 10): More HTTP overhead, slower indexing
- Too large (> 100): Risk of timeout, memory pressure, partial failures

**Memory Management**:

**❌ Memory-intensive (loads everything)**:
```python
# Don't do this for large documents
all_chunks = chunking_pipeline.chunk_document(doc)  # 10,000 chunks in memory
all_embeddings = await embedding_service.get_embeddings_batch(all_chunks)
await indexer.bulk_index_chunks(all_chunks, all_embeddings)
```

**✅ Streaming approach (constant memory)**:
```python
# Stream-based processing
async for chunk_batch in chunking_pipeline.chunk_document_stream(doc, batch_size=50):
    # Embed batch
    embeddings = await embedding_service.get_embeddings_batch(chunk_batch)

    # Index batch immediately
    await indexer.bulk_index_chunks(index_name, chunk_batch, embeddings)

    # Memory freed after each batch
```

**Error Handling Strategy**:
```python
# ✅ Fail-fast on critical errors
if not chunks:
    raise ValueError("No chunks to index")

if not opensearch_client:
    raise EnvironmentError("OpenSearch client not initialized")

# ✅ Log and re-raise indexing failures (no silent defaults)
try:
    success, failed = opensearch_helpers.bulk(...)
    if failed:
        logger.error(
            f"Bulk indexing failed",
            extra={
                "index": index_name,
                "failed_count": len(failed),
                "failed_ids": [f['index']['_id'] for f in failed],
                "errors": [f['index'].get('error') for f in failed]
            }
        )
        raise IndexingError(f"Failed to index {len(failed)} chunks")
except Exception as e:
    logger.error(f"Unexpected indexing error: {e}", extra={"index": index_name})
    raise  # Don't swallow errors
```

## Complete Indexing Pipeline Example

**End-to-end implementation**:
```python
from pathlib import Path
from typing import List, Dict

async def index_document(
    document_path: str,
    doc_id: str,
    organization: str,
    opensearch_client: OpenSearch
) -> str:
    """
    Complete indexing pipeline for a single document.

    Args:
        document_path: Path to document file (PDF, DOCX, PPTX)
        doc_id: Unique document identifier
        organization: Organization/tenant identifier
        opensearch_client: OpenSearch client

    Returns:
        Index name
    """
    # Step 1: Docling extraction
    converter = DocumentConverter()
    docling_result = converter.convert(document_path)

    # Step 2: Hierarchical chunking
    chunker = HybridChunker(max_tokens=512)
    node_parser = DoclingNodeParser(chunker=chunker)
    chunks = node_parser.get_nodes_from_documents([docling_result])

    # Step 3: Embedding generation
    embed_model = BedrockEmbedding(model_name="amazon.titan-embed-text-v2:0")

    # Step 4: Create index
    index_name = f"{INDEX_PREFIX}_{organization}_{doc_id}"
    opensearch_client.indices.create(index=index_name, body=INDEX_SETTINGS)

    # Step 5: Bulk indexing (streaming)
    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]

        # Generate embeddings for batch
        embeddings = [
            embed_model.get_text_embedding(chunk.text)
            for chunk in batch
        ]

        # Prepare bulk actions
        actions = [
            {
                "_index": index_name,
                "_id": f"{doc_id}_chunk_{i + j}",
                "_source": {
                    "text": chunk.text,
                    "chunk_vector": embeddings[j],
                    "metadata": {
                        **chunk.metadata,
                        "docId": doc_id,
                        "organization": organization,
                        "chunk_id": f"{doc_id}_chunk_{i + j}"
                    }
                }
            }
            for j, chunk in enumerate(batch)
        ]

        # Bulk index
        success, failed = opensearch_helpers.bulk(
            opensearch_client,
            actions,
            raise_on_error=False
        )

        if failed:
            raise IndexingError(f"Failed to index {len(failed)} chunks")

    logger.info(f"Successfully indexed {len(chunks)} chunks to {index_name}")
    return index_name
```

---

**Version**: 2.0
**Last Updated**: 2026-02-10
**Status**: Production-tested indexing pipeline
