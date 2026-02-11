# Evaluation Framework

## 1. Overview

A production evaluation framework for LLM applications covers three dimensions:

```
┌─────────────────────────────────────────────────┐
│              Evaluation Dimensions               │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │Retrieval │  │Extraction│  │ Aggregation   │  │
│  │ Quality  │  │ Quality  │  │ Quality       │  │
│  │          │  │          │  │               │  │
│  │ Did we   │  │ Did the  │  │ Do multiple   │  │
│  │ find the │  │ LLM      │  │ sources       │  │
│  │ right    │  │ extract  │  │ agree?        │  │
│  │ context? │  │ correctly│  │               │  │
│  │          │  │ & with   │  │               │  │
│  │ 5 metrics│  │ grounding│  │ 2 metrics     │  │
│  │          │  │ 2 metrics│  │               │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────┘
```

### Design Principles

- **Zero-cost first** — 8 of 9 metrics use only local computation (no LLM calls)
- **Conditional escalation** — Expensive LLM-based evaluation only triggers when cheap metrics flag concern
- **Span-attached** — Every evaluation is attached to the active trace span for correlation
- **Non-blocking** — Evaluation failures never affect business logic

## 2. Dimension 1: Retrieval Quality

### `context_relevance` (score: 0.0–1.0)

**What it measures:** Overall quality of retrieved context — are the chunks relevant to the query?

**Calculation:**
```python
def _calculate_context_relevance_score(self, chunks: list[dict]) -> float:
    """Weighted combination of retrieval quality signals."""
    # Factor 1: Intersection ratio (chunks found by BOTH BM25 and KNN)
    # High intersection = both lexical and semantic search agree
    bm25_ids = {c['chunk_id'] for c in chunks if c.get('retrieval_method') == 'bm25'}
    knn_ids = {c['chunk_id'] for c in chunks if c.get('retrieval_method') == 'knn'}
    intersection = bm25_ids & knn_ids
    intersection_ratio = len(intersection) / max(len(bm25_ids | knn_ids), 1)

    # Factor 2: Average relevance score (normalized)
    scores = [c.get('score', 0) for c in chunks if c.get('score')]
    avg_score = sum(scores) / max(len(scores), 1)

    # Factor 3: Diversity — unique pages represented
    pages = {c.get('page') for c in chunks if c.get('page')}
    diversity = min(len(pages) / 5, 1.0)  # Normalize: 5+ pages = 1.0

    # Weighted combination
    return (intersection_ratio * 0.4) + (avg_score * 0.5) + (diversity * 0.1)
```

**Thresholds:**
- `> 0.7` — Good: retrieval is capturing relevant context
- `0.4–0.7` — Acceptable: may need tuning (thresholds, chunk size, embedding model)
- `< 0.4` — Investigate: queries may be malformed, index may be stale, or embedding quality is poor

**Cost:** Zero (local computation only)

---

### `context_precision` (score: 0.0–1.0)

**What it measures:** Are the most useful chunks ranked highest? Measures whether contributing chunks (those that actually led to extractions) appear in the top-K positions.

**Calculation:**
```python
def _calculate_context_precision(self, extractions: list[dict]) -> dict:
    """Precision at K — how many contributing chunks are in top positions."""
    contributing_chunks = {e['chunk_number'] for e in extractions if e.get('chunk_number')}
    top_k = 10

    # How many of the top-K chunks actually contributed?
    contributing_in_top_k = len({c for c in contributing_chunks if c <= top_k})
    precision_at_k = contributing_in_top_k / min(top_k, len(contributing_chunks)) if contributing_chunks else 0

    # Average rank of contributing chunks
    ranks = [e['chunk_number'] for e in extractions if e.get('chunk_number')]
    avg_rank = sum(ranks) / len(ranks) if ranks else 0

    return {
        'precision_at_10': round(precision_at_k, 3),
        'avg_rank': round(avg_rank, 1),
        'contributing_chunks': len(contributing_chunks)
    }
```

**Why it matters:** If contributing chunks are ranked low (e.g., positions 15–20), reducing the retrieval limit could accidentally exclude them. High precision means the ranking is working correctly.

**Cost:** Zero

---

### `context_recall_heuristic` (score: 0.0–1.0)

**What it measures:** Fast estimate of whether retrieval captured all relevant information. Runs on every request as the first tier of the hybrid recall strategy.

**Calculation:**
```python
def _calculate_context_recall(self, extractions: list[dict], chunks: list[dict]) -> dict:
    """Heuristic recall — zero-cost, always runs."""
    contributing_count = len({e['chunk_number'] for e in extractions if e.get('chunk_number')})
    max_available = len(chunks)

    recall_score = contributing_count / max(max_available, 1)

    # Penalty: if retrieval hit the configured limit, we may have missed chunks
    hit_bm25_limit = len([c for c in chunks if c.get('retrieval_method') == 'bm25']) >= BM25_LIMIT
    hit_knn_limit = len([c for c in chunks if c.get('retrieval_method') == 'knn']) >= KNN_LIMIT

    hit_limit = hit_bm25_limit or hit_knn_limit
    high_filtering = (max_available / max(TOTAL_RETRIEVED_BEFORE_FILTER, 1)) < 0.5

    if hit_limit:
        recall_score *= 0.7   # 30% penalty — retrieval may be truncated
    elif high_filtering:
        recall_score *= 0.85  # 15% penalty — aggressive filtering

    return {
        'recall_score': round(recall_score, 3),
        'contributing_count': contributing_count,
        'hit_limit_warning': hit_limit,
        'high_filtering_warning': high_filtering
    }
```

**Cost:** Zero — this is why it always runs

---

### `context_recall_llm` (score: 0.0–1.0)

**What it measures:** LLM-validated recall — asks an LLM whether the retrieved context contains all information needed to answer the query. This is the expensive second tier.

**When it triggers:** Only when `context_recall_heuristic < 0.7` or when the heuristic flags a retrieval limit hit.

```python
# Hybrid recall strategy — conditional escalation
if context_recall_heuristic['recall_score'] < 0.7 or context_recall_heuristic['hit_limit_warning']:
    logger.debug(f"Heuristic recall low ({context_recall_heuristic['recall_score']}), running LLM validation")
    context_recall_llm = self.evidence_validator.evaluate_context_recall_with_llm(
        field_name=field_name,
        extracted_value=final_value,
        retrieved_chunks=valid_chunks[:10],  # Limit for prompt size
        field_config=field_config
    )
```

**Cost:** One LLM call (the only evaluation that has LLM cost)

**Production impact:** In practice, ~80% of requests have heuristic >= 0.7, so the LLM evaluation runs on ~20% of requests. This reduces evaluation cost by 80% compared to running LLM validation on every request.

---

### `recall_warning` (categorical)

**Values:** `HIT_RETRIEVAL_LIMIT` | `HIGH_THRESHOLD_FILTERING`

**What it measures:** System health signal — not a quality score but a flag that retrieval may be incomplete.

- `HIT_RETRIEVAL_LIMIT` — BM25 or KNN hit the configured maximum result count. There may be more relevant chunks beyond the limit.
- `HIGH_THRESHOLD_FILTERING` — More than 50% of retrieved chunks were filtered out by score thresholds. The thresholds may be too aggressive.

**Cost:** Zero

---

## 3. Dimension 2: Extraction Quality

### `aggregated_confidence` (score: 0.0–1.0)

**What it measures:** Overall confidence in the extracted value, combining signals from the LLM's self-reported confidence and aggregation analysis.

**Sources:**
- LLM self-reported confidence (from structured output)
- Aggregation strategy analysis (when multiple values are found)
- Value format validation (does the output match expected format?)

**Mapping from categorical confidence:**
```python
confidence_map = {'HIGH': 0.90, 'MEDIUM': 0.75, 'LOW': 0.50}
overall_confidence = confidence_map.get(aggregation_confidence, 0.70)

# For single-value cases, use the evidence confidence directly
if len(evidence_sources) == 1 and evidence_sources[0].get('confidence'):
    overall_confidence = float(evidence_sources[0]['confidence'])
```

**Cost:** Zero (derived from existing extraction results)

---

### `semantic_validation` (categorical)

**Values:** `pass` | `fail` | `skipped`

**What it measures:** Is the extracted value actually grounded in the evidence text? This catches hallucinated extractions where the LLM produces a plausible-looking value that doesn't appear in the source material.

**Logic:**
```python
total_validated = validation_summary['passed'] + validation_summary['failed']
if total_validated > 0:
    pass_rate = validation_summary['passed'] / total_validated
    overall_validation = "pass" if pass_rate >= 0.5 else "fail"
else:
    overall_validation = "skipped"  # No evidence available for validation
```

**When `skipped`:** No evidence passages were available for validation (e.g., the LLM returned a value without citing specific chunks).

**Cost:** Zero (compares extracted value against provided evidence text)

---

## 4. Dimension 3: Aggregation Quality

These metrics apply when multiple values are extracted for the same field from different document sections.

### `multi_source_agreement` (score: 0.0–1.0)

**What it measures:** When extracting from multiple sources/chunks, do they produce the same value?

**Calculation:**
```python
def _evaluate_multi_source_agreement(self, field_name: str, results: list[dict]) -> dict:
    """Calculate agreement across multiple extraction results."""
    values = [r['value'] for r in results if r.get('value')]
    unique_values = set(values)

    if len(values) <= 1:
        return {'agreement_percentage': 1.0, 'pattern': 'unanimous', 'unique_values': len(unique_values)}

    # Most common value
    from collections import Counter
    value_counts = Counter(values)
    most_common_count = value_counts.most_common(1)[0][1]
    agreement_percentage = most_common_count / len(values)

    # Categorize
    if agreement_percentage > 0.95:
        pattern = "unanimous"
    elif agreement_percentage > 0.7:
        pattern = "majority"
    elif agreement_percentage > 0.4:
        pattern = "mixed"
    else:
        pattern = "conflicting"

    return {
        'agreement_percentage': round(agreement_percentage, 3),
        'pattern': pattern,
        'unique_values': len(unique_values)
    }
```

**Cost:** Zero

---

### `agreement_pattern` (categorical)

**Values:** `unanimous` | `majority` | `mixed` | `conflicting`

| Pattern | Agreement % | Meaning |
|---------|------------|---------|
| `unanimous` | > 95% | All sources agree — high confidence in the value |
| `majority` | > 70% | Most sources agree — the value is likely correct |
| `mixed` | > 40% | Some agreement — may need human review |
| `conflicting` | <= 40% | No consensus — the field may be ambiguous or the document contains contradictory information |

**Cost:** Zero

---

## 5. Evaluation Submission Pattern

All evaluations follow the same guard pattern:

```python
try:
    if LLMObs and is_observability_enabled():
        span = LLMObs.export_span()  # Gets the current active span
        if span:
            LLMObs.submit_evaluation(
                span=span,
                label="context_relevance",
                metric_type="score",       # "score" or "categorical"
                value=0.85                 # float for score, string for categorical
            )
            logger.debug(f"Evaluation submitted: context_relevance=0.85")
except Exception:
    pass  # Observability must NEVER crash business logic
```

### Two Metric Types

**Score** — a numeric value (0.0–1.0):
```python
LLMObs.submit_evaluation(span=span, label="context_relevance", metric_type="score", value=0.82)
```

**Categorical** — a discrete label:
```python
LLMObs.submit_evaluation(span=span, label="semantic_validation", metric_type="categorical", value="pass")
```

### Submitting Multiple Evaluations Per Span

Multiple evaluations can be attached to the same span. Export the span once and submit all evaluations:

```python
try:
    if LLMObs and is_observability_enabled():
        span = LLMObs.export_span()
        if span:
            LLMObs.submit_evaluation(span=span, label="context_relevance", metric_type="score", value=relevance)
            LLMObs.submit_evaluation(span=span, label="aggregated_confidence", metric_type="score", value=confidence)
            LLMObs.submit_evaluation(span=span, label="semantic_validation", metric_type="categorical", value=validation)
except Exception:
    pass
```

### Why `except Exception: pass` Is Acceptable Here

This is the one acceptable use of silent exception handling. Observability is a side effect — it must never impact the primary extraction/generation pipeline. If Datadog is down, the network is flaky, or the span context is lost, the business logic continues unaffected.

---

## 6. Hybrid Recall Strategy

The hybrid strategy minimizes evaluation cost while maintaining quality monitoring:

```
Request arrives
    │
    ▼
┌─────────────────────────┐
│ context_recall_heuristic │  ← Always runs (zero cost)
│ (fast, local computation)│
└───────────┬─────────────┘
            │
            ├─ score >= 0.7 ──→ Done. Recall is acceptable.
            │
            └─ score < 0.7 or hit_limit ──→ ┌──────────────────────┐
                                              │ context_recall_llm    │  ← Conditional (LLM cost)
                                              │ (LLM validates recall)│
                                              └──────────────────────┘
```

**Production cost savings:** ~80% of requests pass the heuristic threshold, avoiding the LLM evaluation call entirely.

**Configuration:** The 0.7 threshold is a tunable parameter. Lower thresholds trigger fewer LLM evaluations (cheaper but less monitoring). Higher thresholds trigger more (better coverage but higher cost).

---

## 7. Evaluation Cost Summary

| Metric | Compute | LLM Cost | Frequency | Notes |
|--------|---------|----------|-----------|-------|
| `context_relevance` | Minimal | Zero | Every request | Local math on chunk metadata |
| `context_precision` | Minimal | Zero | When > 1 extraction | Rank analysis |
| `context_recall_heuristic` | Minimal | Zero | Every request | Count-based |
| `context_recall_llm` | Minimal | 1 LLM call | ~20% of requests | Only when heuristic < 0.7 |
| `recall_warning` | Minimal | Zero | When flagged | Side effect of heuristic |
| `aggregated_confidence` | Minimal | Zero | Every request | Derived from extraction |
| `semantic_validation` | Minimal | Zero | Every request | String comparison |
| `multi_source_agreement` | Minimal | Zero | Multiple extractions | Counter-based |
| `agreement_pattern` | Minimal | Zero | Multiple extractions | Derived from agreement |

**Total cost per request:** 0–1 LLM calls for evaluation (the extraction LLM call itself is the business logic, not an evaluation cost).

---

## 8. Complete Evaluation Flow

```
@workflow: extract_field("roofType", chunks)
  │
  ├─ submit: context_relevance = 0.82          ← Before LLM call
  │
  ├─ @task: call_bedrock() → extractions
  │
  ├─ submit: context_precision = 0.90           ← After extraction
  ├─ submit: semantic_validation = "pass"       ← Evidence grounding
  ├─ submit: aggregated_confidence = 0.88       ← Overall confidence
  │
  ├─ context_recall_heuristic = 0.75
  │    └─ submit: context_recall_heuristic = 0.75
  │
  ├─ 0.75 > 0.7? → Yes → skip LLM recall      ← Cost optimization
  │
  └─ If multiple values:
       ├─ submit: multi_source_agreement = 0.95
       └─ submit: agreement_pattern = "unanimous"
```
