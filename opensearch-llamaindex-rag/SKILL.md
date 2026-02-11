---
name: opensearch-llamaindex-rag
description: "This skill should be used when implementing hybrid retrieval-augmented generation (RAG) systems using OpenSearch and LlamaIndex. Provides production-grade guidance on dual-service architecture, vector + lexical hybrid search (BM25 + KNN), HNSW indexing, post-processing pipelines, and intelligent field extraction from unstructured documents."
---

# OpenSearch + LlamaIndex RAG Architecture

## Overview

This skill provides production-tested patterns for building hybrid RAG systems that combine OpenSearch's vector (HNSW) and lexical (BM25) search capabilities with LlamaIndex's chunking and retrieval orchestration. The architecture has been proven in production for intelligent document processing, achieving ~3.5s latency per field extraction and $0.02-0.55 per document cost depending on model choice.

The guidance covers a complete dual-service architecture: an indexing service that chunks, embeds, and indexes documents, and a retrieval service that performs hybrid search, post-processing, and intelligent extraction. All patterns follow fail-fast error handling, structured observability, and production-grade best practices.

## When to Use This Skill

Use this skill when:
- Building a RAG system for document understanding, question answering, or field extraction
- Implementing hybrid search combining semantic (vector) and lexical (keyword) retrieval
- Designing chunking strategies for complex documents (PDFs, DOCX, PPTX with tables/images)
- Setting up per-document or multi-tenant OpenSearch indexes with HNSW vector search
- Implementing custom post-processing logic for retrieval (page boost, context expansion, visual evidence)
- Optimizing retrieval accuracy with intersection boost or custom scoring
- Integrating Docling for document structure preservation (layout, tables, hierarchies)
- Designing producer-consumer architecture for document processing pipelines
- Tuning performance, cost, and accuracy trade-offs in production RAG systems

**Trigger scenarios**:
- "How do I implement hybrid search with OpenSearch and LlamaIndex?"
- "What's the best chunking strategy for documents with tables and images?"
- "How do I boost retrieval accuracy for specific pages or fields?"
- "Should I use per-document indexes or a global index in OpenSearch?"
- "How do I combine BM25 and KNN scores effectively?"
- "What HNSW parameters should I use for production?"
- "How do I add surrounding chunks for better context?"
- "What's the optimal batch size for bulk indexing?"

## Configuration Placeholders

Before applying this skill, identify your project-specific values:

**Service Names**:
- `{INDEXING_SERVICE}` - Service that chunks, embeds, and indexes documents (e.g., `document-ingestion`, `doc-processor`)
- `{RETRIEVAL_SERVICE}` - Service that retrieves and extracts (e.g., `intelligent-extraction`, `field-extractor`)
- `{ORCHESTRATION_SERVICE}` - API/orchestrator (e.g., `main-api`, `gateway`)

**Messaging Topics** (if using Kafka/SQS/EventBridge):
- `{TOPIC_EXTRACTION_REQUESTED}` - Trigger for indexing pipeline
- `{TOPIC_EMBEDDINGS_COMPLETE}` - Indexing completion signal
- `{TOPIC_EXTRACTION_COMPLETE}` - Extraction completion signal

**Index Configuration**:
- `{INDEX_PREFIX}` - OpenSearch index prefix (e.g., `documents`, `contracts`, `medical_records`)
- `{DOMAIN_FIELDS}` - Fields to extract (e.g., `contract_date`, `party_name`, `diagnosis_code`)

Throughout the reference documents, replace these placeholders with your project values.

## How to Use This Skill

### Understanding the Architecture

For system design, service responsibilities, and data flow patterns:
- Consult `references/01-architecture.md` for dual-service producer-consumer pattern, component overview, and deployment strategies

**Example questions**:
- "How should I structure my RAG services?"
- "What's the producer-consumer pattern for document indexing?"
- "How do I separate indexing from retrieval responsibilities?"
- "What messaging patterns work for document processing pipelines?"

### Implementing Indexing

For document processing, chunking, embedding, and OpenSearch indexing:
- Consult `references/02-indexing-strategy.md` for Docling integration, hierarchical chunking, embedding generation, HNSW configuration, bulk indexing, and memory management

**Example questions**:
- "How do I chunk documents with Docling while preserving structure?"
- "What HNSW parameters should I use for 1024-dim embeddings?"
- "How do I handle embeddings larger than the model's token limit?"
- "What's the optimal batch size for bulk indexing?"
- "How do I create per-document indexes in OpenSearch?"
- "What metadata should I store with each chunk?"

### Implementing Retrieval

For hybrid search, score combination, and dual retrieval strategies:
- Consult `references/03-retrieval-strategy.md` for BM25 + KNN hybrid search, single-call vs. three-phase retrieval, intersection boost, score normalization, and query construction

**Example questions**:
- "How do I implement native OpenSearch hybrid search?"
- "What's the difference between single-call and three-phase retrieval?"
- "How do I boost chunks found in both BM25 and KNN results?"
- "What score thresholds should I use for BM25 and KNN?"
- "How do I build queries from field configurations?"
- "When should I use HybridRetriever vs RetrievalPipeline?"

### Implementing Post-Processing

For ranking enhancements, context expansion, and visual evidence:
- Consult `references/04-post-processing.md` for page boost, adjacent chunk expansion, image supplementation, and final top-k selection

**Example questions**:
- "How do I boost chunks from specific pages (e.g., cover page)?"
- "How do I add surrounding chunks for context continuity?"
- "How many images should I include for visual extraction?"
- "What's the correct execution order for post-processors?"
- "How do I implement custom post-processors?"
- "When should I use adjacent chunk expansion?"

### Production Best Practices

For authentication, error handling, observability, and configuration management:
- Consult `references/05-best-practices.md` for IAM authentication (no STS delays), fail-fast error patterns, structured logging, distributed tracing, and field-level configuration

**Example questions**:
- "How do I authenticate to OpenSearch without STS delays?"
- "What's the fail-fast error handling pattern for indexing?"
- "How do I implement structured logging for retrieval metrics?"
- "How do I manage field-level configuration in production?"
- "What observability patterns should I use?"
- "How do I tune batch sizes for different chunk types?"

### Configuration & Performance

For tuning, cost optimization, scaling, and troubleshooting:
- Consult `references/06-configuration-reference.md` for all configuration options, latency breakdown, cost analysis, scaling strategies, and common issues

**Example questions**:
- "What are the recommended embedding and retrieval configs?"
- "How do I optimize cost between different LLM models?"
- "How do I scale OpenSearch for thousands of documents?"
- "Why is my retrieval latency high?"
- "How do I calibrate score thresholds?"
- "What's the cost per document for extraction?"

## Key Architectural Decisions

All guidance follows these production-tested patterns:

1. **Dual-Service Architecture** - Separate indexing (producer) from retrieval (consumer) for independent scaling and failure isolation

2. **Hybrid Search** - Combine BM25 (lexical/keyword) and KNN (semantic/vector) for comprehensive recall across different query types

3. **HNSW Indexing** - Use `ef_construction=512, m=16` for optimal recall/performance balance with 1024-dimensional embeddings

4. **Per-Document Indexes** - Isolate documents in separate OpenSearch indexes for multi-tenancy, security, and parallel processing

5. **Post-Processing Pipeline** - Apply domain logic after retrieval (page boost for critical pages, context expansion for continuity, visual evidence for extraction)

6. **Fail-Fast Error Handling** - No silent defaults, explicit failures with comprehensive logging (errors must surface immediately)

7. **Observable by Default** - Structured JSON logging and distributed tracing for production visibility (DataDog APM, OpenLLMetry)

## Domain Example: Property Insurance

The reference documents include concrete examples from a property insurance extraction system (extracting building details like roof geometry, construction type, policy numbers). These serve as implementation patterns - apply the same techniques to your domain:

- **Legal contracts**: Extract party names, contract dates, clause types
- **Medical records**: Extract diagnoses, medications, patient demographics
- **Financial documents**: Extract account numbers, transaction details, compliance data
- **Research papers**: Extract methodologies, findings, citations

The technical patterns (chunking, hybrid search, post-processing) remain the same; only the field names and domain-specific logic change.

## Quick Reference: Key Metrics

| Metric | Value | Description |
|--------|-------|-------------|
| **Embedding Dimension** | 1024 | Bedrock Titan V2 (adjust for your model) |
| **Chunk Size** | 512 tokens | ~2000 characters with semantic boundaries |
| **Max Retrieval** | 100 chunks | Before post-processing filters |
| **Final Context** | 10 text + 4 image | Chunks sent to LLM for extraction |
| **BM25 Threshold** | 0.5 | Minimum lexical relevance score |
| **KNN Threshold** | 0.3 | Minimum semantic similarity (cosine) |
| **Intersection Boost** | 2.0x | Score multiplier for dual-phase matches |
| **Indexing Batch Size** | 50 documents | Bulk indexing chunk size (tune by size) |
| **HNSW ef_construction** | 512 | Index build quality (higher = better recall) |
| **HNSW m** | 16 | Graph connections per node (balance) |

---

**Version**: 2.0
**Last Updated**: 2026-02-10
**Production Status**: Battle-tested in document processing systems
