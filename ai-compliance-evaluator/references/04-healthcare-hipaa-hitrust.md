# HIPAA and HITRUST — the layer with teeth

AI RMF is voluntary. ISO 42001 is optional. **This one is not.** A HIPAA-regulated,
HITRUST-certified client's security and compliance gatekeepers will raise this layer first — and
often through a vague internal AI policy that must be taken seriously anyway. Everything else in
this pack is subordinate to it.

---

## 0. The constraint that often overrides everything: data residency

Regulated clients commonly impose a contractual clause of this shape:

> **No client information may leave the client's environment.** Not patient data. Not non-patient
> data. Not a copy-pasted requirement doc. Even non-PHI egress breaks the clause, and the legal
> exposure is **the vendor's**.

Where such a clause exists, the practical consequences are not negotiable:

- Any sandbox, POC, or client demo uses **synthetic / lookalike data only** — no connections to the
  client's cloud tenant, design tools, or ticketing systems.
- The production posture is the platform running **inside the client's tenant** (e.g. Azure AI
  Foundry for an Azure shop), which is precisely why a cloud-agnostic Kubernetes core is worth the
  cost. That design decision is a *compliance* decision, and it should be presented as one.
- Every new plan gets pressure-tested against this rule before anything else.

Note the asymmetry: such a clause is *stricter* than HIPAA. HIPAA would permit PHI to flow to a
business associate under a BAA. A residency clause does not permit the data to leave at all.
**Do not argue HIPAA-compliance as a way around it** — that is a category error and it will read as
evasive to the client's security team.

---

## 1. HIPAA and AI — the actual ground truth

**There is no HIPAA AI rule.** HHS/OCR has issued no AI-specific regulation. The existing Privacy,
Security, and Breach Notification Rules apply *as-is* to any system that creates, receives,
maintains, or transmits PHI — including an LLM pipeline. There is no AI carve-out and no AI
exemption. An agent is treated exactly like an employee or a subcontractor would be.

Three consequences that bite in an agentic architecture:

### De-identification — the only two legal methods
Per HHS's still-current guidance
(<https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html>):

- **Safe Harbor** — remove all 18 enumerated identifiers.
- **Expert Determination** — a qualified expert statistically determines re-identification risk is
  very small, and documents the method.

If we ever train, fine-tune, or *evaluate* on real patient data, it must pass one of these before it
stops being PHI. **There is no "it's just eval data" or "it's just training data" exception.** For us
this is mostly moot — we are not touching patient records, we are touching requirements and code —
but it governs any future eval set built from real client artifacts.

### Minimum necessary
The Minimum Necessary Rule applies to an agent exactly as it applies to a person. **An agent with
tool access to more data than its task requires is a violation waiting to be cited**, regardless of
whether it ever reads the excess. This is the single most important HIPAA principle to internalize
for agentic design, and it converges precisely with OWASP's *Excessive Agency* (LLM06) and the
"least-agency" principle. The compliance requirement and the security requirement are the same
requirement — scope every tool binding to the narrowest data it needs.

### Business Associate Agreements with model providers
A model provider that receives prompts containing PHI **is a Business Associate** and must be under a
BAA. If PHI reaches an endpoint or feature *not* covered by that BAA, we are non-compliant the moment
real PHI enters a prompt.

- **AWS Bedrock** is covered under the AWS Business Associate Addendum in HIPAA-eligible regions; the
  BAA is self-serve via AWS Artifact at no cost. Bedrock (and AgentCore) appear on the HIPAA Eligible
  Services Reference — **verify against the live page before relying on it**:
  <https://aws.amazon.com/compliance/hipaa-eligible-services-reference/>
- **Azure OpenAI** is covered under the Microsoft Online Services BAA / DPA — relevant for
  client-tenant deployments on Azure.

**The failure mode to actually watch:** BAA coverage varies by *endpoint, feature, and sub-processor*.
Logging and telemetry features, preview APIs, and third-party plugins are commonly **out of BAA
scope even when the base model endpoint is in scope**. This is the most-cited real-world compliance
failure in this space. It has a direct implication for any LLM platform: add Langfuse or any
tracing layer and **the trace store inherits PHI** and must sit inside the same compliance boundary
as the model call. A self-hosted trace store inside the client tenant is
the only posture that survives this; a SaaS observability vendor does not, unless separately
BAA-covered.

Standard defensive pattern (practitioner convention, not a published standard): **a PHI
scanner/redactor at the egress boundary before any prompt leaves the environment, emitting an audit
trail of what it redacted.** Worth building regardless — it is cheap, it is demonstrable, and it is
the single most reassuring thing to show a healthcare security reviewer.

### Find the undeclared PHI stores before the reviewer does

An assessment that stops at "the database and the trace store" will miss the stores that actually
sink most engagements. Enumerate these explicitly in any readiness review — each one holds full
document or message content, and each one is a PHI store nobody wrote on the data-flow diagram:

- **The agent framework's own persistence.** LangGraph checkpointers, agent memory, conversation
  state, message-history tables. They retain complete document text **indefinitely, with no default
  TTL**, and because the *framework* writes them rather than the application, they never surface
  when someone greps the codebase for where data is saved. Typically also not CMK-encrypted and not
  covered by any retention policy. **Ask about this by name — it is the most commonly missed store
  in LLM platforms, and a reviewer who finds it before you did will assume there are others.**
- **The trace/observability store** (see above) — the most-cited failure, and the one people at
  least know to look for.
- **Model invocation logs.** Enabling Bedrock model invocation logging is the right call for audit
  evidence, but it creates a bucket of prompts and completions in plaintext. It is simultaneously a
  control and a PHI store; treat it as both (encryption, retention, access logging).
- **Application logs and error traces** that print prompt contents into a log pipeline with weaker
  access control than the governed payload store.
- **Cached intermediate artifacts** — analysis caches, agent-authored instruction files, vector
  stores and their source chunks.

For each: assign a data class, put it on the diagram, give it a deliberate TTL and a purge job, and
confirm it sits inside the compliance boundary. "We didn't know the framework was writing that" is
not a defense, and it is a straightforward retention violation the moment a client's contract
specifies how long their data may be held.

---

## 2. HITRUST's AI offerings

HITRUST — which HITRUST-certified clients already live inside — now sells two distinct AI products.
Knowing the difference matters, because clients often ask about the wrong one and the vendor should
be able to reframe.
<https://hitrustalliance.net/ai-hub>

| | **AI Security Assessment & Certification** | **AI Risk Management Assessment** |
|---|---|---|
| **Controls** | **44**, tailorable | **51** |
| **Output** | A real **HITRUST certification** (1- or 2-year), third-party validated | A scored assessment. **No certificate.** |
| **Scope** | Securing the AI platform and pipeline: prompt injection, model theft, data leakage. OWASP/ATLAS territory. | Lifecycle governance: bias, accountability, documentation. AI RMF / ISO 42001 territory. |
| **Aligned to** | NIST, ISO/IEC, OWASP | **Scored against NIST AI RMF 1.0 and ISO/IEC 23894** |
| **How taken** | Standalone, **or bolted onto an existing e1 / i1 / r2** HITRUST CSF assessment | Standalone or complementary |

Announced Nov 2024: <https://hitrustalliance.net/press-releases/hitrust_launches_ai_security_assessment_and_certification>

### Why this is the most strategically useful finding in this pack

**HITRUST's AI Risk Management Assessment is scored against NIST AI RMF.** That closes the loop
perfectly:

- The client already speaks HITRUST.
- HITRUST's AI governance product is scored against AI RMF.
- AI RMF is free, immediate, and the natural framework for a vendor to adopt anyway.

So AI RMF work is not an academic exercise — **it is the direct input to an artifact the client's
compliance function already recognizes and knows how to read.** That is the bridge between the
vendor's engineering work and the client's governance language, and it is worth saying out loud in
client-facing material.

### What a HITRUST-certified client will most likely require
As a vendor delivering an AI subsystem into a HITRUST-certified environment, expect one of:

**(a)** The vendor holds its own HITRUST AI Security certification — expensive, slow, rarely
worth it for a single engagement; or
**(b)** **The vendor supplies control evidence mapped to the client's framework**, so that bolting
the AI Security assessment onto their existing e1/i1/r2 does not break on the vendor's subsystem.
**This is the realistic ask.** It means the artifacts need to be *mappable*, not that the vendor
needs its own certificate.

Plan for (b). Design the evidence artifacts ([06-required-artifacts.md](06-required-artifacts.md)) so
they can be handed to the client's assessor and mapped to the 44 AI Security controls.

---

## 3. One gap worth flagging

**FDA.** If the platform's outputs ever influence a *clinical* decision, FDA's Software-as-a-Medical-
Device jurisdiction may attach independently of HIPAA and HITRUST. For a delivery-workflow platform
it plainly does not — the outputs are developer tickets and test cases, not clinical
recommendations, and no patient is an AI subject in the 42001 sense.

But when the client is a healthcare software company, the obvious question in a room full of their
executives is *"could we point this at our clinical modules?"* The answer to have ready is:
**not without a separate regulatory analysis.** Say it before they do; it demonstrates the vendor
understands their world, not just its own.
