---
name: hackett-doc-template
description: |
  **Hackett Group Document Template**: Creates professional, Hackett Group-branded .docx documents using the corporate template (navy branding, Garamond body, Arial Narrow headings, branded cover page, headers, and footers). Use this skill whenever the user wants to create ANY document that should follow the Hackett Group brand style — reports, proposals, assessments, action plans, memos, guides, whitepapers, analyses, executive summaries, or any other professional deliverable. Trigger on: Hackett Group, Hackett template, branded document, corporate report, professional document, any request for a .docx that should look like a Hackett Group deliverable. Also trigger when the user already has a document built with this template and wants to create a new one in the same style.
---

# Hackett Group Document Template

## Overview

This skill provides the complete Hackett Group corporate template specification for generating branded .docx documents. It covers the visual identity (colors, typography, layout), document architecture (cover page, headers/footers, body sections), and reusable component patterns (tables, cards, callout boxes, numbered lists).

The template is content-agnostic — it works for any document type. The user provides the content and structure; this skill ensures the output looks like a polished Hackett Group deliverable.

## When to Use

Use this skill whenever the user needs a document that follows the Hackett Group brand. Common examples include (but aren't limited to):

- Security audit reports and action plans
- Cloud migration assessments
- Executive summaries and board presentations
- Technical proposals and architecture reviews
- Compliance and governance reports
- Project status reports and post-mortems
- Cost optimization analyses
- Any document that needs the Hackett Group "look and feel"

## Document Architecture

Every Hackett Group document uses a **two-section layout** in the .docx:

### Section 1: Cover Page (no header/footer)

The cover page is its own Word section with headers and footers suppressed. It contains:

1. **Hackett Group logo** — large, left-aligned (~468×86 px). Use `assets/hackett_logo_cover.jpeg`.
2. **Navy horizontal line** — a thick (#003366) border acting as a visual separator, set as a bottom border on an empty paragraph (size 48, space 1).
3. **Title block** — centered, with the document title, subtitle/scope, and document type on separate lines. Use Arial Narrow, navy color, varying sizes (36pt title, 32pt subtitle, 28pt type).
4. **Metadata line** — centered summary stats or key identifiers (e.g., "Account 123456 | 17 Users | February 2026"). Calibri 11pt, #666666.
5. **Footer block** — "Prepared by" / "The Hackett Group" / "Date: [Month Year]" at the bottom. Garamond, navy, centered.

### Section 2: Body (with branded header and footer)

All content goes in this section. It carries:

- **Header**: Document title text in Arial Narrow 10pt bold navy (#003366), left-aligned. Hackett Group small logo right-aligned via a right tab stop at the content width. Use `assets/hackett_logo_small.png`.
- **Footer**: "© [Year] The Hackett Group, Inc. All rights reserved." left-aligned in Calibri 8pt #666666. Page number right-aligned.

## Brand Specification

### Colors

| Name | Hex | Usage |
|------|-----|-------|
| Navy | #003366 | Primary brand — Heading 1, Heading 3, table headers, cover line, card top borders |
| Text2 | #44546A | Heading 2 color |
| Table Border | #999999 | All table cell borders |
| White | #FFFFFF | Table header text |
| Gray BG | #F2F2F2 | Card header backgrounds, alternate row shading |
| Scope Box Fill | #E8EEF4 | Light blue fill for callout/scope boxes |

### Status/Risk Color Palette

Use these for any status indicators, risk levels, RAG ratings, or conditional formatting:

| Level | Background | Text Color | Use For |
|-------|-----------|------------|---------|
| Critical/Red | #FFC7CE | #9C0006 | Critical risk, blocked, failed |
| High/Orange | #FFE0B2 | #7A4100 | High risk, warning, at risk |
| Medium/Yellow | #FFF9C4 | #7A6500 | Medium risk, needs attention |
| Low/Blue | #D6E4F0 | #003366 | Low risk, informational |
| OK/Green | #C6EFCE | #006100 | OK, on track, completed, passed |

### Typography

| Element | Font | Size (half-pts) | Style |
|---------|------|-----------------|-------|
| Body text | Garamond | 22 (11pt) | Justified alignment |
| Heading 1 | Arial Narrow | 32 (16pt) | Bold, ALL CAPS, navy, characterSpacing: 20, page break before |
| Heading 2 | Calibri | 28 (14pt) | Bold, #44546A |
| Heading 3 | Calibri | 28 (14pt) | Bold, ALL CAPS, navy, characterSpacing: 20 |
| Table header cells | Calibri | 20 (10pt) | Bold, italic, white text on navy fill, centered |
| Table body cells | Calibri | 20 (10pt) | Normal, #333333 |
| Header text | Arial Narrow | 20 (10pt) | Bold, navy |
| Footer text | Calibri | 16 (8pt) | #666666 |

### Page Layout

- **Paper**: US Letter — 12240 × 15840 DXA
- **Margins**: 1080 DXA (0.75 inches) all sides
- **Content width**: 10080 DXA (12240 − 2 × 1080)

## Reusable Components

These are the building blocks that can be composed into any document. The reference template (`references/build_template.js`) contains working implementations of all of these.

### Tables

All tables share a consistent style:

- Borders: #999999 gray, size 4 (inner), size 8 (outer)
- Header row: #003366 navy fill, white bold italic text, centered
- Body cells: Calibri 10pt, #333333, left-aligned with cell margins (top/bottom 60, left/right 100)
- **Critical**: always set BOTH `columnWidths` on the Table AND individual `width` on each TableCell. The docx library requires both for correct rendering.

```javascript
function headerCell(text, width) {
  return new TableCell({
    borders, width: { size: width, type: WidthType.DXA },
    shading: { fill: "003366", type: ShadingType.CLEAR },
    margins: cellMargins,
    children: [new Paragraph({
      spacing: { before: 40, after: 40 },
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text, bold: true, italics: true, color: "FFFFFF", font: "Calibri", size: 20 })],
    })],
  });
}
```

### Cards (Entity Detail Blocks)

Used when presenting a per-item assessment (e.g., per-user, per-service, per-finding). Each card has:

1. **Header bar**: Single-cell table with gray fill (#F2F2F2), navy top border (size 12), entity name in Arial Narrow bold.
2. **Stats table**: Key metrics in a compact table (same table styling as above).
3. **Analysis paragraph**: Garamond body text explaining the data.

### Callout / Scope Boxes

For highlighting scope, key takeaways, or important notes:

- Single-cell table, no standard borders
- Left border: navy (#003366), size 24
- Fill: #E8EEF4 (light blue)
- Content: bullet points or metadata lines in Garamond

### Numbered & Bulleted Lists

Use the numbering config pattern with multiple references (steps1-5, bullets1-5) so different sections can have independent counters:

```javascript
function makeNumberingConfigs() {
  const refs = ["steps1","steps2","steps3","steps4","steps5","bullets1","bullets2","bullets3"];
  return refs.map(ref => ({
    reference: ref,
    levels: [{ level: 0,
      format: ref.startsWith("steps") ? LevelFormat.DECIMAL : LevelFormat.BULLET,
      text: ref.startsWith("steps") ? "%1." : "\u2022",
      alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 720, hanging: 360 } } },
    }],
  }));
}
```

### Status Cells

For any table cell that needs color-coded status:

```javascript
function statusCell(label, width) {
  const map = {
    CRITICAL: { fill: "FFC7CE", color: "9C0006" },
    HIGH:     { fill: "FFE0B2", color: "7A4100" },
    MEDIUM:   { fill: "FFF9C4", color: "7A6500" },
    LOW:      { fill: "D6E4F0", color: "003366" },
    OK:       { fill: "C6EFCE", color: "006100" },
  };
  const s = map[label] || { fill: "F2F2F2", color: "333333" };
  return cell(label, width, { bold: true, fill: s.fill, color: s.color });
}
```

## Implementation

Use **Node.js** with the `docx` library (docx-js v9.5.3+). Also read the `docx` skill's SKILL.md for general docx-js patterns and gotchas (ShadingType.CLEAR, ImageRun requires `type`, etc.).

### Key Code Pattern

```javascript
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: "Garamond", size: 22 },
        paragraph: { spacing: { before: 240, line: 280 }, alignment: AlignmentType.BOTH },
      },
    },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial Narrow", color: "003366", allCaps: true, characterSpacing: 20 },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0, pageBreakBefore: true },
      },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Calibri", color: "44546A" },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 1 },
      },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Calibri", color: "003366", allCaps: true, characterSpacing: 20 },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: { config: makeNumberingConfigs() },
  sections: [
    // Section 1: Cover page (no header/footer)
    { properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 } } },
      children: [ /* cover content */ ] },
    // Section 2: Body (with branded header + footer)
    { properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1080, bottom: 1080, left: 1080 } } },
      headers: { default: new Header({ children: [ /* header paragraph with logo */ ] }) },
      footers: { default: new Footer({ children: [ /* copyright + page number */ ] }) },
      children: [ /* all body content: headings, paragraphs, tables, cards */ ] },
  ],
});
```

### Logo Images

The skill bundles two logo files in `assets/`:

- `hackett_logo_small.png` — for the page header (right-aligned via tab stop). Load with `fs.readFileSync()`, use `ImageRun` with `type: "png"`.
- `hackett_logo_cover.jpeg` — for the cover page (left-aligned, ~468×86 px). Use `ImageRun` with `type: "jpg"`.

### Writing the Output

```javascript
const buffer = await Packer.toBuffer(doc);
fs.writeFileSync("output.docx", buffer);
```

## Workflow

1. Understand the document type and content the user needs
2. Plan the sections, headings, tables, and cards
3. Read this skill for the template specification
4. Read `references/build_template.js` for working code examples of every component
5. Write a build script that assembles the document using the patterns above
6. Generate the .docx
7. Validate the file (should be a valid ZIP with word/document.xml, styles.xml, etc.)
8. Present the file to the user

## Reference Template

The file `references/build_template.js` is a complete, working ~650-line Node.js script that generates a complex multi-section report (the IAM Security Audit Action Plan). It demonstrates every component pattern listed above — cover page, header/footer, tables, cards, callout boxes, numbered lists, status-colored cells, and more. Use it as your starting point for any new document.

When creating a new document, copy the reusable parts (constants, helpers, styles, numbering config, cover page pattern, header/footer) and replace the data and body content with whatever the user needs.
