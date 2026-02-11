---
name: llm-observability
description: "This skill should be used when implementing observability, tracing, and evaluation for LLM-powered Python applications. Provides generalized strategies for what to observe in LLM systems, span instrumentation with graceful degradation, a multi-metric evaluation framework across retrieval/extraction/aggregation dimensions, structured logging with trace correlation, and Datadog LLM Observability integration as a platform reference."
---

# LLM Observability & Evaluation

Production-tested patterns for observing, tracing, and evaluating LLM-powered applications. Covers the full observability stack: distributed tracing, span instrumentation, evaluation metrics, structured logging, and platform integration. Applicable to RAG pipelines, extraction systems, agents, and any LLM-powered workflow.

## When to Use

Apply this skill when:
- Adding observability to an LLM-powered application (RAG, agents, extraction, chat)
- Deciding what metrics and evaluations to collect for LLM pipelines
- Instrumenting LLM workflows with span decorators (`@workflow`, `@task`, `@agent`)
- Implementing structured logging with trace-log correlation
- Designing evaluation metrics for retrieval quality, extraction confidence, or multi-source agreement
- Integrating with Datadog LLM Observability (ddtrace + LLMObs + OpenLLMetry)
- Setting up auto-instrumentation for boto3/Bedrock, LlamaIndex, or LangChain
- Designing graceful degradation so observability never crashes business logic
- Optimizing observability cost (sampling, conditional evaluation, noise filtering)

**Trigger scenarios**:
- "How do I add tracing to my LLM pipeline?"
- "What should I observe in a RAG application?"
- "How do I evaluate retrieval quality in production?"
- "What evaluations should I collect for LLM extraction?"
- "How do I correlate logs with traces?"
- "What's the graceful degradation pattern for observability decorators?"
- "How do I set up Datadog LLMObs for my Python service?"

## Key Principles

1. **Observability must never crash business logic** -- All tracing, evaluation, and metric submission wrapped in guard patterns. A tracing failure must not fail an extraction or generation call.

2. **Initialize before import** -- Tracing libraries (ddtrace, OpenLLMetry) work by monkey-patching target libraries at import time. Initialization must happen before importing boto3, LlamaIndex, or any instrumented library. Violating this silently loses all tracing.

3. **Dual-stack tracing** -- Use a provider-level tracer (ddtrace for AWS/Bedrock, or OpenAI SDK instrumentation) for infrastructure calls, and a framework-level tracer (OpenLLMetry/Traceloop for LlamaIndex/LangChain) for orchestration. Neither alone covers the full stack.

4. **Graceful degradation via feature flag** -- A module-level `_OBSERVABILITY_ENABLED` flag set during initialization. Decorators degrade to no-ops when the tracing library is absent. All evaluation submissions gated behind `is_observability_enabled()`.

5. **Hybrid evaluation strategy** -- Fast heuristic metrics always run (zero LLM cost). Expensive LLM-based evaluations only trigger when the heuristic falls below a threshold. Minimize LLM calls for evaluation purposes.

6. **Three evaluation dimensions** -- Retrieval quality (did retrieval find the right context?), extraction quality (did the LLM extract correctly and with grounding?), aggregation quality (do multiple sources agree?).

7. **Log-trace correlation** -- Every log line includes trace_id and span_id for linking logs to traces. Structured JSON logging with service metadata enables unified observability across any platform.

## How to Use This Skill

### Understanding the Architecture

For system design, initialization order, dual-stack tracing, and the feature flag pattern:
- Consult `references/01-observability-architecture.md`

**Example questions**: "What's the correct initialization order?", "How do ddtrace and OpenLLMetry work together?", "What gets auto-instrumented?"

### Instrumenting LLM Pipelines

For span decorators, graceful import patterns, nesting behavior, and span naming:
- Consult `references/02-instrumentation-strategies.md`

**Example questions**: "How do I trace a RAG pipeline?", "What's the graceful degradation pattern for decorators?", "When do I use @workflow vs @task?"

### Implementing Evaluations

For the multi-metric evaluation framework, hybrid recall strategy, and submission patterns:
- Consult `references/03-evaluation-framework.md`

**Example questions**: "What evaluations should I collect?", "How does hybrid recall work?", "How do I submit evaluations to LLMObs?"

### Structured Logging & Trace Correlation

For JSON logging setup, trace ID injection, and platform-agnostic correlation:
- Consult `references/04-structured-logging.md`

**Example questions**: "How do I set up structured logging with trace correlation?", "What fields should LLM logs include?", "How do I suppress noisy third-party loggers?"

### Datadog Integration

For Datadog-specific configuration, environment variables, ddtrace-run, and LLMObs setup:
- Consult `references/05-platform-integration-datadog.md`

**Example questions**: "What DD_* environment variables do I need?", "How do I configure ddtrace-run for Kubernetes?", "How do I set up agentless mode for local dev?"

### Production Operations

For graceful shutdown, flush ordering, cost optimization, and conflict workarounds:
- Consult `references/06-production-operations.md`

**Example questions**: "What's the shutdown flush order?", "How do I reduce Kafka polling noise?", "How do I handle the AWS SigV4 conflict?"

## Evaluation Framework Summary

| Metric | Dimension | Type | Cost | Description |
|--------|-----------|------|------|-------------|
| `context_relevance` | Retrieval | score | Zero | Intersection ratio + avg score + diversity |
| `context_precision` | Retrieval | score | Zero | Contributing chunks in top-K |
| `context_recall_heuristic` | Retrieval | score | Zero | Fast recall estimate (always runs) |
| `context_recall_llm` | Retrieval | score | LLM call | LLM-validated recall (conditional) |
| `recall_warning` | Retrieval | categorical | Zero | HIT_RETRIEVAL_LIMIT / HIGH_THRESHOLD_FILTERING |
| `aggregated_confidence` | Extraction | score | Zero | Overall extraction confidence |
| `semantic_validation` | Extraction | categorical | Zero | Evidence grounding: pass / fail / skipped |
| `multi_source_agreement` | Aggregation | score | Zero | Agreement across multiple extractions |
| `agreement_pattern` | Aggregation | categorical | Zero | unanimous / majority / mixed / conflicting |

8 of 9 metrics are zero-cost. Only `context_recall_llm` invokes an LLM, and only when the heuristic flags concern.

## Anti-Patterns

- **Observability crashing business logic** -- Never let a tracing or evaluation error propagate. Guard with `try/except Exception: pass`.
- **Importing before initializing** -- boto3 or LlamaIndex imported before `patch()` means no auto-instrumentation, silently.
- **LLM evaluation on every request** -- Use heuristic-first strategy; LLM validation only when the cheap metric flags concern.
- **Silent observability failures** -- Log warnings when observability is unavailable, but do not raise exceptions.
- **Hardcoded sampling rates** -- Use environment variables for all sampling and threshold configuration.
- **High-cardinality span tags** -- Avoid user IDs or request IDs as tag values; use them as span attributes instead.

## Quick Reference: Initialization Order

1. Configure structured logging (before anything else)
2. Initialize provider tracer (ddtrace: patches boto3, botocore, httpx)
3. Initialize framework tracer (OpenLLMetry/Traceloop: patches LlamaIndex, LangChain)
4. Set module-level `_OBSERVABILITY_ENABLED = True`
5. Import application libraries (boto3, LlamaIndex, etc.)
6. Start application

---

**Version**: 1.0
**Last Updated**: 2026-02-10
**Status**: Production-tested in LLM extraction and RAG systems
