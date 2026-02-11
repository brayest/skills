# Docling Configuration & Content Extraction

## DocumentConverter Setup

```python
from docling.document_converter import (
    DocumentConverter,
    PdfFormatOption,
    WordFormatOption,
    PowerpointFormatOption,
)
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions

# RapidOCR with GPU acceleration
ocr_options = RapidOcrOptions(
    force_full_page_ocr=True,   # Critical for vector-rendered tables
    backend="torch"             # CUDA via PyTorch
)

pdf_options = PdfPipelineOptions(
    do_ocr=True,
    do_table_structure=True,
    generate_picture_images=True,
    images_scale=2.0,           # 144 DPI (2x default 72)
    ocr_options=ocr_options,
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
        InputFormat.DOCX: WordFormatOption(),
        InputFormat.PPTX: PowerpointFormatOption(),
    }
)
```

## Configuration Decisions

| Option | Value | Rationale |
|--------|-------|-----------|
| `force_full_page_ocr` | `True` | Tables rendered as vector graphics have no extractable text layer. Without this, OCR skips pages that appear to have text but the tables are empty vectors. |
| `backend` | `"torch"` | Enables CUDA GPU acceleration for RapidOCR inference. Falls back to CPU automatically if no GPU is available. |
| `images_scale` | `2.0` | 144 DPI instead of default 72 DPI. Higher resolution improves OCR accuracy on small text and table cells. Trade-off: 4x memory per page image. |
| `generate_picture_images` | `True` | Extracts embedded images as PIL objects for downstream processing (VLM description, storage). |
| `do_table_structure` | `True` | Enables the table detection model that identifies rows, columns, and cell boundaries. |

## Single Conversion, Multiple Outputs

The most important optimization: **convert the document once, extract everything from the result**.

```python
# Convert ONCE
doc = converter.convert(file_path).document

# Extract multiple content types from the same DoclingDocument
text_chunks = chunker.chunk(dl_doc=doc)          # Hierarchical text chunks
tables = doc.tables                               # Structured table objects
images = [p.get_image(doc) for p in doc.pictures] # PIL Image objects
markdown = doc.export_to_markdown()               # Full markdown export
```

Never re-convert or re-read the file for different content types. Docling conversion is the most expensive operation (OCR, layout analysis, table detection).

## Fail-Fast Conversion

```python
from pathlib import Path

def convert_document(file_path: str):
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    result = converter.convert(str(path))

    if result.document is None:
        raise ValueError(f"Conversion failed for: {file_path}")

    return result.document
```

No fallbacks, no silent defaults. If Docling cannot convert a document, the error must surface immediately.

## Table Extraction

Export each table to markdown, preserving structure metadata:

```python
def extract_tables(doc) -> list[dict]:
    tables = []
    if not hasattr(doc, "tables") or not doc.tables:
        return tables

    for idx, table_item in enumerate(doc.tables):
        table_markdown = table_item.export_to_markdown(doc)

        # Skip tables with empty text (embedding models require non-empty input)
        if not table_markdown or not table_markdown.strip():
            continue

        page_number = 0
        if hasattr(table_item, "prov") and table_item.prov:
            page_number = table_item.prov[0].page_no

        caption = ""
        if hasattr(table_item, "caption") and table_item.caption:
            caption = str(table_item.caption)

        num_rows = getattr(table_item.data, "num_rows", 0) if table_item.data else 0
        num_cols = getattr(table_item.data, "num_cols", 0) if table_item.data else 0

        tables.append({
            "text": table_markdown,
            "metadata": {
                "page": page_number,
                "content_type": "table",
                "section_header": caption,
                "table_index": idx,
                "num_rows": num_rows,
                "num_cols": num_cols,
            },
        })

    return tables
```

## Image Extraction

Extract images as PIL objects, convert to PNG bytes for transport and storage:

```python
import io

def extract_images(doc) -> list[dict]:
    images = []
    if not hasattr(doc, "pictures") or not doc.pictures:
        return images

    for idx, picture in enumerate(doc.pictures):
        try:
            # Docling API requires passing the document to get_image()
            pil_image = picture.get_image(doc)
            if pil_image is None:
                continue

            # Get provenance (page and position)
            page_number = 0
            bbox = None
            if hasattr(picture, "prov") and picture.prov:
                prov = picture.prov[0]
                page_number = getattr(prov, "page_no", 0)
                if hasattr(prov, "bbox"):
                    bbox_obj = prov.bbox
                    bbox = {
                        "l": getattr(bbox_obj, "l", 0),
                        "t": getattr(bbox_obj, "t", 0),
                        "r": getattr(bbox_obj, "r", 0),
                        "b": getattr(bbox_obj, "b", 0),
                    }

            # Convert PIL Image to PNG bytes (serialization-safe)
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

            caption = str(picture.caption) if hasattr(picture, "caption") and picture.caption else ""

            images.append({
                "bytes": image_bytes,
                "format": "png",
                "page": page_number,
                "bbox": bbox,
                "width": pil_image.width,
                "height": pil_image.height,
                "caption": caption,
            })

        except Exception as e:
            # Images are supplementary — log warning, continue with remaining
            logger.warning(f"Failed to extract image {idx}: {e}")

    return images
```

Image extraction uses a resilience exception to the fail-fast rule: images are supplementary to text/table extraction. Losing one image should not discard an entire document's text chunks.

## Empty Content Filtering

Embedding models typically require non-empty input (e.g., `minLength: 1`). Filter empty content before sending to embedding services:

```python
chunks = [c for c in chunks if c.get("text") and c["text"].strip()]
tables = [t for t in tables if t.get("text") and t["text"].strip()]
```

## Supported Formats

| Format | Processing |
|--------|-----------|
| **PDF** | Text extraction, OCR for scanned pages, table detection, image extraction |
| **DOCX** | Text + formatting, tables, images via `python-docx` |
| **PPTX** | Slide content, text, tables via `python-pptx` |

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `docling` | >=2.64.0 | Core document extraction engine |
| `docling-core` | >=2.9.0 | Data models (DoclingDocument, DocChunk) |
| `onnxruntime-gpu` | ==1.22.0 | GPU OCR inference (pin: 1.23.x has GPU discovery bug) |
| `python-docx` | >=1.1.0 | DOCX format support |
| `python-pptx` | >=0.6.23 | PPTX format support |
| `Pillow` | >=10.0.0 | Image processing |
