# AI Compliance — Building Agentic AI Platforms for Regulated Clients

Research pack on what a vendor must comply with when building AI systems — scoped to an agentic
platform architecture (LangGraph agents, Bedrock, Postgres/S3, K8s) delivered into
**HIPAA/HITRUST-regulated** healthcare clients.

Compiled 2026-07-12 from primary sources (NIST, HHS, OWASP, MITRE, HITRUST). ISO/IEC 42001 is a
paywalled standard — its clauses and controls are **described here in our own words** from
certification-body sources, never reproduced. Buy the standard before a certification push.

## The files

| File | What it answers |
|---|---|
| [01-nist-ai-rmf.md](01-nist-ai-rmf.md) | NIST AI RMF: the four functions, trustworthiness characteristics, the Playbook, Profiles, the GenAI Profile. What "doing AI RMF" concretely means. |
| [02-iso-42001.md](02-iso-42001.md) | ISO/IEC 42001: Clauses 4–10, the 38 Annex A controls, mandatory documented information, the certification path, and which AI *roles* we hold. |
| [03-crosswalk.md](03-crosswalk.md) | How the two relate, plus the EU AI Act. Which to adopt, in what order, and why they are complementary rather than competing. |
| [04-healthcare-hipaa-hitrust.md](04-healthcare-hipaa-hitrust.md) | The layer that actually has legal teeth for us: HIPAA (de-identification, BAAs, minimum necessary) and HITRUST's two AI assessments. Includes the data-residency constraint. |
| [05-engineering-controls.md](05-engineering-controls.md) | What we build in code: OWASP LLM Top 10 (2025), OWASP Agentic/ASI, MITRE ATLAS, NIST SP 800-218A. Mapped to our actual architecture. |
| [06-required-artifacts.md](06-required-artifacts.md) | The evidence an auditor asks for. Which artifacts are real standards, which we must design ourselves. |
| [07-roadmap.md](07-roadmap.md) | Sequenced plan: what to do now, before the pilot, and before any certification claim. |

## Implementation guidance

The requirements above, translated into technical design — split by layer:

| Folder | What it holds |
|---|---|
| the `ai-engineering-implementation` skill | Code-level design: agent least-agency, prompt-injection defenses, data boundary and redaction, decision traces, the eval harness, CI/CD gates. Patterns in Python/FastAPI/LangGraph. |
| the `ai-platform-implementation` skill | Platform-level design: tenancy and residency architecture, workload identity and model allowlists, default-deny egress, audit logging, supply-chain enforcement, Bedrock Guardrails. Cloud-agnostic patterns, AWS worked examples, Azure equivalents noted. |

The rule that organizes the split: **every guarantee is enforced twice** — once in code, once in
infrastructure. The software folder is what a hijacked agent runs into first; the infrastructure
folder is what it runs into when the code layer fails.

## The short version

**Three layers, different force.**

- **NIST AI RMF** — voluntary, non-certifiable, US. It tells us *what good looks like*. There is no
  certificate to earn; you demonstrate it through artifacts. Cheap to adopt, useful immediately.
- **ISO/IEC 42001** — certifiable, prescriptive, international. It tells us *how to manage* AI as a
  management system (PDCA). It is the thing a client procurement team can actually be shown a
  certificate for. Real cost: an audited management system, not a document set.
- **HIPAA / HITRUST** — the only layer with legal and contractual teeth in a US healthcare
  engagement. HIPAA has
  no AI-specific rule; the existing Privacy/Security Rules apply as-is to LLM pipelines. HITRUST now
  sells an **AI Security Assessment (44 controls, certifiable)** and an **AI Risk Management
  Assessment (51 controls, scored, no certificate)**.

**The order that matters with a healthcare client.** The client's security and compliance
gatekeepers will not ask about ISO 42001 first. They will ask where PHI goes. Answer HIPAA and
HITRUST first; use AI RMF to structure risk work now; treat ISO 42001 as the credential a vendor
grows into as the platform becomes a reusable asset across clients.

**The constraint that often overrides everything.** Regulated clients commonly impose a
data-residency clause: no client information may leave the client's environment — even non-patient
data. Where one applies, every control in these docs is subordinate to it, and any demo or sandbox
uses synthetic data only. See [04-healthcare-hipaa-hitrust.md](04-healthcare-hipaa-hitrust.md).

## Source note

Where a claim is vendor marketing or an inference rather than a primary source, it is flagged
inline. Two known gaps, flagged so they are not quietly treated as settled:

- The NIST↔ISO 42001 crosswalk PDF exists on NIST's domain but is **Microsoft-submitted**, not
  NIST-authored, and its row-level mappings were not machine-verified. Read it directly before
  citing specific mappings.
- Several "standard" audit artifacts (red-team report templates, drift-monitoring records) have **no
  published template** from NIST, ISO, or OWASP. We design them against required *content*. Do not
  let a vendor sell one as a standard.
