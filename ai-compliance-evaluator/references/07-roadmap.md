# Roadmap — what to actually do

Sequenced by what unblocks an engagement, not by what a framework says comes first. Effort estimates
assume a small team.

---

## The framing

A regulated client rarely asks for an ISO 42001 certificate. They ask **"where does our data go"**
and **"how do we know the AI isn't making things up."** Those two questions are the entire compliance
conversation for most engagements, and both have engineering answers, not paperwork answers.

So the roadmap is ordered by those two questions — and it lands, almost incidentally, on a defensible
AI RMF posture, because the artifacts overlap.

---

## Now — before the client POC (days, not weeks)

These are cheap, and two of them are things a security reviewer can be *shown*.

1. **AI system inventory.** One row per agent. Fields per the AI RMF Playbook
   (documentation, IR plan, data dictionaries, source links, owner). ~1 hour.
2. **System cards** for each agent. Models used, prompts, graph shape, intended use,
   **known limitations**, and *what the agent must never be trusted to do*. ~1 day. This is also the
   best client-facing explainer of what the agents actually are — it does double duty in a deck.
3. **Data-flow diagram with the residency boundary drawn on it.** Where every byte of client data
   goes, and where the boundary is. This is the single artifact that answers question #1, and it is
   the one the client's security team will want. It also forces noticing that a SaaS trace store
   would cross the line. ~half a day.
4. **Confirm the AWS BAA and Bedrock's HIPAA eligibility** against the live AWS page. Do not take a
   blog's word for it, including this pack's. ~1 hour.

## Before the pilot (weeks)

5. **Prompt-injection hardening (P0 in [05-engineering-controls.md](05-engineering-controls.md)).**
   Requirement docs and PR diffs are untrusted input today and are treated as trusted. Delimit,
   separate instructions from data, add an ingest-time detection pass.
6. **Least-agency audit of every tool binding.** Especially any code volume mount a QA agent holds.
   Scope it to the code under evaluation. One control that satisfies OWASP LLM06, OWASP ASI01, and
   HIPAA minimum-necessary simultaneously.
7. **Egress redaction + audit trail** at the boundary before the model endpoint. The most
   demonstrable control a vendor can build for a healthcare reviewer.
8. **Rate/cost caps on the writer fan-out** (LLM10).
9. **Tracing / event logs.** Usually on the roadmap for product reasons already; it is also ISO
   42001 A.6.2.8 and the backbone of every incident and audit artifact. **Self-hosted** — the trace
   store inherits the data's compliance boundary.
10. **Eval harness + first evaluation report.** The highest-value item on this list. It is
    MEASURE 2.1/2.3, it is ISO A.6.2.4, and it is the proof of output accuracy that the entire
    value case rests on. If only one thing on this page gets done, it is this one.

## Before production / before any compliance claim

11. **AI system impact assessment** per agent, structured on ISO/IEC 42005's section list. Include
    the ATLAS threat-model table as its technical half.
12. **AI risk register** seeded from NIST AI 600-1's 12 GenAI risk categories. Mark the irrelevant
    ones "not applicable, because —"; that is a stronger position than omitting them.
13. **Red-team pass on prompt injection**, with the results written up (MEASURE 2.7). The write-up
    *is* the artifact.
14. **Current/Target Profile** across the ~13 AI RMF subcategories in
    [01-nist-ai-rmf.md](01-nist-ai-rmf.md). One spreadsheet; it is the gap analysis and the roadmap in
    a single document, and it is the deliverable that most looks like "we do AI RMF."
15. **AI incident log and response plan** (MANAGE 4.3).
16. **Third-party assessment of Bedrock/models** (GOVERN 6.1/6.2), including a model-deprecation
    contingency.
17. **AI policy** — the one genuinely paperwork-shaped item. Do it when there is an organization to
    apply it to, not before.

## Not now

- **ISO 42001 certification.** 6–12 months of a *running* management system before a Stage 2 audit is
  even passable, and clients rarely ask. Revisit only when a reusable-platform thesis lands and the
  credential becomes a sales asset across clients. Build against its structure meanwhile; the
  artifacts above are most of Clause 6 and Annex A.6/A.7 anyway.
- **The vendor's own HITRUST AI Security certification.** Expensive; the realistic client ask is
  *mappable evidence* so the client's own assessment does not break on the vendor's subsystem — not
  that the vendor holds a certificate. Design the artifacts to be mappable to the 44 controls; do
  not chase the cert.
- **EU AI Act work.** Monitor only. Revisit on an EU client.

---

## The one-slide version for the client

> **Three questions, three answers.**
>
> *Where does our data go?* — Nowhere. The platform runs inside your tenant; the architecture is
> cloud-agnostic on a Kubernetes core precisely so it can. Here is the data-flow diagram with the
> boundary drawn on it, and here is the egress redaction that enforces it.
>
> *How do we know the AI isn't making things up?* — Because we measure it. Here is the eval harness,
> the golden set, and the output-accuracy number. Non-determinism is managed and observed, not
> hoped away.
>
> *Who is accountable when it's wrong?* — Named owners per agent in the AI system inventory, an
> incident log, traced decisions you can reconstruct, and a human approval gate designed so that
> disagreeing is cheap.

Those three answers are the governance story, and every one of them is backed by an artifact on this
page rather than by an assurance. That is the difference between "we take AI governance seriously"
and a platform a HITRUST-certified client can actually adopt.

---

## The honest summary

**The compliance work and the product work are the same work.** Tracing, evals, and scoped tool
access are on the engineering roadmap regardless — they are what makes the agents good. What the
compliance framing adds is a *second justification* for them and a way to turn them into client-facing
evidence.

That is worth saying plainly the first time delivery-deadline pressure makes someone suggest that
governance can wait until after the deadline. It cannot be deferred, because there is nothing to
defer — it is the same sprint.
