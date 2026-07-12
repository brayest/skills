# Observability — decision traces as the compliance backbone

**Requirement being implemented:** ISO 42001 A.6.2.8 (event logs) and A.6.2.6 (operation/monitoring),
NIST MANAGE 4.1 (post-deployment monitoring) and 4.3 (incident tracking), SP 800-218A
respond-to-vulnerabilities, AI 600-1 incident disclosure.

The standard all of these converge on: **you can reconstruct, after the fact, what the agent saw,
what it decided, what it did, and which prompt+model produced it.** That is one sentence and it is
the entire requirement. Everything below is the schema that sentence implies.

This is also the capability most LLM platforms identify as their real gap — tracing and evals — so
this file is usually the compliance spec for work already planned, not new scope.

---

## 1. The trace model

One **trace** per user-triggered operation (generate backlog, chat turn, QA evaluation), containing
**spans** per graph node, with LLM spans carrying the full reconstruction payload:

```python
class LLMSpan(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None
    agent: str                        # "product-agent" | "qa-agent"
    node: str                         # "ticket_planner", "haiku_ticket_writer[3]"

    # Reconstruction — the compliance core
    prompt_name: str                  # "REQUIREMENTS_ANALYSIS_PROMPT"
    prompt_version: str               # git sha of the prompts package at build time
    model_id: str                     # exact Bedrock model ID, as invoked
    input_digest: str                 # sha256 of final post-redaction prompt
    input_ref: str | None             # pointer into governed payload store (see §3)
    output_digest: str
    output_ref: str | None

    # Egress + safety signals
    egress_report: EgressSummary      # what the redactor scanned/redacted/blocked
    injection_suspected: bool
    schema_valid: bool                # did output pass validation first try
    retries: int

    # Accounting
    input_tokens: int
    output_tokens: int
    latency_ms: int
    session_id: str
    data_class: DataClass             # highest classification touched
    ts: datetime
```

Design decisions embedded there:

- **`prompt_version` is the build's git SHA, stamped at image build time** (env var injected in CI).
  Prompts are code in this repo, so the code version *is* the prompt version — no separate registry
  needed until prompts leave the repo. This gives prompt↔output↔eval linkage for free.
- **Digest always, payload by reference.** Every span carries hashes (tamper-evident, cheap); full
  prompt/completion bodies go to a **governed payload store** with its own access control and
  retention (§3). Traces without payloads are auditable; payloads without governance are a leak.
- **The egress report and safety signals live on the span.** "Show me every invocation where
  redaction fired" or "where injection was suspected" must be a query, not an investigation.

## 2. Persisted artifacts carry their provenance

Every object the agents write (ticket JSON, analysis cache, `requirements_agent.md`, test cases)
embeds the trace that produced it:

```python
class ArtifactProvenance(BaseModel):
    trace_id: str
    span_id: str
    prompt_version: str
    model_id: str
    generated_at: datetime
    reviewed: TicketReview | None      # filled when a human touches it
```

This closes the loop in both directions: from a bad ticket in the DB to the exact prompt+model+input
that made it (incident forensics), and from a prompt change to every artifact it produced
(blast-radius analysis when a regression ships). It is also, literally, the "traceability graph"
the product promises the client — same data structure, second buyer.

## 3. Where traces live — the boundary rule

**The trace store inherits the classification of what traces contain.** Payloads include client
requirement text; therefore the trace store sits inside the same boundary as the database:

- **Self-hosted only** (Langfuse/Phoenix/OTLP backend on the cluster) — a SaaS observability vendor
  is an egress path and a fourth-party disclosure, per
  `04-healthcare-hipaa-hitrust` in the `ai-compliance-evaluator` skill. Deployment pattern in
  `04-audit-logging` in the `ai-platform-implementation` skill.
- Two access tiers: **metadata/metrics** (spans without payloads — engineers, dashboards, the
  client's future platform team) and **payloads** (named roles, access itself logged). This mirrors
  the two-tier need: quality monitoring is daily; reading raw client prompts is exceptional.
- Retention is set per tier and per `data_class`, and it must be *decided*, documented in the
  record-retention line of the AI policy, and enforced by lifecycle rules — not left to disk
  capacity. (Client-internal payloads: align to the client agreement. Synthetic: keep liberally,
  they feed evals.)

Instrument via **OpenTelemetry GenAI semantic conventions** (`gen_ai.*` attributes) rather than a
vendor SDK's native format — the backend stays swappable (matters when the platform moves into a
client-owned tenant on another cloud, where the same traces should land in the client's stack
unchanged).

### The store everyone forgets: agent checkpoints

The trace store is the *obvious* payload store. The one that gets missed in every review is the
**framework's own persistence layer** — LangGraph checkpointers, agent memory, conversation state,
message history tables. These retain **full document and message content indefinitely, with no
default TTL**, and they are written by the framework rather than by your code, so they never show up
when someone greps for where data is saved.

In a system whose data-flow diagram promises "requirement docs are processed and discarded," a
checkpoint table quietly holding every document ever uploaded is a straightforward
retention violation — and under HIPAA it is a PHI store nobody declared. Concretely:

- **Inventory it.** Every checkpointer, memory store, and message table goes on the data-flow diagram
  with its `data_class` and its retention.
- **Set a TTL and enforce it.** Checkpoints exist to resume interrupted runs — that need expires in
  hours or days, not forever. Pick the number deliberately and implement a purge job; "we'll clean it
  up later" means "we have an undeclared PHI store."
- **Consider what you actually need to persist.** Checkpointing the full document text when a content
  hash plus an S3 reference would do is the cheapest fix available.
- The same logic applies to **DB-backed chat history** and any **cached analysis artifact**: if it
  holds client content, it inherits the classification, the boundary, and the retention rules.

## 4. Monitoring — the always-on eval

MANAGE 4.1 wants drift detection; A.6.2.6 wants operation monitoring. Derive both from the trace
stream rather than building a second system:

| Signal | Source | It detects |
|---|---|---|
| `schema_valid` rate, `retries` | spans | model/prompt regression, silent model updates upstream |
| Edit rate / accepted-untouched rate | `TicketReview` | quality drift **and** automation bias, respectively |
| `injection_suspected` rate | spans | attack activity or over-firing heuristics |
| Redaction hit rate by class | egress reports | data hygiene upstream is degrading |
| Token/latency/cost per operation | spans | LLM10 unbounded consumption, fan-out bugs |
| Online eval scores on sampled outputs | eval harness ([05](05-evaluation.md)) | fit-criteria quality drift |

Alert thresholds are config, reviewed in the same cadence as the risk register — a threshold nobody
chose is a threshold nobody owns.

## 5. Incidents — the log is a query away

MANAGE 4.3 wants incident records with severity, response, and version history. Because every span
carries versions and safety signals, an **AI incident record** is a thin document over trace data:

```python
class AIIncident(BaseModel):
    incident_id: str
    severity: Literal["sev1", "sev2", "sev3"]
    category: Literal["injection", "data_egress", "quality", "availability", "capability_violation"]
    trace_ids: list[str]              # the evidence
    affected_sessions: list[str]
    prompt_version: str; model_id: str
    detected_by: str                  # alert name | human report
    timeline: list[IncidentEvent]     # detected → contained → resolved
    corrective_action: str | None     # feeds ISO 10.2 and the risk register
```

Triggers that *must* open one automatically: any `EgressViolation` (blocked hard-identifier), any
`CapabilityViolation` in production, red-team regression on a promoted version. Human triggers:
client reports, reviewer flags. The client-facing communication duty (ISO A.8.4) hangs off severity —
define now, in the client agreement, which severities the client hears about and how fast, so it is
a contract term rather than an improvisation during the first incident.

## 6. What falls out for free

Build §1–§3 and the following artifacts stop being writing tasks:

- **Event logs** (ISO A.6.2.8) — the trace stream itself.
- **Monitoring records** (MANAGE 4.1, artifact #11) — the dashboard's history.
- **Red-team reports** (artifact #9) — red-team runs are traced runs with a tag.
- **Human-oversight records** (artifact #13) — the review table.
- **Incident log** (artifact #12) — §5.
- The evaluation report's raw data (artifact #8) — spans joined to eval scores.

That is six of the fifteen artifacts in `06-required-artifacts` in the `ai-compliance-evaluator` skill
generated as a side effect of telemetry the product needs anyway. This is the strongest single
argument that compliance and product are the same sprint.
