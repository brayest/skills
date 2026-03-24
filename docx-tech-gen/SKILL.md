---
name: docx-tech-gen
description: This skill should be used when converting markdown technical documents to professionally styled Word (.docx) files with syntax-highlighted code blocks, styled tables, and Mermaid diagrams. Covers the full pipeline from markdown authoring through pandoc conversion, python-docx styling, and Pygments syntax highlighting.
---

# Technical Document Generation — Markdown to Styled DOCX

## Purpose

This skill provides a complete pipeline for producing professional Word documents from markdown source files. It handles font styling, table formatting with colored headers, syntax-highlighted code blocks, Mermaid diagram rendering, and page layout — all automated via Python scripting.

## When to Use This Skill

- Converting a markdown file to a polished `.docx` for sharing with stakeholders
- Creating RFC documents, technical proposals, or architecture documents as Word files
- Any time a user asks to "make a docx", "convert to Word", or "export to docx"
- When the user wants professional formatting on a technical document with code blocks and tables
- When the user wants to improve the styling of an existing `.docx` file

## Requirements

- **pandoc** (installed at `/opt/homebrew/bin/pandoc`) — markdown to docx conversion
- **python-docx** (`/opt/homebrew/bin/python3` with `python-docx 1.2.0`) — direct docx manipulation
- **pygments** (`/opt/homebrew/bin/python3` with `pygments`) — syntax highlighting
- **mermaid-cli** (via `npx -y @mermaid-js/mermaid-cli`) — diagram rendering (optional, only if markdown contains mermaid)

## Pipeline — Three Steps

### Step 1: Mermaid Diagrams (if present)

If the markdown contains mermaid code blocks, render them to PNG before conversion:

```bash
# Create diagrams directory next to the markdown file
mkdir -p diagrams

# Write .mmd files from mermaid blocks, then render
npx -y @mermaid-js/mermaid-cli -i diagrams/my-diagram.mmd -o diagrams/my-diagram.png -w 1400 -b white
```

Replace mermaid code blocks in the markdown with image references:
```markdown
![Diagram Title](diagrams/my-diagram.png)
```

### Step 2: Pandoc Conversion

Convert markdown to docx. Do NOT use `--toc` unless explicitly requested — it adds a separate TOC page before the content.

```bash
pandoc input.md -o output.docx --from markdown --to docx --syntax-highlighting=tango --resource-path=.
```

Key flags:
- `--syntax-highlighting=tango` — adds basic highlighting (will be enhanced in Step 3)
- `--resource-path=.` — resolves image paths relative to current directory

### Step 3: Python Styling Script

Run a Python script using `/opt/homebrew/bin/python3` to apply professional formatting directly to the docx. The script does three things: paragraph/font styling, table styling, and syntax highlighting.

## Styling Specifications

### Fonts and Sizes

| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Heading 1 | Calibri | 18pt | Bold | Navy `#1B2A4A` |
| Heading 2 | Calibri | 14pt | Bold | Navy `#1B2A4A` |
| Heading 3 | Calibri | 11pt | Bold | Dark gray `#333333` |
| Body Text | Calibri | 10pt | Normal | Dark gray `#333333` |
| First Paragraph | Calibri | 10pt | Normal | Dark gray `#333333` |
| Normal | Calibri | 10pt | Normal | Dark gray `#333333` |
| Source Code | Consolas | 8pt | Normal | Per-token (syntax highlighted) |
| Compact | Consolas | 8pt | Normal | Dark gray `#333333` |
| Table cells | Calibri | 9pt | Normal (bold for headers) | Dark gray / White for headers |

### Spacing

- Line spacing: 1.15 for body text
- Space after body paragraphs: 6pt
- Space after headings: H1=8pt, H2=6pt, H3=4pt
- Space before headings: H1=18pt, H2=14pt, H3=10pt

### Page Setup

- Margins: 0.75 inches all sides
- This gives more horizontal room for tables and code blocks

### Table Styling

- **Header row**: Background `#2E5090` (dark blue), white bold text
- **Odd data rows** (row 2, 4, 6...): White background
- **Even data rows** (row 3, 5, 7...): Background `#F2F2F2` (light gray)
- **Borders**: All cells have thin `#BFBFBF` (light gray) borders
- **Cell padding**: 40 twips top/bottom, 80 twips left/right
- **Cell paragraph spacing**: 1pt before/after

### Code Block Syntax Highlighting

Use Pygments to tokenize code blocks (paragraphs with "Source Code" style). Skip "Compact" style — those are bullet lists, not code.

**Language auto-detection heuristic:**

| Pattern | Language | Lexer |
|---------|----------|-------|
| `resource "`, `variable "`, `module "`, `set {` | HCL/Terraform | `get_lexer_by_name('hcl')` |
| `Route::`, `'=>`, `function (`, `->`, `$variable` | PHP | `get_lexer_by_name('php', startinline=True)` |
| `import {`, `export default`, `defineNuxtPlugin`, `defineEventHandler` | TypeScript | `get_lexer_by_name('typescript')` |
| `helm `, `npm `, `docker `, `kubectl ` | Bash | `get_lexer_by_name('bash')` |
| `key: value` patterns with indentation, no `=>` | YAML | `get_lexer_by_name('yaml')` |
| None of the above | Plain text | `TextLexer()` |

**Token color map (VS Code light-theme inspired):**

| Token Type | Color | Hex |
|------------|-------|-----|
| Keywords | Blue (bold) | `#569CD6` |
| Keyword.Type, Name.Builtin, Name.Class | Teal | `#4EC9B0` |
| Name.Function, Name.Decorator | Dark yellow | `#795E26` |
| Name.Tag | Blue | `#569CD6` |
| Name.Attribute | Dark cyan | `#2B91AF` |
| Name.Variable | Dark blue | `#001080` |
| String (all variants) | Dark red | `#A31115` |
| Comment (all variants) | Green | `#6A9955` |
| Number | Green | `#098858` |
| Operator, Punctuation | Gray | `#606060` |
| Default | Near-black | `#1E1E1E` |

**Code block background**: `#F5F5F5` (light gray paragraph shading)

## Complete Python Styling Script

This is the reference script. Adapt paths as needed for each document:

```python
#!/usr/bin/env /opt/homebrew/bin/python3
"""
Style a pandoc-generated .docx with professional formatting.
Usage: python3 style_docx.py input.docx
"""
import re
import sys
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from pygments import lex
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import Token, Keyword, Name, String, Comment, Operator, Punctuation, Number, Literal

DOCX_PATH = sys.argv[1] if len(sys.argv) > 1 else 'output.docx'
doc = Document(DOCX_PATH)

# === COLORS ===
NAVY = RGBColor(0x1B, 0x2A, 0x4A)
DARK_GRAY = RGBColor(0x33, 0x33, 0x33)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
HEADER_BG = "2E5090"
ALT_ROW_BG = "F2F2F2"
BORDER_COLOR = "BFBFBF"
CODE_BG = "F5F5F5"
DEFAULT_CODE_COLOR = RGBColor(0x1E, 0x1E, 0x1E)

TOKEN_COLORS = {
    Keyword:              RGBColor(0x56, 0x9C, 0xD6),
    Keyword.Constant:     RGBColor(0x56, 0x9C, 0xD6),
    Keyword.Declaration:  RGBColor(0x56, 0x9C, 0xD6),
    Keyword.Namespace:    RGBColor(0x56, 0x9C, 0xD6),
    Keyword.Type:         RGBColor(0x4E, 0xC9, 0xB0),
    Name.Builtin:         RGBColor(0x4E, 0xC9, 0xB0),
    Name.Function:        RGBColor(0x79, 0x5E, 0x26),
    Name.Class:           RGBColor(0x4E, 0xC9, 0xB0),
    Name.Decorator:       RGBColor(0x79, 0x5E, 0x26),
    Name.Tag:             RGBColor(0x56, 0x9C, 0xD6),
    Name.Attribute:       RGBColor(0x2B, 0x91, 0xAF),
    Name.Variable:        RGBColor(0x00, 0x10, 0x80),
    String:               RGBColor(0xA3, 0x11, 0x15),
    String.Double:        RGBColor(0xA3, 0x11, 0x15),
    String.Single:        RGBColor(0xA3, 0x11, 0x15),
    String.Interpol:      RGBColor(0xA3, 0x11, 0x15),
    Comment:              RGBColor(0x6A, 0x99, 0x55),
    Comment.Single:       RGBColor(0x6A, 0x99, 0x55),
    Comment.Multiline:    RGBColor(0x6A, 0x99, 0x55),
    Comment.Preproc:      RGBColor(0x6A, 0x99, 0x55),
    Number:               RGBColor(0x09, 0x88, 0x58),
    Number.Integer:       RGBColor(0x09, 0x88, 0x58),
    Operator:             RGBColor(0x60, 0x60, 0x60),
    Punctuation:          RGBColor(0x60, 0x60, 0x60),
    Literal:              RGBColor(0xA3, 0x11, 0x15),
    Literal.String:       RGBColor(0xA3, 0x11, 0x15),
}

def get_token_color(token_type):
    while token_type:
        if token_type in TOKEN_COLORS:
            return TOKEN_COLORS[token_type]
        token_type = token_type.parent
    return DEFAULT_CODE_COLOR

def detect_lexer(text):
    if re.search(r'(resource|variable|module|data)\s+"', text) or re.search(r'^\s*set\s*\{', text, re.M):
        return get_lexer_by_name('hcl')
    if re.search(r"(Route::|'=>|function\s*\(|->|\$\w+)", text):
        return get_lexer_by_name('php', startinline=True)
    if re.search(r'(import\s*\{|export\s+default|defineNuxtPlugin|defineEventHandler|datadogRum)', text):
        return get_lexer_by_name('typescript')
    if re.search(r'^(helm |npm |docker |kubectl |pip )', text):
        return get_lexer_by_name('bash')
    if re.search(r'^\s*\w[\w.-]*:\s', text, re.M) and '=>' not in text:
        return get_lexer_by_name('yaml')
    return TextLexer()

def set_cell_shading(cell, color_hex):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}" w:val="clear"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def set_cell_borders(cell, color="BFBFBF", sz="4"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="{sz}" w:color="{color}" w:space="0"/>'
        f'  <w:left w:val="single" w:sz="{sz}" w:color="{color}" w:space="0"/>'
        f'  <w:bottom w:val="single" w:sz="{sz}" w:color="{color}" w:space="0"/>'
        f'  <w:right w:val="single" w:sz="{sz}" w:color="{color}" w:space="0"/>'
        f'</w:tcBorders>'
    )
    existing = tcPr.find(qn('w:tcBorders'))
    if existing is not None:
        tcPr.remove(existing)
    tcPr.append(borders)

def set_paragraph_shading(paragraph, color_hex):
    pPr = paragraph._p.get_or_add_pPr()
    existing = pPr.find(qn('w:shd'))
    if existing is not None:
        pPr.remove(existing)
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}" w:val="clear"/>')
    pPr.append(shd)

# === 1. PAGE SETUP ===
for section in doc.sections:
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)

# === 2. PARAGRAPH STYLING ===
style_map = {
    'Heading 1':       {'font': 'Calibri', 'size': Pt(18), 'bold': True,  'color': NAVY,      'space_before': Pt(18), 'space_after': Pt(8)},
    'Heading 2':       {'font': 'Calibri', 'size': Pt(14), 'bold': True,  'color': NAVY,      'space_before': Pt(14), 'space_after': Pt(6)},
    'Heading 3':       {'font': 'Calibri', 'size': Pt(11), 'bold': True,  'color': DARK_GRAY, 'space_before': Pt(10), 'space_after': Pt(4)},
    'Body Text':       {'font': 'Calibri', 'size': Pt(10), 'bold': False, 'color': DARK_GRAY, 'space_before': Pt(0),  'space_after': Pt(6)},
    'First Paragraph': {'font': 'Calibri', 'size': Pt(10), 'bold': False, 'color': DARK_GRAY, 'space_before': Pt(0),  'space_after': Pt(6)},
    'Normal':          {'font': 'Calibri', 'size': Pt(10), 'bold': False, 'color': DARK_GRAY, 'space_before': Pt(0),  'space_after': Pt(4)},
    'Compact':         {'font': 'Consolas','size': Pt(8),  'bold': False, 'color': DARK_GRAY, 'space_before': Pt(0),  'space_after': Pt(2)},
    'Source Code':     {'font': 'Consolas','size': Pt(8),  'bold': False, 'color': DARK_GRAY, 'space_before': Pt(0),  'space_after': Pt(2)},
}

for para in doc.paragraphs:
    sname = para.style.name
    if sname in style_map:
        cfg = style_map[sname]
        pf = para.paragraph_format
        pf.space_before = cfg['space_before']
        pf.space_after = cfg['space_after']
        if sname not in ('Source Code', 'Compact'):
            pf.line_spacing = 1.15
        for run in para.runs:
            run.font.name = cfg['font']
            run.font.size = cfg['size']
            run.font.color.rgb = cfg['color']
            if cfg['bold'] and sname.startswith('Heading'):
                run.font.bold = True

# === 3. TABLE STYLING ===
for table in doc.tables:
    table.autofit = True
    for row_idx, row in enumerate(table.rows):
        for cell in row.cells:
            set_cell_borders(cell, BORDER_COLOR)
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            margins = parse_xml(
                f'<w:tcMar {nsdecls("w")}>'
                f'  <w:top w:w="40" w:type="dxa"/>'
                f'  <w:left w:w="80" w:type="dxa"/>'
                f'  <w:bottom w:w="40" w:type="dxa"/>'
                f'  <w:right w:w="80" w:type="dxa"/>'
                f'</w:tcMar>'
            )
            existing_mar = tcPr.find(qn('w:tcMar'))
            if existing_mar is not None:
                tcPr.remove(existing_mar)
            tcPr.append(margins)
            for para in cell.paragraphs:
                para.paragraph_format.space_before = Pt(1)
                para.paragraph_format.space_after = Pt(1)
                for run in para.runs:
                    run.font.name = 'Calibri'
                    run.font.size = Pt(9)
                    if row_idx == 0:
                        run.font.bold = True
                        run.font.color.rgb = WHITE
                    else:
                        run.font.color.rgb = DARK_GRAY
            if row_idx == 0:
                set_cell_shading(cell, HEADER_BG)
            elif row_idx % 2 == 0:
                set_cell_shading(cell, ALT_ROW_BG)

# === 4. SYNTAX HIGHLIGHTING ===
for para in doc.paragraphs:
    if para.style.name != 'Source Code':
        continue
    text = para.text
    if not text.strip():
        continue
    lexer = detect_lexer(text)
    tokens = list(lex(text, lexer))
    for run in para.runs:
        run._r.getparent().remove(run._r)
    for token_type, token_value in tokens:
        if not token_value:
            continue
        run = para.add_run(token_value)
        run.font.name = 'Consolas'
        run.font.size = Pt(8)
        run.font.color.rgb = get_token_color(token_type)
        if token_type in (Keyword, Keyword.Declaration, Keyword.Namespace, Keyword.Constant):
            run.font.bold = True
    set_paragraph_shading(para, CODE_BG)

# === SAVE ===
doc.save(DOCX_PATH)
print(f"Styled: {DOCX_PATH}")
```

## Markdown Authoring Tips for Best DOCX Output

### Tables
- Keep tables narrow (2-3 columns max) — wide tables get squished in docx
- If a comparison table has 5+ columns, split into multiple 2-column tables (one per category)
- Use `|:---|:---|` for left-alignment

### Code Blocks
- Always specify the language hint in fenced blocks (` ```hcl `, ` ```php `, ` ```yaml `, ` ```typescript `, ` ```bash `)
- Keep code blocks short (under 30 lines) — long blocks don't paginate well in Word

### Diagrams
- Use Mermaid for architecture diagrams — they render well as PNG
- For `graph LR` (left-to-right), use `<br/>` for multi-line node labels
- Set `-w 1400 -b white` when rendering with mmdc for consistent sizing
- Only embed 1-2 diagrams per document — too many PNGs bloat file size

### Structure
- Use `---` (horizontal rules) between major sections — pandoc converts these to section breaks
- Don't use `--toc` unless the user asks for it — it adds a separate page before content
- H1 is the document title, H2 are major sections, H3 are subsections

## Example Usage

When a user says "convert this markdown to a styled docx":

1. Check for Mermaid blocks → render to PNG if present
2. Run pandoc: `pandoc input.md -o output.docx --from markdown --to docx --syntax-highlighting=tango --resource-path=.`
3. Run the Python styling script on the output docx
4. Verify by checking file size and paragraph/table count
