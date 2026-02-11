# Chunking Strategies for Docling Documents

## HybridChunker Configuration

```python
from docling.chunking import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

# Use a tokenizer compatible with the target embedding model
hf_tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
hf_tokenizer.model_max_length = 100000  # Suppress truncation warnings

tokenizer = HuggingFaceTokenizer(
    tokenizer=hf_tokenizer,
    max_tokens=512,
)

chunker = HybridChunker(
    tokenizer=tokenizer,
    merge_peers=True,
)
```

**Tokenizer choice**: Use a tokenizer from the same family as the embedding model. The tokenizer is used for accurate token counting, not embedding generation. If the embedding model uses a different tokenizer, chunk sizes may not align with the model's context window.

## Why HybridChunker

Docling's `HybridChunker` combines two strategies:

1. **Structure-aware splitting** — Respects document hierarchy (headings, sections, paragraphs). Never splits in the middle of a table or across a heading boundary.
2. **Token-aware sizing** — Uses a real tokenizer (not character count) to ensure chunks fit within the embedding model's context window.

This is superior to naive character-based or recursive text splitting because it preserves the document's semantic structure while maintaining accurate token budgets.

## Token Limit Selection

| Token Limit | Embedding Quality | Retrieval Precision | Trade-off |
|------------|-------------------|---------------------|-----------|
| 128 | High (very focused) | Very precise | Too many chunks, loss of surrounding context |
| 256 | High | Precise | Good for short documents or fine-grained retrieval |
| **512** | **Balanced** | **Balanced** | **Best for mixed content (text + tables)** |
| 1024 | Lower (diluted) | Broader recall | Tables and text mixed together, less precise matching |

**512 tokens (~2000 characters)** is the general-purpose sweet spot for RAG retrieval. Large enough to contain a full paragraph or small table, small enough for precise semantic matching. Adjust based on specific embedding model context windows and retrieval requirements.

## Merge Peers

`merge_peers=True` consolidates small consecutive chunks that share the same heading hierarchy. Without this, sections with many short paragraphs produce excessive tiny chunks.

```
Without merge_peers:
  Chunk 1: "Section Title" → "The main building has 5 stories."  (12 tokens)
  Chunk 2: "Section Title" → "It was constructed in 1995."       (8 tokens)
  Chunk 3: "Section Title" → "The annex was added in 2001."      (9 tokens)

With merge_peers:
  Chunk 1: "Section Title" → "The main building has 5 stories.
            It was constructed in 1995. The annex was added in 2001."  (29 tokens)
```

Fewer, richer chunks improve both embedding quality and retrieval relevance.

## Two Chunking Pathways

### Pathway 1: File-Based (Double Conversion)

Used when only a file path is available and the document has not been converted yet:

```python
from llama_index.readers.docling import DoclingReader
from llama_index.node_parser.docling import DoclingNodeParser

reader = DoclingReader(export_type=DoclingReader.ExportType.JSON)
documents = reader.load_data(file_path=file_path)
nodes = node_parser.get_nodes_from_documents(documents)
```

**Drawback**: DoclingReader internally re-reads and re-converts the file. If the document was already converted, this doubles processing time.

### Pathway 2: Direct from DoclingDocument (Preferred)

Chunk directly from an already-converted DoclingDocument — avoids re-reading the file:

```python
doc = processor.convert_document(file_path)  # Convert once
chunk_iter = chunker.chunk(dl_doc=doc)        # Chunk from memory
nodes = [docchunk_to_textnode(c, i) for i, c in enumerate(chunk_iter)]
```

**Always prefer Pathway 2** when a DoclingDocument is already available. This is especially important in Ray workers where conversion and chunking happen in the same process.

## LlamaIndex Integration

To use Docling chunks with LlamaIndex:

```python
from llama_index.node_parser.docling import DoclingNodeParser

node_parser = DoclingNodeParser(chunker=chunker)

# Pathway 1: from file
documents = reader.load_data(file_path=file_path)
nodes = node_parser.get_nodes_from_documents(documents)

# Pathway 2 requires manual DocChunk → TextNode conversion (see below)
```

### Key Dependencies for LlamaIndex Integration

| Package | Version | Purpose |
|---------|---------|---------|
| `llama-index-readers-docling` | >=0.3.0 | DoclingReader for file-based loading |
| `llama-index-node-parser-docling` | >=0.4.0 | Structure-aware DoclingNodeParser |
| `llama-index-core` | >=0.11.0 | TextNode, Document base classes |

## DocChunk to TextNode Conversion

When using Pathway 2 (direct chunking), convert Docling DocChunk objects to LlamaIndex TextNode format:

```python
from llama_index.core.schema import TextNode

def docchunk_to_textnode(chunk, index: int) -> TextNode:
    """Convert a Docling DocChunk to LlamaIndex TextNode."""
    doc_items = []
    page_number = 0
    doc_items_label = ""
    headings = []

    if hasattr(chunk, "meta") and chunk.meta:
        meta = chunk.meta

        # Extract headings
        if hasattr(meta, "headings") and meta.headings:
            headings = list(meta.headings)

        # Extract doc_items with provenance
        if hasattr(meta, "doc_items") and meta.doc_items:
            for item in meta.doc_items:
                item_dict = {}

                if hasattr(item, "label"):
                    item_dict["label"] = str(item.label) if item.label else ""
                    if not doc_items_label:
                        doc_items_label = item_dict["label"]

                if hasattr(item, "prov") and item.prov:
                    prov_list = []
                    for prov in item.prov:
                        prov_dict = {}
                        if hasattr(prov, "page_no"):
                            prov_dict["page_no"] = prov.page_no
                            if page_number == 0:
                                page_number = prov.page_no
                        if hasattr(prov, "bbox"):
                            prov_dict["bbox"] = str(prov.bbox)
                        prov_list.append(prov_dict)
                    item_dict["prov"] = prov_list

                doc_items.append(item_dict)

    section_header = ", ".join(headings) if headings else ""

    return TextNode(
        text=chunk.text,
        metadata={
            "doc_items": doc_items,
            "headings": headings,
            "page": page_number,
            "section_header": section_header,
            "doc_items_label": doc_items_label,
        },
        id_=f"chunk_{index}",
    )
```

## Metadata Preservation

Every chunk carries its document provenance through the pipeline:

```python
metadata = {
    "page": 5,                                    # Source page number
    "section_header": "Section Title, Subsection", # Heading hierarchy
    "doc_items_label": "text",                     # Content type (text/table)
    "doc_items": [                                 # Provenance details
        {
            "label": "paragraph",
            "prov": [{"page_no": 5, "bbox": "..."}],
        }
    ],
    "headings": ["Section Title", "Subsection"],   # Full heading hierarchy
}
```

This metadata enables:
- **Page-level filtering** in retrieval queries
- **Section-aware re-ranking** during search
- **Source attribution** in LLM responses
- **Content-type-specific retrieval** (e.g., retrieve only tables about a topic)

## Chunk Statistics Logging

Track chunking quality during processing:

```python
def log_chunk_stats(nodes: list) -> None:
    if not nodes:
        logger.warning("No chunks generated")
        return

    text_lengths = [len(n.text) for n in nodes]
    avg_length = sum(text_lengths) / len(text_lengths)

    logger.info(
        f"Chunk stats: count={len(nodes)}, "
        f"avg_chars={avg_length:.0f}, "
        f"min={min(text_lengths)}, max={max(text_lengths)}"
    )
```
