# Post-Processing Pipeline

> **Configuration for Your Project**
>
> Before implementing this section, ensure you've defined:
> - `{INDEXING_SERVICE}`: Your document processing service name (e.g., `document-ingestion`, `doc-processor`)
> - `{RETRIEVAL_SERVICE}`: Your extraction service name (e.g., `intelligent-extraction`, `field-extractor`)
> - `{INDEX_PREFIX}`: Your OpenSearch index prefix (e.g., `documents`, `contracts`, `records`)
> - `{FIELD_NAME}`: Placeholder for field-specific configuration
>
> Replace these placeholders throughout the code examples below.

## Overview

Post-processors run **after retrieval** to enhance context and apply domain-specific logic. They implement the LlamaIndex `BaseNodePostprocessor` interface.

**Execution Order** (critical - order matters!):
```python
retrieved_nodes = hybrid_retriever.retrieve(...)

# 1. PageBoostPostprocessor (boost critical pages)
nodes = page_boost_processor.postprocess_nodes(nodes)

# 2. AdjacentChunkExpander (add surrounding context)
nodes = adjacent_expander.postprocess_nodes(nodes)

# 3. ImageSupplementPostprocessor (add visual evidence)
nodes = image_supplement_processor.postprocess_nodes(nodes)

# 4. FinalTopKSelector (limit final context size)
nodes = final_selector.postprocess_nodes(nodes)
```

## Post-Processor Selection Decision Tree

```
Start: Retrieved chunks from hybrid search
  │
  ↓
[Q] Does the field appear on known pages (e.g., cover, summary)?
  ├─ YES → Use PageBoostPostprocessor
  │          └─ boost_pages=[0] for first page
  │          └─ boost_amount=100.0 (default)
  │
  └─ NO  → Skip page boost
  │
  ↓
[Q] Does the field need surrounding context for accuracy?
  ├─ YES → Use AdjacentChunkExpander
  │          └─ Clauses split across chunks
  │          └─ Table rows spanning pages
  │          └─ Multi-sentence descriptions
  │          └─ num_before=1, num_after=1 (default)
  │
  └─ NO  → Skip adjacent expansion
  │
  ↓
[Q] Does the field require visual evidence?
  ├─ YES → Use ImageSupplementPostprocessor
  │          └─ High visual: 4 images (e.g., building photos, diagrams)
  │          └─ Medium visual: 2-3 images (e.g., signatures, stamps)
  │          └─ Low visual: 0-1 images (e.g., identifiers, codes)
  │
  └─ NO  → image_priority=false (text-only)
  │
  ↓
ALWAYS use FinalTopKSelector
  └─ Limits text chunks to final_top_k=10 (default)
  └─ Keeps all images (already limited by ImageSupplement)
```

## 1. PageBoostPostprocessor

**Location**: `/{RETRIEVAL_SERVICE}/domain/processing/postprocessors.py`

**Purpose**: Boost chunks from critical pages (e.g., cover page, summary page)

**Implementation**:
```python
class PageBoostPostprocessor(BaseNodePostprocessor):
    """Boost nodes from specific pages to prioritize critical sections."""

    def __init__(self, boost_pages: List[int] = None, boost_amount: float = 100.0):
        """
        Args:
            boost_pages: List of page numbers to boost (0-indexed)
            boost_amount: Score increment for boosted pages
        """
        self._boost_pages = set(boost_pages or [])
        self._boost_amount = boost_amount

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        """Apply page boost and re-sort."""
        for node in nodes:
            page = node.node.metadata.get('page')
            if page in self._boost_pages:
                original_score = node.score or 0.0
                node.score = original_score + self._boost_amount
                node.node.metadata['boost_source'] = 'page_boost'
                node.node.metadata['original_score'] = original_score

        # Re-sort by score
        return sorted(nodes, key=lambda x: x.score or 0, reverse=True)
```

**Configuration Example**:
```python
# Field config (from centralized configuration)
{
    "field_name": "{FIELD_NAME}",
    "page_boost": [0],  # Boost cover page (field usually on first page)
    # ...
}

# Creates processor
processor = PageBoostPostprocessor(boost_pages=[0], boost_amount=100.0)
```

**Use Cases by Domain**:
- **Legal contracts**: Party names on signature page (last page)
- **Medical records**: Patient ID on cover page, diagnosis on summary page
- **Financial documents**: Account numbers on first page, totals on last page
- **Research papers**: Abstract on page 1, conclusions on last page

**Effect**:
```
Original ranking:
1. Chunk from page 5 (score: 0.85)
2. Chunk from page 3 (score: 0.80)
3. Chunk from page 0 (score: 0.60)  ← Cover page

After page boost (+100):
1. Chunk from page 0 (score: 100.60)  ← Now top-ranked
2. Chunk from page 5 (score: 0.85)
3. Chunk from page 3 (score: 0.80)
```

## 2. AdjacentChunkExpander

**Purpose**: Add surrounding chunks for context preservation

**Implementation**:
```python
class AdjacentChunkExpander(BaseNodePostprocessor):
    """Add chunks before/after selected chunks for context continuity."""

    def __init__(
        self,
        opensearch_client: OpenSearch,
        index_name: str,
        doc_id: str,
        num_before: int = 1,
        num_after: int = 1
    ):
        """
        Args:
            num_before: Number of chunks to add before each selected chunk
            num_after: Number of chunks to add after each selected chunk
        """
        self._client = opensearch_client
        self._index_name = index_name
        self._doc_id = doc_id
        self._num_before = num_before
        self._num_after = num_after

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        """Expand each node with adjacent chunks."""
        expanded_nodes = []
        seen_chunk_ids = set()

        for node in nodes:
            # Add original node
            if node.node.metadata['chunk_id'] not in seen_chunk_ids:
                expanded_nodes.append(node)
                seen_chunk_ids.add(node.node.metadata['chunk_id'])

            # Get adjacent chunks on same page
            page = node.node.metadata.get('page')
            position = node.node.metadata.get('position', {})

            # Query: all chunks on this page, sorted by position
            adjacent_chunks = self._get_adjacent_chunks(page, position)

            # Add num_before chunks
            for adj_chunk in adjacent_chunks[:self._num_before]:
                if adj_chunk['chunk_id'] not in seen_chunk_ids:
                    adj_node = self._create_adjacent_node(adj_chunk, node)
                    expanded_nodes.append(adj_node)
                    seen_chunk_ids.add(adj_chunk['chunk_id'])

            # Add num_after chunks
            for adj_chunk in adjacent_chunks[-self._num_after:]:
                if adj_chunk['chunk_id'] not in seen_chunk_ids:
                    adj_node = self._create_adjacent_node(adj_chunk, node)
                    expanded_nodes.append(adj_node)
                    seen_chunk_ids.add(adj_chunk['chunk_id'])

        return expanded_nodes

    def _create_adjacent_node(self, chunk_data: Dict, original_node: NodeWithScore) -> NodeWithScore:
        """Create node for adjacent chunk with special metadata."""
        node = TextNode(
            text=chunk_data['text'],
            metadata={
                **chunk_data['metadata'],
                'is_adjacent': True,
                'adjacent_to': original_node.node.metadata['chunk_id']
            }
        )
        # Score = 0 (context only, not a semantic match)
        return NodeWithScore(node=node, score=0.0)
```

**Rationale**:
- **Context preservation**: Relevant info may span multiple chunks
- **Sentence boundaries**: Chunking can split mid-sentence or mid-paragraph
- **Table continuity**: Table rows may be split across chunks
- **Zero score**: Adjacent chunks don't inflate relevance scores

**Example**:
```
Selected chunk (score: 0.85):
"The building features modern construction with energy-efficient systems."

Adjacent chunk before (score: 0.0):
"The property is located at 123 Main Street, Springfield."

Adjacent chunk after (score: 0.0):
"Installation was completed in 2020 and meets current building codes."

→ LLM receives full context for better extraction
```

## 3. ImageSupplementPostprocessor

**Purpose**: Add image chunks as visual evidence for extraction

**Implementation**:
```python
class ImageSupplementPostprocessor(BaseNodePostprocessor):
    """Add image chunks for visual field extraction."""

    # Field-specific image slot configuration
    VISUAL_FIELD_IMAGE_SLOTS = {
        # High visual dependency (4 images)
        "building_photos": 4,      # Architecture, structure
        "diagram_analysis": 4,     # Technical drawings
        "signature_verification": 3, # Handwriting, stamps

        # Medium visual dependency (2-3 images)
        "material_identification": 3,
        "condition_assessment": 2,
        "layout_analysis": 2,

        # Low visual dependency (0-1 images)
        "identifier_extraction": 1,  # IDs, codes
        "text_fields": 0,            # Pure text extraction

        # Default: 2 images for unspecified fields
    }

    def __init__(
        self,
        field_name: str,
        image_priority: bool = True,
        max_images: Optional[int] = None
    ):
        """
        Args:
            field_name: Field being extracted (determines image slot count)
            image_priority: Whether to include images at all
            max_images: Override default image slot count
        """
        self._field_name = field_name
        self._image_priority = image_priority
        self._max_images = max_images or self.VISUAL_FIELD_IMAGE_SLOTS.get(field_name, 2)

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        """Supplement text nodes with limited image nodes."""
        if not self._image_priority:
            # Text-only mode
            return [n for n in nodes if n.node.metadata.get('chunk_type') != 'image']

        # Separate text and image chunks
        text_nodes = [n for n in nodes if n.node.metadata.get('chunk_type') != 'image']
        image_nodes = [n for n in nodes if n.node.metadata.get('chunk_type') == 'image']

        # Sort images by score (most relevant first)
        image_nodes = sorted(image_nodes, key=lambda x: x.score or 0, reverse=True)

        # Select top-N images based on field
        selected_images = image_nodes[:self._max_images]

        # Mark images as supplementary
        for img_node in selected_images:
            img_node.node.metadata['is_supplement'] = True
            img_node.node.metadata['supplement_type'] = 'visual_evidence'

        # Return all text + limited images
        return text_nodes + selected_images
```

**Visual Field Examples by Domain**:

**Legal Contracts**:
```python
# High visual (4 images): Signature verification, seal authentication
# Medium visual (2-3 images): Handwritten amendments, exhibits with diagrams
# Low visual (0-1 images): Party names, contract dates (text extraction)
```

**Medical Records**:
```python
# High visual (4 images): X-rays, scans, charts/graphs, anatomical diagrams
# Medium visual (2-3 images): Lab results with tables, prescription images
# Low visual (0-1 images): Patient ID, diagnosis codes (text extraction)
```

**Financial Documents**:
```python
# High visual (4 images): Checks, signatures, stamps, handwritten notes
# Medium visual (2-3 images): Account statements with tables, transaction lists
# Low visual (0-1 images): Account numbers, routing numbers (text extraction)
```

**Configuration**:
```python
# Field config
{
    "field_name": "{FIELD_NAME}",
    "visual_analysis": {
        "enabled": true,
        "max_images": 4
    },
    "image_priority": true
}
```

## 4. FinalTopKSelector

**Purpose**: Ensure final context fits LLM limits and prioritizes text over images

**Implementation**:
```python
class FinalTopKSelector(BaseNodePostprocessor):
    """Final selection ensuring text priority and context size limits."""

    def __init__(self, final_top_k: int = 10):
        """
        Args:
            final_top_k: Maximum number of TEXT chunks (images unlimited within supplement limits)
        """
        self._final_top_k = final_top_k

    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None
    ) -> List[NodeWithScore]:
        """Select top-k text nodes, keep all images (already limited by ImageSupplement)."""
        # Separate by type
        text_nodes = [n for n in nodes if n.node.metadata.get('chunk_type') != 'image']
        image_nodes = [n for n in nodes if n.node.metadata.get('chunk_type') == 'image']

        # Sort text by score
        text_nodes = sorted(text_nodes, key=lambda x: x.score or 0, reverse=True)

        # Select top-k text
        selected_text = text_nodes[:self._final_top_k]

        # Keep all images (already limited by ImageSupplementPostprocessor)
        return selected_text + image_nodes
```

**Rationale**:
- **LLM context limits**: Claude has 200k token limit, but staying under 50k optimizes cost
- **Text priority**: Text extraction is more accurate than visual interpretation
- **Image supplementation**: Images provide evidence but shouldn't dominate context

**Final Context Composition**:
```
Top 10 text chunks (ranked by hybrid score + boosts)
  ├─ Chunk 1 (score: 100.85) [page boost applied]
  ├─ Chunk 2 (score: 0.92) [in both phases]
  ├─ Chunk 3 (score: 0.88)
  ├─ Adjacent chunk (score: 0.0) [context for Chunk 2]
  ├─ ...
  └─ Chunk 10 (score: 0.45)

+ Top 4 image chunks (visual evidence)
  ├─ Image 1 (score: 0.75) [relevant photo]
  ├─ Image 2 (score: 0.68) [diagram]
  ├─ Image 3 (score: 0.52) [supporting visual]
  └─ Image 4 (score: 0.48) [additional context]

Total: ~14 chunks → ~7000 tokens → sent to Claude for extraction
```

## Customizing for Your Domain

### Legal Contracts

**Post-processor configuration**:
```python
# Party names (signature page)
{
    "field_name": "party_name",
    "page_boost": [-1],  # Last page (0-indexed from end)
    "include_adjacent": true,  # Capture full signature block
    "visual_analysis": {"enabled": true, "max_images": 3},  # Signatures
    "final_top_k": 10
}

# Contract dates (cover page)
{
    "field_name": "contract_date",
    "page_boost": [0],  # First page
    "include_adjacent": false,  # Dates are compact
    "visual_analysis": {"enabled": false},  # Text-only
    "final_top_k": 5
}
```

### Medical Records

**Post-processor configuration**:
```python
# Diagnosis codes (summary page)
{
    "field_name": "diagnosis_code",
    "page_boost": [0, 1],  # Cover and summary pages
    "include_adjacent": true,  # Multi-line diagnoses
    "visual_analysis": {"enabled": false},  # Text-only
    "final_top_k": 15
}

# Treatment images (throughout document)
{
    "field_name": "treatment_plan",
    "page_boost": [],  # No specific page
    "include_adjacent": true,  # Full treatment descriptions
    "visual_analysis": {"enabled": true, "max_images": 4},  # Charts, scans
    "final_top_k": 10
}
```

### Financial Documents

**Post-processor configuration**:
```python
# Account numbers (header)
{
    "field_name": "account_number",
    "page_boost": [0],  # First page
    "include_adjacent": false,  # Compact identifier
    "visual_analysis": {"enabled": false},  # Text-only
    "final_top_k": 5
}

# Transaction details (throughout)
{
    "field_name": "transaction_summary",
    "page_boost": [],  # Distributed across pages
    "include_adjacent": true,  # Multi-line transactions
    "visual_analysis": {"enabled": true, "max_images": 2},  # Tables, graphs
    "final_top_k": 15
}
```

## Integration Example

**Complete post-processing pipeline**:
```python
from llama_index.core.postprocessor import BaseNodePostprocessor

def create_post_processing_pipeline(
    field_config: Dict,
    opensearch_client: OpenSearch,
    index_name: str,
    doc_id: str
) -> List[BaseNodePostprocessor]:
    """
    Create field-specific post-processing pipeline.

    Args:
        field_config: Field configuration from centralized config
        opensearch_client: OpenSearch client for adjacent chunk queries
        index_name: OpenSearch index name
        doc_id: Document ID

    Returns:
        List of post-processors in execution order
    """
    processors = []

    # 1. Page boost (if configured)
    if field_config.get('page_boost'):
        processors.append(
            PageBoostPostprocessor(
                boost_pages=field_config['page_boost'],
                boost_amount=field_config.get('page_boost_amount', 100.0)
            )
        )

    # 2. Adjacent chunk expansion (if enabled)
    if field_config.get('include_adjacent', True):
        processors.append(
            AdjacentChunkExpander(
                opensearch_client=opensearch_client,
                index_name=index_name,
                doc_id=doc_id,
                num_before=field_config.get('adjacent_chunks_before', 1),
                num_after=field_config.get('adjacent_chunks_after', 1)
            )
        )

    # 3. Image supplementation (if enabled)
    visual_config = field_config.get('visual_analysis', {})
    if visual_config.get('enabled', False):
        processors.append(
            ImageSupplementPostprocessor(
                field_name=field_config['field_name'],
                image_priority=field_config.get('image_priority', True),
                max_images=visual_config.get('max_images')
            )
        )

    # 4. Final top-k selector (always)
    processors.append(
        FinalTopKSelector(
            final_top_k=field_config.get('final_top_k', 10)
        )
    )

    return processors

# Usage
field_config = load_field_config("{FIELD_NAME}")
post_processors = create_post_processing_pipeline(
    field_config,
    opensearch_client,
    index_name=f"{INDEX_PREFIX}_{org}_{doc_id}",
    doc_id=doc_id
)

# Apply pipeline
nodes = retrieved_nodes
for processor in post_processors:
    nodes = processor.postprocess_nodes(nodes)
```

---

**Version**: 2.0
**Last Updated**: 2026-02-10
**Status**: Production-tested post-processing patterns
