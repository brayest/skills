# Required artifacts — the evidence an auditor asks for

Governance frameworks are ultimately assessed on **documents and records**, not intentions. This is
the list of what we must be able to hand over, what standard demands each one, and — importantly —
**which ones have a real published template and which ones we have to design ourselves.**

That last distinction matters. Several vendors sell "AI red-team report templates" and "AI governance
document packs" as if they were standards. For most of these artifacts, **no published template
exists** from NIST, ISO, or OWASP. What exists is a specification of required *content*. Design
against the content; do not buy a template and assume it confers compliance.

---

## 1. The artifact set

| # | Artifact | Demanded by | Template status |
|---|---|---|---|
| 1 | **AI system inventory / registry** | AI RMF **GOVERN 1.6**; ISO 42001 A.4.2 | **Semi-standard.** The AI RMF Playbook specifies the fields — see below. |
| 2 | **AI policy** | ISO 42001 **5.2**, A.2.2; AI RMF GOVERN 1.x | Org-designed. Certification bodies publish outlines. |
| 3 | **AI risk register** | ISO 42001 6.1.2; AI RMF GOVERN/MAP | Org-designed. **Not a NIST-named artifact** — a convention, though a near-universal one. |
| 4 | **AI system impact assessment** | ISO 42001 **6.1.4 / 8.4 / A.5**; AI RMF MAP 5.1–5.2 | **ISO/IEC 42005:2025** exists precisely for this. See §3. |
| 5 | **Statement of Applicability (SoA)** | ISO 42001 **6.1.3** | Standard-defined structure. Only needed for a 42001 push. |
| 6 | **Model cards** (one per agent) | AI RMF **MEASURE 2.1**, MAP 1.1/2.1 | **Genuinely standardized.** Mitchell et al. 2018; Hugging Face is the de facto format. |
| 7 | **Datasheets for datasets** | AI RMF MEASURE 2.1 | **Genuinely standardized.** Gebru et al. 2018. |
| 8 | **Evaluation / TEVV report** | AI RMF **MEASURE 2.1, 2.3**; ISO 42001 A.6.2.4 (V&V) | **No published template.** Required *contents* are specified; format is ours. |
| 9 | **Red-team report** | AI RMF **MEASURE 2.7** | **No published template.** Do not let a vendor tell you otherwise. |
| 10 | **Event logs / decision traces** | ISO 42001 **A.6.2.8**; SP 800-218A | Org-designed. This is engineering, not paperwork. |
| 11 | **Drift / post-deployment monitoring records** | AI RMF **MANAGE 4.1**; ISO 42001 A.6.2.6 | **No published template.** |
| 12 | **AI incident log + response plan** | AI RMF **MANAGE 4.3**; ISO 42001 A.8.4 | No template. NIST points at the AI Incident Database and AIAAIC repository as structural models. |
| 13 | **Human-oversight records** | AI 600-1 (human-AI configuration); EU AI Act Art. 14 | Org-designed. For us: the PO/QA approval trail. |
| 14 | **Third-party / supplier AI assessment** | AI RMF **GOVERN 6.1–6.2**; ISO 42001 A.10.3 | Org-designed. Covers Bedrock and the models. |
| 15 | **Current / Target Profile** | AI RMF Profiles | CSET publishes a usable template (its extra fields are CSET's, not NIST's). |

---

## 2. The two that are actually standardized — use them, don't reinvent

**Model cards** and **datasheets for datasets** are the only artifacts in this list with genuine,
widely-adopted, stable formats. The AI RMF Playbook cites both by name (Mitchell et al.; Gebru et
al.) under MAP 1.1, MAP 2.1/2.3, and MEASURE 2.1 as the expected transparency documentation.

Together they form the documentation chain: **datasheet (data provenance) → model card (model
behaviour and limits) → system documentation (deployment context)**.

Hugging Face's format is the practical implementation — a YAML-fronted README with a structured
metadata block: <https://huggingface.co/docs/hub/en/model-cards> (annotated template and guidebook
linked from there).

**A caveat specific to us:** we do not train models. Our "model card" is really a **system card** for
each agent — the Product agent and the QA agent — documenting the composed system: which Bedrock
models, which prompts, what the graph does, intended use, **known limitations**, evaluation results,
and what it must never be trusted to do. That last field is the most valuable one in the document and
the one most often left out.

---

## 3. AI system impact assessment — ISO/IEC 42005:2025

The first international standard dedicated specifically to AI impact assessment, published 2025, and
the operational companion to 42001's 6.1.4 requirement (42001 says *have a process*; 42005 says *here
is how*). NIST published a crosswalk between 42005 and the AI RMF in Aug 2025, so **MAP and MEASURE
work populates a 42005-shaped assessment directly** — no duplicate effort.

> Paywalled, so the section list below is triangulated from secondary sources, not the standard text.
> Directionally reliable; buy the standard before formal use.

An impact assessment should carry, at minimum:

1. Methodology, findings, mitigations, monitoring plan
2. How the assessment feeds organizational decision-making
3. Lifecycle scope and timing — what is assessed and when
4. Named roles and responsibilities
5. **Impact thresholds** — the triggers that escalate to deeper assessment
6. Findings across dimensions: **privacy, fairness, transparency, safety**, environmental impact
7. Patterns, trends, identified mitigations
8. A standardized reporting format for stakeholders/regulators
9. Formal approval and sign-off
10. **Ongoing monitoring and review records** — 42005 frames impact assessment as *continuous*, not a
    one-time gate. Redo it after significant change (42001 §8.4 says so explicitly).

**The EU AI Act's FRIA** is a related but distinct, legally-mandated instrument for deployers of
certain high-risk systems, narrower in focus (fundamental rights: dignity, privacy,
non-discrimination, access to justice). Not a current obligation for us — but a useful structural
template.

---

## 4. The AI system inventory — the schema

The Playbook gives a usable field list, which makes this the closest thing to an official template in
the whole set. Per GOVERN 1.6, each entry should hold:

- System documentation
- Incident response plan
- Data dictionaries
- Links to implementation / source code
- Named **AI-actor contacts** (who owns this)

NIST warns explicitly that **partial inventories provide substantially less value than complete
ones** — a half-populated registry is close to worthless, because its value is in being the
authoritative answer to "what AI do we run."

For us this starts trivially small: **two entries** — Product agent, QA agent. Start it now while it
is two rows; retrofitting an inventory later is how organizations end up with shadow AI.

---

## 5. What we already have, and what is missing

Grounded in the platform's current state:

**Have (partially):**
- System documentation — a good architecture README is the raw material for the system cards, not a
  substitute for them.
- Prompt inventory and strategy documentation.
- Versioning and rollback of prompts via git.

**Missing — and these are the gaps that matter:**
- **Tracing / event logs.** Usually already wanted for product reasons. It is also a compliance
  artifact (#10). Two reasons, one build.
- **An eval harness and evaluation report** (#8). The single highest-value missing artifact: it is
  simultaneously MEASURE 2.1/2.3, ISO A.6.2.4, and the proof of output accuracy that the entire
  client value case rests on.
- **Model/system cards** (#6). A day of work. Should exist before any client demo.
- **AI system inventory** (#1). An hour of work.
- **Impact assessment** (#4) for each agent.
- **Red-team results** for prompt injection (#9).
- **Incident log and response plan** (#12).

The ordering insight: **the two most valuable missing artifacts (tracing and evals) are things a
platform team builds for product reasons anyway.** The compliance framing does not add work — it
adds a second, independent justification for work already on the roadmap, and it converts that work
into client-facing evidence. That is the argument to make when delivery-deadline pressure makes
someone ask whether governance can wait.
