# Retrieval Strategy

> **Configuration for Your Project**
>
> Before implementing this section, ensure you've defined:
> - `{RETRIEVAL_SERVICE}`: Your extraction service name (e.g., `intelligent-extraction`, `field-extractor`)
> - `{INDEX_PREFIX}`: Your OpenSearch index prefix (e.g., `documents`, `contracts`, `records`)
> - `{FIELD_NAME}`: Placeholder for field-specific configuration
>
> Replace these placeholders throughout the code examples below.

## Dual Retrieval Implementations

The system provides **two retrieval strategies** serving different use cases:

| Feature | HybridRetriever | RetrievalPipeline |
|---------|-----------------|-------------------|
| **Location** | `/{RETRIEVAL_SERVICE}/domain/extraction/retrieval.py` | `/{RETRIEVAL_SERVICE}/domain/extraction/retrieval_pipeline.py` |
| **Approach** | Single-call native hybrid | Three-phase custom |
| **OpenSearch Calls** | 1 call | 2 calls (BM25 + KNN) |
| **Score Combination** | OpenSearch pipeline | Manual Python logic |
| **Intersection Boost** | No | Yes (2.0x multiplier) |
| **Normalization** | min_max (automatic) | Manual (divide by 10) |
| **Complexity** | Simple | Complex |
| **Performance** | Faster (1 call) | Slower (2 calls + processing) |
| **Flexibility** | Limited | High (custom boost logic) |
| **Debugging** | Limited visibility | Full phase visibility |

### Strategy Selection Decision Matrix

```
Start: Need to retrieve chunks for field extraction
  │
  ↓
[Q] Do you need intersection boost (identify consensus matches)?
  ├─ NO  → Use HybridRetriever
  │         └─ Simpler, faster, suitable for most fields
  │         └─ Single OpenSearch call
  │         └─ Native score normalization (statistically sound)
  │
  └─ YES → Use RetrievalPipeline
            └─ Identifies chunks found by BOTH BM25 and KNN
            └─ 2.0x boost for intersection chunks
            └─ Two OpenSearch calls (higher latency)
            └─ Manual score normalization (requires tuning)
  │
  ↓
[Q] Do you need custom field-specific boost logic?
  ├─ NO  → Use HybridRetriever
  │         └─ Standard hybrid search sufficient
  │
  └─ YES → Use RetrievalPipeline
            └─ Can apply custom logic per field
            └─ Full control over score combination
  │
  ↓
[Q] Is debugging visibility critical?
  ├─ NO  → Use HybridRetriever
  │         └─ Black-box hybrid search
  │
  └─ YES → Use RetrievalPipeline
            └─ Can inspect BM25 and KNN results separately
            └─ Easier to diagnose retrieval issues
```

**Recommendation**: Standardize on **HybridRetriever** for most fields, use **RetrievalPipeline** only when intersection boost significantly improves extraction accuracy.

## Strategy 1: HybridRetriever (Native OpenSearch)

**Location**: `/{RETRIEVAL_SERVICE}/domain/extraction/retrieval.py`

**Architecture**:
```python
def retrieve(
    self,
    doc_id: str,
    field_name: str,
    field_config: Dict[str, Any],
    index_name: str
) -> List[NodeWithScore]:
    """Execute single-call hybrid search using OpenSearch native pipeline."""

    # Step 1: Build query strings
    bm25_query = self._build_bm25_query(field_config)
    # Combines: queries.*, keywords, keywords_search

    knn_query = self._build_knn_query(field_name, field_config)
    # Uses: instructions.task for semantic context

    # Step 2: Generate query embedding
    query_embedding = self.embed_model.get_text_embedding(knn_query)

    # Step 3: Create hybrid query
    query = VectorStoreQuery(
        query_embedding=query_embedding,    # Semantic (KNN)
        query_str=bm25_query,               # Lexical (BM25)
        similarity_top_k=100,               # Max results
        mode=VectorStoreQueryMode.HYBRID,   # Native hybrid mode
        filters=MetadataFilters(            # Document filter
            filters=[
                MetadataFilter(
                    key="docId",
                    value=doc_id,
                    operator=FilterOperator.EQ
                )
            ]
        )
    )

    # Step 4: Execute search (single OpenSearch call)
    result = self.vector_store.query(query)

    # Step 5: Convert to NodeWithScore
    nodes = [
        NodeWithScore(node=node, score=score)
        for node, score in zip(result.nodes, result.similarities)
    ]

    # Step 6: Filter by minimum score
    nodes = [n for n in nodes if (n.score or 0) >= self.config.min_score]

    # Step 7: Apply post-processors
    return self._apply_post_processors(nodes, doc_id, field_name, field_config, index_name)
```

### OpenSearch Hybrid Pipeline Configuration

```python
HYBRID_SEARCH_PIPELINE_NAME = "hybrid-search-pipeline"

HYBRID_SEARCH_PIPELINE_BODY = {
    "phase_results_processors": [
        {
            "normalization-processor": {
                "normalization": {
                    "technique": "min_max"  # Normalize to [0, 1]
                },
                "combination": {
                    "technique": "arithmetic_mean",
                    "parameters": {
                        "weights": [0.5, 0.5]  # 50% BM25, 50% KNN
                    }
                }
            }
        }
    ]
}
```

**Score Normalization (OpenSearch Native)**:
```
BM25 score range: [0, unbounded] → min_max → [0, 1]
KNN score range:  [0, 1]         → already normalized

Combined score = (BM25_normalized * 0.5) + (KNN_normalized * 0.5)
```

### Query Building Patterns

**Generic Query Template**:
```python
def _build_bm25_query(self, field_config: Dict) -> str:
    """
    Build BM25 query from field configuration.

    Field config structure:
    {
        "queries": {
            "exact": "specific keyword query",
            "pattern": "natural language pattern",
            "fuzzy": "fuzzy matching terms"
        },
        "instructions": {
            "keywords": ["keyword1", "keyword2", ...]
        },
        "keywords_search": ["related", "terms", ...]
    }
    """
    query_parts = []

    # Add all query variations
    query_parts.extend(field_config.get('queries', {}).values())

    # Add keywords from instructions
    query_parts.extend(field_config.get('instructions', {}).get('keywords', []))

    # Add additional search keywords
    query_parts.extend(field_config.get('keywords_search', []))

    # Combine into single query string
    return ' '.join(filter(None, query_parts))

def _build_knn_query(self, field_name: str, field_config: Dict) -> str:
    """
    Build KNN query from task description.

    Uses semantic task description for embedding generation.
    """
    task = field_config.get('instructions', {}).get('task')
    if task:
        return task
    else:
        # Fallback: generic extraction prompt
        return f"Extract {field_name} from the document"
```

**Example field configurations by domain**:

**Legal Contracts**:
```python
{
    "field_name": "party_name",
    "queries": {
        "exact": "party name signatory",
        "pattern": "who is signing this contract",
        "fuzzy": "contracting parties signatories"
    },
    "instructions": {
        "task": "Extract the names of the parties signing the contract",
        "keywords": ["party", "signatory", "contractor", "vendor", "client"]
    },
    "keywords_search": ["agreement", "contract", "signed", "undersigned"]
}
```

**Medical Records**:
```python
{
    "field_name": "diagnosis_code",
    "queries": {
        "exact": "ICD-10 diagnosis code",
        "pattern": "what is the diagnosis",
        "fuzzy": "medical condition diagnosis ICD"
    },
    "instructions": {
        "task": "Extract the ICD-10 diagnosis code from the medical record",
        "keywords": ["diagnosis", "ICD-10", "ICD", "condition", "disease"]
    },
    "keywords_search": ["primary", "secondary", "admission", "discharge"]
}
```

**Financial Documents**:
```python
{
    "field_name": "account_number",
    "queries": {
        "exact": "account number",
        "pattern": "what is the account identifier",
        "fuzzy": "acct number account ID"
    },
    "instructions": {
        "task": "Extract the account number from the statement",
        "keywords": ["account", "number", "ID", "identifier"]
    },
    "keywords_search": ["checking", "savings", "primary", "routing"]
}
```

### Advantages & Disadvantages

**Advantages**:
- ✅ Single OpenSearch call (lower latency: ~120ms vs ~250ms)
- ✅ Native normalization (statistically sound min_max technique)
- ✅ Simpler code (less maintenance burden)
- ✅ Consistent scoring (OpenSearch handles edge cases)
- ✅ Built-in support in LlamaIndex

**Disadvantages**:
- ❌ No intersection boost (can't identify consensus matches)
- ❌ Less flexibility (tied to OpenSearch pipeline configuration)
- ❌ Limited customization (can't apply field-specific boost logic)
- ❌ Black-box scoring (harder to debug why chunks ranked as they are)

## Strategy 2: RetrievalPipeline (Custom Three-Phase)

**Location**: `/{RETRIEVAL_SERVICE}/domain/extraction/retrieval_pipeline.py`

**Architecture**:
```python
def retrieve(
    self,
    doc_id: str,
    field_name: str,
    field_config: Dict[str, Any],
    index_name: str
) -> List[NodeWithScore]:
    """Execute three-phase retrieval with custom intersection boost."""

    # Phase 1: BM25 Retrieval
    bm25_chunks = self.phase1_bm25_retrieval(
        opensearch_client,
        index_name,
        doc_id,
        field_name,
        field_config
    )

    # Phase 2: KNN Semantic Search
    knn_chunks = self.phase2_knn_retrieval(
        opensearch_client,
        index_name,
        doc_id,
        field_name,
        field_config
    )

    # Phase 3: Combine with Intersection Boost
    combined_chunks = self.phase3_combine_and_rank(
        bm25_chunks,
        knn_chunks,
        field_name,
        field_config
    )

    # Convert to NodeWithScore
    nodes = self._chunks_to_nodes(combined_chunks)

    # Apply post-processors
    return self._apply_post_processors(nodes, doc_id, field_name, field_config, index_name)
```

### Phase 1: BM25 Lexical Search

**Query Structure**:
```python
def phase1_bm25_retrieval(self, client, index_name, doc_id, field_name, config):
    """Execute BM25 search with fuzzy matching."""

    # Build combined query from multiple sources
    query_parts = []
    query_parts.extend(config.get('queries', {}).values())
    query_parts.extend(config.get('instructions', {}).get('keywords', []))
    query_parts.extend(config.get('keywords_search', []))
    combined_query = ' '.join(query_parts)

    search_body = {
        "size": config.get('max_bm25_results', 100),
        "min_score": config.get('bm25_score_threshold', 0.5),
        "query": {
            "bool": {
                "must": [
                    {
                        "multi_match": {
                            "query": combined_query,
                            "fields": ["text"],
                            "type": "best_fields",  # Best single field match
                            "operator": "or",       # Any keyword match
                            "fuzziness": "AUTO"     # Typo tolerance (edit distance 1-2)
                        }
                    }
                ],
                "filter": [
                    {"term": {"metadata.docId": doc_id}}
                ]
            }
        }
    }

    response = client.search(index=index_name, body=search_body)

    return [
        {
            'chunk_id': hit['_id'],
            'text': hit['_source']['text'],
            'metadata': hit['_source']['metadata'],
            'bm25_score': hit['_score'],
            'knn_score': 0.0  # Placeholder
        }
        for hit in response['hits']['hits']
    ]
```

**BM25 Parameters**:
- **best_fields**: Scores based on single best-matching field (vs. cross_fields which combines)
- **operator: "or"**: Returns docs matching ANY keyword (vs. "and" requiring all)
- **fuzziness: AUTO**:
  - 0 edits for terms length 1-2
  - 1 edit for terms length 3-5
  - 2 edits for terms length > 5
- **min_score: 0.5**: Filters out low-relevance matches (noise reduction)

### Phase 2: KNN Semantic Search

**Query Structure**:
```python
def phase2_knn_retrieval(self, client, index_name, doc_id, field_name, config):
    """Execute pure KNN vector search."""

    # Use task description for semantic query
    task_query = config.get('instructions', {}).get('task', f"Extract {field_name}")

    # Generate query embedding
    query_vector = self.embed_model.get_text_embedding(task_query)

    search_body = {
        "size": config.get('max_knn_results', 100),
        "query": {
            "knn": {
                "chunk_vector": {
                    "vector": query_vector,
                    "k": config.get('max_knn_results', 100),
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"metadata.docId": doc_id}}
                            ]
                        }
                    }
                }
            }
        }
    }

    response = client.search(index=index_name, body=search_body)

    # Post-filter by score threshold
    knn_threshold = config.get('knn_score_threshold', 0.3)
    filtered_hits = [
        hit for hit in response['hits']['hits']
        if hit['_score'] >= knn_threshold
    ]

    return [
        {
            'chunk_id': hit['_id'],
            'text': hit['_source']['text'],
            'metadata': hit['_source']['metadata'],
            'bm25_score': 0.0,  # Placeholder
            'knn_score': hit['_score']
        }
        for hit in filtered_hits
    ]
```

**KNN Parameters**:
- **k: 100**: Return top 100 most semantically similar chunks
- **cosine similarity**: Calculated via HNSW (configured in index)
- **filter**: Document-level isolation (ensures single-doc retrieval)
- **threshold: 0.3**: Lower than BM25 (semantic relevance is fuzzier)

### Phase 3: Score Combination & Intersection Boost

**Combination Logic**:
```python
def phase3_combine_and_rank(self, bm25_chunks, knn_chunks, field_name, config):
    """Combine scores with intersection boost for high-confidence matches."""

    # Identify intersection (chunks in BOTH phases)
    bm25_ids = {chunk['chunk_id'] for chunk in bm25_chunks}
    knn_ids = {chunk['chunk_id'] for chunk in knn_chunks}
    intersection_ids = bm25_ids & knn_ids

    # Combine chunks (union of both phases)
    combined_dict = {}

    for chunk in bm25_chunks + knn_chunks:
        chunk_id = chunk['chunk_id']
        if chunk_id not in combined_dict:
            combined_dict[chunk_id] = chunk
        else:
            # Merge scores from both phases
            combined_dict[chunk_id]['bm25_score'] = max(
                combined_dict[chunk_id]['bm25_score'],
                chunk['bm25_score']
            )
            combined_dict[chunk_id]['knn_score'] = max(
                combined_dict[chunk_id]['knn_score'],
                chunk['knn_score']
            )

    # Calculate combined scores
    intersection_boost = config.get('intersection_boost', 2.0)

    for chunk_id, chunk in combined_dict.items():
        # Normalize BM25 to [0, 1] (divide by 10 - heuristic)
        bm25_normalized = min(chunk['bm25_score'] / 10.0, 1.0)
        knn_normalized = chunk['knn_score']  # Already [0, 1]

        # 50/50 weighted average
        base_score = (bm25_normalized * 0.5) + (knn_normalized * 0.5)

        # Apply intersection boost
        if chunk_id in intersection_ids:
            chunk['combined_score'] = base_score * intersection_boost
            chunk['in_both_phases'] = True
        else:
            chunk['combined_score'] = base_score
            chunk['in_both_phases'] = False

    # Sort by combined score
    ranked_chunks = sorted(
        combined_dict.values(),
        key=lambda x: x['combined_score'],
        reverse=True
    )

    # Separate text and image chunks
    text_chunks = [c for c in ranked_chunks if c['metadata'].get('chunk_type') != 'image']
    image_chunks = [c for c in ranked_chunks if c['metadata'].get('chunk_type') == 'image']

    # Select top-k text + limited images
    final_top_k = config.get('final_top_k', 10)
    max_images = config.get('visual_analysis', {}).get('max_images', 4)

    return text_chunks[:final_top_k] + image_chunks[:max_images]
```

**Intersection Boost Rationale**:
- **Consensus signal**: Chunks found by BOTH lexical and semantic search are high-confidence
- **2.0x multiplier**: Doubles the score for intersection chunks
- **Example**:
  - Chunk A (BM25 only): score = 0.6 → final = 0.6
  - Chunk B (KNN only): score = 0.5 → final = 0.5
  - Chunk C (both): score = 0.4 → final = 0.4 * 2.0 = **0.8** (now top-ranked)

**Known Issues**:
```python
# ⚠️ Issue 1: BM25 normalization uses magic constant
bm25_normalized = min(chunk['bm25_score'] / 10.0, 1.0)
# Problem: BM25 scores are unbounded - dividing by 10 is arbitrary
# Better: Use min-max normalization or percentile-based approach

# ⚠️ Issue 2: Intersection boost is binary (2x or 1x)
if chunk_id in intersection_ids:
    chunk['combined_score'] = base_score * 2.0
# Problem: No gradation based on score strength
# Better: Variable boost based on agreement magnitude
# agreement_factor = 1.0 + (bm25_normalized * knn_normalized) * 0.5
```

### Advantages & Disadvantages

**Advantages**:
- ✅ Intersection boost (identifies consensus matches - proven to improve accuracy)
- ✅ High flexibility (custom boost logic per field)
- ✅ Separation of concerns (distinct BM25/KNN phases)
- ✅ Debugging visibility (can inspect each phase independently)
- ✅ Field-specific customization (apply domain logic)

**Disadvantages**:
- ❌ Two OpenSearch calls (higher latency: ~250ms vs ~120ms)
- ❌ Manual normalization (potential for bugs, requires calibration)
- ❌ More complex (harder to maintain, more code)
- ❌ Arbitrary constants (divide by 10, 2x boost - need tuning)

## Score Thresholding & Calibration

### Threshold Configuration

```python
{
    "field_name": "{FIELD_NAME}",
    "bm25_score_threshold": 0.5,  # Minimum lexical relevance
    "knn_score_threshold": 0.3,   # Minimum semantic similarity
    "min_score": 0.4,             # Minimum combined score (HybridRetriever only)
    "intersection_boost": 2.0     # Score multiplier for consensus matches
}
```

### Calibration Methodology

1. **Collect ground truth**: Sample 100 documents with known fields
2. **Run retrieval**: Execute on all samples, collect scores
3. **Analyze distribution**: Plot score distributions for correct/incorrect matches
4. **Set thresholds**: Choose values that maximize F1 score

**Example analysis**:
```python
# Score distribution for correct matches
Correct matches:
  BM25:  Mean=8.5,  Median=7.2,  Min=2.1,  Max=45.3
  KNN:   Mean=0.72, Median=0.68, Min=0.42, Max=0.95

# Score distribution for incorrect matches
Incorrect matches:
  BM25:  Mean=2.1,  Median=1.5,  Min=0.1,  Max=8.9
  KNN:   Mean=0.35, Median=0.32, Min=0.05, Max=0.58

# Recommended thresholds
Recommended:
  BM25: 0.5 (normalized) → filters 85% of incorrect matches
  KNN:  0.3              → filters 78% of incorrect matches
```

### Field-Specific Tuning

**High-precision fields** (identifiers, codes, numbers):
```python
{
    "bm25_score_threshold": 0.7,  # Stricter
    "knn_score_threshold": 0.5
}
```

**Fuzzy fields** (descriptions, narratives, summaries):
```python
{
    "bm25_score_threshold": 0.3,  # More permissive
    "knn_score_threshold": 0.2
}
```

---

**Version**: 2.0
**Last Updated**: 2026-02-10
**Status**: Production-tested dual retrieval strategies
