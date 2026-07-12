# Data boundary — classification, egress redaction, residency in code

**Requirement being implemented:** client data-residency clauses (common in regulated engagements —
where one applies, it overrides everything), HIPAA
Privacy/Security Rules (minimum necessary, de-identification), OWASP LLM02 (Sensitive Information
Disclosure), ISO 42001 A.7 (data quality/provenance).

The architecture-level boundary (private endpoints, egress-denied networking) is
`03-network-egress` in the `ai-platform-implementation` skill. This file is the
**code that runs at that boundary** and the data discipline inside it. Both layers exist because each
catches the other's failures: network policy stops the request code forgot to filter; code redaction
sanitizes the request the network legitimately allows (the model call itself).

---

## 1. Classify data in the type system

Make sensitivity a property of the data, not tribal knowledge. Cheapest durable mechanism: every
persisted/transported payload carries a classification, set at ingest, propagated by construction:

```python
class DataClass(StrEnum):
    SYNTHETIC = "synthetic"        # demo/lookalike data — the only class allowed in demos
    CLIENT_INTERNAL = "client"     # client requirements, code, tickets — never leaves tenant
    PHI = "phi"                    # not expected in this platform; the class exists so its
                                   # appearance is an *event*, not an ambiguity

class StoredArtifact(BaseModel):
    data_class: DataClass
    origin: str                    # upload id / session id — provenance (ISO A.7.5)
    sha256: str
    ...
```

Rules enforced in code, not convention:

- Ingest **must** assign a class; a classless artifact fails validation (no default — a default *is*
  a fallback, and it would default wrong exactly once).
- The class travels into S3 object tags and trace attributes, so storage-level policy and
  observability can key on it (`04-audit-logging` in the `ai-platform-implementation` skill).
- **Demo/sandbox environments refuse anything above `SYNTHETIC` at the API boundary.** This turns
  the synthetic-data-only rule for demos from a briefing point into a 403.

### Enumerate every store, including the ones the framework writes for you

Classification is worthless if you miss a store. The ones teams declare: the database, the object
store, the trace backend. The ones that get missed, every time:

- **Agent framework persistence** — LangGraph checkpointers, agent memory, message history. Written
  by the framework, not by your code, so they never surface when someone greps for writes. They hold
  **full document and message content, indefinitely, with no default TTL.**
- **Cached intermediate artifacts** — an analysis cache, an agent-authored instruction file.
- **Application logs** — an exception handler that prints a prompt into stdout has just written
  client content into a log store with different access control than your governed payload store.

Each of these inherits the classification of what it holds, and therefore the boundary and the
retention rules. The practical test: if your data-flow diagram claims documents are "processed and
discarded," go look at the checkpoint table. It is almost certainly still holding every document
ever uploaded — which, in a HIPAA context, is an undeclared PHI store. Give every one of them a
deliberate TTL and a purge job, and prefer persisting a content hash plus a reference over
persisting the content itself.

## 2. The egress gate — one choke point for everything that leaves

All model calls go through a single client wrapper. Nothing else in the codebase may construct a
Bedrock/LLM client — enforce with a lint rule (forbid `ChatBedrockConverse(` outside
`app/llm/gateway.py`) so the choke point stays a choke point.

```python
# app/llm/gateway.py — the ONLY path to the model
class LLMGateway:
    def __init__(self, cfg: GatewayConfig):
        self._client = ChatBedrockConverse(
            model=cfg.model_id, region_name=cfg.region,   # explicit region, always
        )
        self._redactor = Redactor(cfg.redaction_policy)

    def invoke(self, messages: list[BaseMessage], *, ctx: TraceContext) -> AIMessage:
        report = self._redactor.scan(messages)
        if report.blocked:                        # hard identifiers → refuse, loudly
            raise EgressViolation(report.summary())  # fail the request, page nobody silently
        messages = report.apply()                 # soft hits → redact + annotate
        ctx.record_egress(report)                 # what was scanned/redacted → trace
        return self._client.invoke(messages)
```

Redactor design points:

- **Two-tier response.** Hard identifiers (SSN/MRN/patterns from HIPAA's Safe Harbor list, plus
  client-defined markers) **block the request** — in this platform their presence means something
  upstream already went wrong, and continuing-with-redaction would hide that. Soft hits (names,
  emails, phone numbers in requirement text) get redacted with stable placeholders (`[PERSON_1]`)
  so the model's output remains post-processable.
- **The audit trail is the point.** Every invocation records: what classes of content were detected,
  what was redacted, hash of pre/post prompt. This record is what you show a security reviewer —
  "here is the gate, here is its log" (`04-audit-logging` in the `ai-platform-implementation` skill).
- Engine: start with pattern+dictionary (deterministic, explainable, fast); a small NER model
  (e.g. Presidio-style) can be added *behind the same interface*. Do not start with an LLM-as-
  redactor — the redactor must not itself be an egress path or a nondeterminism source.
- **Scope honestly.** In production-inside-tenant, the model endpoint is *inside* the boundary and
  the redactor's role shifts from "prevent residency breach" to "minimum necessary + defense in
  depth." In any configuration where the model endpoint is outside (our AWS sandbox), the redactor
  plus synthetic-only data classes are the control. The same code serves both; the *policy* object
  differs per environment.

## 3. Minimum necessary as a prompt-construction rule

HIPAA's minimum-necessary rule, applied to context building: **a prompt gets the fields the task
needs, not the object graph we happen to have.** Concretely:

- Context builders select named fields (`ticket.title`, `ticket.fit_criteria`) — never
  `model_dump()` a whole ORM object into a prompt. Serializing whole objects is how internal IDs,
  emails, and unrelated tenant data leak into prompts *and traces* by accident.
- Define per-call **context schemas** (pydantic models of exactly what may enter each prompt). They
  are cheap, they document data flow per prompt for the impact assessment, and they make "what data
  does the Product agent see?" answerable by reading types.

## 4. De-identification for eval and test data

The eval harness ([05-evaluation.md](05-evaluation.md)) needs realistic data; HIPAA allows exactly
two ways to make real data non-PHI (Safe Harbor's 18 identifiers, or Expert Determination) — and the
residency clause is stricter still: even de-identified client data doesn't leave. So, in order of
preference:

1. **Synthetic-first** — generated lookalike requirements/code (the `examples/` pattern already in
   the repo). Zero legal surface; the default for golden sets, demos, CI.
2. **Client data, inside the client tenant only** — when the pilot needs real requirement docs,
   the eval runs where the data lives; results (metrics, not content) come out.
3. Never: real client artifacts copied into vendor sandbox environments, "just for testing."
   That is the exact scenario a residency clause names, and the legal exposure is the vendor's.

Metadata for whatever the golden set contains: source, `data_class`, creation date, method
(generated/curated), owner — that's the datasheet (artifact #7), maintained as YAML next to the set.

## 5. Secrets and configuration hygiene

Boring, load-bearing:

- No secrets in prompts, ever ([02-untrusted-input.md](02-untrusted-input.md) §4) — prompts leak.
- No AWS access keys in code or env — credential chain locally, workload identity in cluster
  (already the repo rule; `02-identity-access` in the `ai-platform-implementation` skill).
- Config through validated settings objects that **fail at startup** when required values are
  missing. A service that boots with a blank redaction policy is not "running with defaults," it is
  a compliance incident that hasn't been noticed yet.
- Logs and error messages follow the same redaction discipline as prompts: exception handlers must
  not print prompt contents (which may contain client data) into stdout logs that ship to a log
  store with different access control than the trace store. Log the trace ID; look up the content
  in the governed store.

## 6. Mapping back

| Mechanism | Satisfies |
|---|---|
| `DataClass` in the type system + env refusal rules | Residency clause · demo-safety rule · LLM02 |
| Single LLM gateway + lint-enforced choke point | LLM02 · auditable egress (ISO A.6.2.8) |
| Two-tier redactor + egress audit trail | HIPAA · the artifact a reviewer is shown |
| Context schemas per prompt | Minimum necessary · impact-assessment data-flow section |
| Synthetic-first eval data, datasheet metadata | HIPAA de-identification · ISO A.7.4/A.7.5 · artifact #7 |
| Fail-at-startup config, redacted logs | No-fallbacks rule · LLM02 in the logging path |
