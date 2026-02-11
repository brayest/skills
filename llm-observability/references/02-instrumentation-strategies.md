# Instrumentation Strategies

## 1. Span Decorators

Span decorators create named trace spans that appear in the observability platform's trace waterfall. Three decorator types represent different semantic levels:

| Decorator | Semantic Meaning | Use For |
|-----------|-----------------|---------|
| `@workflow` | A high-level pipeline or operation | Document processing, batch extraction, multi-step RAG pipelines |
| `@task` | A discrete step within a workflow | Single LLM call, embedding generation, validation step, retrieval |
| `@agent` | An autonomous agent entry point | Agent loops, ReAct-style agents, tool-calling agents |

### When to Use Each

**`@workflow`** — Entry point for a complete operation. One workflow per user-visible action:
- `extract_all_fields()` — processes an entire document
- `process_query()` — handles a complete RAG query
- `batch_process_images()` — processes a set of images

**`@task`** — Individual steps within a workflow. Nest under workflows for drill-down:
- `retrieve_context()` — single retrieval call
- `call_llm()` — single LLM invocation
- `validate_result()` — post-processing validation
- `generate_embedding()` — single embedding call

**`@agent`** — Autonomous agent patterns with iterative loops:
- `process_single_field()` — an agent that decides strategy, retrieves, extracts, validates
- `research_agent()` — multi-step research with tool calls

### Nesting Behavior

When a `@task` function is called from within a `@workflow` function, the task span appears nested under the workflow span in the trace waterfall:

```
@workflow: extract_field()               [total: 3200ms]
  ├─ @task: retrieve_context()           [450ms]
  ├─ @task: call_bedrock()               [2100ms]
  │    └─ Bedrock converse() span        [auto-traced: tokens, model_id]
  ├─ @task: validate_evidence()          [350ms]
  └─ evaluations submitted               [context_relevance=0.82, ...]
```

## 2. Graceful Import Pattern

Decorators must degrade to no-ops when the tracing library is not installed. This allows the same codebase to run in production (with tracing) and in tests/local dev (without tracing dependencies).

### Module-Level Import with Fallback

```python
# At the top of any module that uses decorators
try:
    from ddtrace.llmobs.decorators import workflow, task
    from ddtrace.llmobs import LLMObs
    LLMOBS_AVAILABLE = True
except ImportError:
    LLMOBS_AVAILABLE = False
    workflow = lambda f: f  # no-op: returns the function unchanged
    task = lambda f: f
    LLMObs = None

from myapp.observability import is_observability_enabled
```

### Key Points

- The `lambda f: f` pattern makes the decorator a transparent pass-through
- `LLMObs = None` allows guarding evaluation submissions with `if LLMObs and is_observability_enabled()`
- Import happens once at module load time — no per-call overhead
- The same code path executes regardless of whether tracing is available

### Alternative: OpenLLMetry Decorators

When using Traceloop/OpenLLMetry directly (without ddtrace LLMObs):

```python
try:
    from traceloop.sdk.decorators import workflow, task, agent
    _TRACING_AVAILABLE = True
except ImportError:
    _TRACING_AVAILABLE = False
    def workflow(name=None):
        return lambda fn: fn
    def task(name=None):
        return lambda fn: fn
    def agent(name=None):
        return lambda fn: fn
```

## 3. Applying Decorators

### Basic Usage

```python
@workflow
async def extract_field(self, field_name: str, chunks: list[dict]) -> dict:
    """High-level extraction — appears as a workflow span."""
    relevance = self._calculate_relevance(chunks)

    # Submit evaluation against the current workflow span
    try:
        if LLMObs and is_observability_enabled():
            span = LLMObs.export_span()
            if span:
                LLMObs.submit_evaluation(
                    span=span,
                    label="context_relevance",
                    metric_type="score",
                    value=relevance
                )
    except Exception:
        pass  # Observability must never crash business logic

    result = await self._call_llm(field_name, chunks)
    return result


@task
def _call_llm(self, field_name: str, chunks: list[dict]) -> dict:
    """Individual LLM call — nested as a task span under the workflow."""
    response = self.llm_client.converse(...)
    return response
```

### Agent Pattern

```python
@agent
async def _process_single_field(self, field_name: str, document_id: str) -> dict:
    """Agent entry point — decides strategy, retrieves, extracts, validates."""
    # Step 1: Determine retrieval strategy
    strategy = self._select_strategy(field_name)

    # Step 2: Retrieve context
    chunks = await self._retrieve(field_name, strategy)

    # Step 3: Extract with LLM
    result = await self._extract(field_name, chunks)

    # Step 4: Validate
    validated = await self._validate(result, chunks)

    return validated
```

## 4. Span Naming Conventions

Consistent span names enable filtering and aggregation in dashboards:

| Operation Type | Recommended Name | Example |
|---------------|-----------------|---------|
| Document pipeline | `workflow.document_extraction` | Processing an entire document |
| Field extraction | `workflow.field_extraction` | Extracting a single field |
| Image analysis | `workflow.image_analysis` | VLM-based image description |
| Hybrid retrieval | `task.hybrid_retrieval` | BM25 + KNN combined search |
| LLM extraction call | `task.llm_extraction` | Single Bedrock/OpenAI call |
| Embedding generation | `task.embedding_generation` | Generating embeddings for text |
| Evidence validation | `task.evidence_validation` | Grounding check on extracted values |
| Post-processing | `task.post_processing` | Ranking, filtering, context expansion |
| Aggregation analysis | `task.aggregation_analysis` | Multi-value strategy determination |
| Agent field processing | `agent.field_processor` | Autonomous agent for a single field |

## 5. Adding Metadata to Spans

Attach contextual metadata to spans for filtering and debugging:

```python
@workflow
async def extract_field(self, field_name: str, document_id: str, chunks: list) -> dict:
    # Add metadata to the current span
    try:
        if LLMObs and is_observability_enabled():
            LLMObs.annotate(
                input_data=f"field={field_name}, chunks={len(chunks)}",
                metadata={
                    "document_id": document_id,
                    "field_name": field_name,
                    "chunks_count": len(chunks),
                    "model": "anthropic.claude-sonnet",
                }
            )
    except Exception:
        pass

    # ... extraction logic
```

### What to Include in Span Metadata

**Include:**
- `document_id`, `field_name` — for filtering
- `model` — which LLM model was used
- `chunks_count` — retrieval volume
- `token_count` (input/output) — cost tracking
- `latency_ms` — performance

**Avoid (privacy/cost):**
- Full prompt text (large, may contain PII)
- Full LLM response text (large)
- Raw embeddings (very large, not useful in traces)
- User identifiers as tag values (high cardinality)

## 6. Async Instrumentation

Decorators work transparently with both sync and async functions:

```python
@workflow
async def async_extraction(self, ...) -> dict:
    """Async workflow — decorator handles both sync and async."""
    result = await self._async_llm_call(...)
    return result

@task
def sync_embedding(self, text: str) -> list[float]:
    """Sync task — same decorator works."""
    return self.embedding_model.encode(text)
```

### Context Propagation in Concurrent Tasks

When using `asyncio.gather()` or `asyncio.create_task()`, trace context may not propagate automatically. Ensure the parent span context is accessible:

```python
@workflow
async def batch_extract(self, fields: list[str]) -> list[dict]:
    """Parallel extraction — each gather'd coroutine gets its own task span."""
    tasks = [self._extract_single(field) for field in fields]
    results = await asyncio.gather(*tasks)
    return results

@task
async def _extract_single(self, field: str) -> dict:
    """Each task creates its own span — context propagates from the workflow."""
    return await self._call_llm(field)
```

The `@task` decorator on each coroutine ensures a new child span is created, maintaining the trace hierarchy even in concurrent execution.
