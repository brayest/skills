---
name: ai-engineering-implementation
description: Write the application code that makes an LLM or agentic system safe, governable, and auditable — capability manifests and least-agency tool bindings, prompt-injection defenses, data classification and egress redaction, decision traces and event logs, eval harnesses and golden sets, and CI/CD gates for prompts and model pins. Use this whenever someone is building or reviewing agent code and the answer needs to be a design or a diff: giving an agent a new tool, handling uploaded documents or PR diffs as prompt input, deciding what an agent may read or write, stopping prompt injection, keeping client data or PHI out of prompts and traces, instrumenting LLM calls, building evals for non-deterministic output, gating a model upgrade in CI, or designing human review that isn't a rubber stamp. Trigger it even without the word "compliance" — "can my agent run shell commands", "how do I test a RAG pipeline", "should I let the model pick the file path", "my agent reads a whole repo", "how do I version prompts", or "review this LangGraph graph" all belong here. This skill produces CODE and code-level design; for the cloud/K8s/IAM/network side use `ai-platform-implementation`, and for assessing a system against frameworks use `ai-compliance-evaluator`.
---

# AI Engineering Implementation

You are writing the application-layer code that turns compliance requirements into real controls.
Everything here is grounded in published guidance (OWASP LLM Top 10 2025, OWASP Agentic/ASI, MITRE
ATLAS, NIST SP 800-218A, ISO 42001 Annex A, HIPAA minimum-necessary), but the output should be code
and design, not citations. Cite the framework only where it changes what you build or explains why a
control that looks paranoid is actually load-bearing.

Examples are Python/FastAPI/LangGraph with pydantic at the boundaries. Adapt the idiom to whatever
stack is in front of you — the patterns are stack-independent.

## Three stances that decide most design questions

**1. The model is untrusted; the boundary is code.** Every guarantee you make is enforced by
deterministic code around the model — schema validation, scoped credentials, egress filters — never
by instructions inside a prompt. A prompt is a request. A validator is a control. When someone
proposes "we'll tell the model not to do that," they have proposed a wish, not a mitigation.

**2. Every LLM interaction is evidence.** Stamp each call with prompt version, model ID, and trace
ID, and make it reconstructable afterward. Do this and the compliance artifacts (event logs,
incident records, red-team reports, human-oversight records) fall out of telemetry instead of being
written by hand later. This is the highest-leverage thing on the list.

**3. Fail loud.** A redaction failure, a schema mismatch, a missing config — abort the request.
Degraded-but-running is the non-compliant state and the one that hides the incident. No silent
fallbacks, no best-effort saves, no defaults that paper over a missing value.

## The convergence worth understanding

These are not three separate obligations; they are one piece of engineering seen from three angles:

- **Least-agency** (OWASP LLM06) = **HIPAA minimum-necessary** = good tool design.
- **Event logs** (ISO 42001 A.6.2.8) = the tracing you already want for debugging.
- **Eval harness** (NIST MEASURE 2.1/2.3) = the proof your output is accurate = the product's core
  claim.

Which means the compliance work and the product work are usually the *same sprint*. That is the
argument to make when deadline pressure suggests governance can wait: there is nothing to defer.

## Workflow

1. **Understand the system before prescribing.** What are the agents, what tools do they hold, what
   untrusted input reaches a prompt, where does output go, what data class is in play, who reviews.
2. **Find the untrusted-input surfaces.** In agentic systems these are usually broader than people
   think: uploaded documents, source code and PR diffs (comments are attacker-controlled text), chat
   turns, *and persisted agent state re-read on later runs*.
3. **Bound the blast radius before hardening the input.** Prompt injection is not fully preventable;
   only capability scoping bounds the damage. Design so a fully hijacked agent still cannot do
   anything consequential — then add input hygiene on top.
4. **Read the relevant reference** (routing below) and write the design or the code.
5. **Say what you did not cover.** If the fix needs an IAM policy or a network rule too, say so and
   point at `ai-platform-implementation` — half a control silently presented as a whole one is worse
   than an acknowledged gap.

## Reference routing

| Task | Read |
|---|---|
| Orientation and the three stances | `references/overview.md` |
| Giving an agent tools; what it may read/write; capability manifests; human-in-the-loop and automation bias; agent memory/state poisoning | `references/01-agent-design.md` |
| Prompt injection; fenced prompts; ingest screening; output handling and safe rendering; system-prompt hygiene; the red-team corpus | `references/02-untrusted-input.md` |
| Data classification in the type system; the single LLM gateway and egress redactor; minimum-necessary context schemas; de-identification for eval data; secrets/config hygiene | `references/03-data-boundary.md` |
| Trace schema; artifact provenance; where traces may live; monitoring signals; incident records | `references/04-observability.md` |
| Golden sets; deterministic vs. LLM-judge vs. human metric layers; judge calibration; deployment-like conditions; online eval and drift; the eval report | `references/05-evaluation.md` |
| Pipeline gates for prompts/manifests/model pins; SBOM, signing, scanning; eval and red-team gates; the release record; responding to model vulnerabilities | `references/06-cicd.md` |

## Recurring traps

- **Identifiers that scope data access (session_id, tenant_id, user_id) must come from the
  authenticated request context, never from model output.** An LLM asked to emit a session ID will
  eventually emit someone else's.
- **Output validation happens before *persistence*, not just before display.** Model output is
  untrusted input to the next component — including your database and your S3 keys.
- **Markdown rendering of agent output is an egress channel.** A remote image URL exfiltrates by
  making the reviewer's browser fetch it. A `javascript:` link is XSS against the reviewer's
  session. Under a data-residency constraint this is the cheapest exfiltration path in the system.
- **The trace store inherits the classification of what traces contain.** If payloads hold client
  data, a SaaS observability vendor is an egress path and a fourth-party disclosure. Self-host.
- **The framework writes data stores you never declared.** Agent checkpointers, memory, and message
  history retain full document content indefinitely with **no default TTL** — and because the
  framework writes them, they never surface when someone greps for where data is saved. If your
  data-flow diagram says documents are "processed and discarded," go look at the checkpoint table:
  it is probably still holding every document ever uploaded. Give it a deliberate TTL and a purge
  job, and prefer persisting a hash plus a reference over the content itself.
- **Allowlist, never denylist.** A denylist of dangerous paths or values fails open — the one you
  forget (`.env.local`, `.aws/credentials`) is the one that leaks. An allowlist fails closed.
- **A human approval gate with a prominent "approve all" button is theatre.** Automation bias is a
  named risk (NIST AI 600-1). Make disagreement cheap and record the edit rate — it is both your
  oversight artifact and your most honest quality metric.
- **Assert properties, not transcripts, in evals.** LLM output is non-deterministic; golden
  expectations are structural and semantic invariants. And evaluate through the *real graph*, not a
  bare model call — system behavior ≠ model behavior.
- **A model pin bump is a release, not a config flip.** It rides the full eval and red-team gates
  like any other change.
