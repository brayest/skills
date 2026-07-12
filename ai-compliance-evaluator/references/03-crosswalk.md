# Crosswalk — AI RMF vs. ISO 42001 vs. EU AI Act

Three layers that get conflated. They are not competitors; they operate at different altitudes and
carry different force.

## The one-line distinction

| | Force | Answers |
|---|---|---|
| **NIST AI RMF** | Voluntary, non-certifiable | *What good looks like* — risk modelling and best practice |
| **ISO/IEC 42001** | Certifiable, prescriptive | *How to manage* — governance, auditability, a certificate |
| **EU AI Act** | **Law**, enforced, penalties | *How you comply* — the legal constraint you must satisfy |

The EU AI Act is tiered by risk (unacceptable / high / limited / minimal) with penalties reaching
€35M or 7% of global turnover. **It does not apply to a US-only, internal-facing deployment.** It
is in this pack because (a) it applies the moment the platform is sold into an EU client, and
(b) it is a useful structural template regardless.

For a US healthcare engagement the layer with actual teeth is neither of the three — it is
**HIPAA/HITRUST**.
See [04-healthcare-hipaa-hitrust.md](04-healthcare-hipaa-hitrust.md).

---

## How AI RMF and ISO 42001 map onto each other

**They have no lineage relationship — do not describe one as built on the other.** They were authored
independently: ISO 42001 takes its skeleton from the ISO **Harmonized Structure (Annex SL)**, the same
management-system shell as ISO 27001 and 9001, while AI RMF is a NIST framework organized around four
functions. Their concerns overlap heavily, so the two are **crosswalked** — but saying "AI RMF is the
structure ISO 42001 is built on" (or the reverse) is simply wrong, and it is the kind of error that
destroys credibility in a room with a compliance auditor. Say *crosswalked*, or *complementary*, and
never *derived from*.

With that established, the concerns line up like this. AI RMF's **GOVERN** covers ground that 42001
handles in Clauses 4–5 (context, leadership, policy). **MAP** corresponds to Clause 6.1 planning plus
the impact assessment (6.1.4 / Annex A.5). **MEASURE** corresponds to Clause 9 plus the lifecycle V&V
controls (A.6). **MANAGE** corresponds to Clauses 8 and 10 — operation, treatment, nonconformity,
corrective action.

The honest summary: **doing AI RMF properly gets you most of the way to 42001's substance, and none
of the way to its certificate.** 42001 adds the management-system scaffolding that makes it
auditable — the Statement of Applicability, the internal audit programme, the management review, the
documented-information discipline. That scaffolding is the cost, and the certificate is what you buy
with it.

### The official crosswalk

NIST hosts a crosswalk between AI RMF and ISO/IEC 42001:
<https://airc.nist.gov/docs/NIST_AI_RMF_to_ISO_IEC_42001_Crosswalk.pdf>

**Two caveats, both load-bearing:**
1. It is **Microsoft-submitted**, not NIST-authored. NIST hosts community crosswalks and vets them
   for accuracy and absence of advertising, but does not endorse them.
2. Its row-level mappings were **not verified** during this research (the PDF resisted extraction).
   Read it directly before citing any specific clause↔subcategory pairing in a client deliverable.

The full crosswalk index — including ISO/IEC 23894 and ISO/IEC 42005 (both INCITS, Aug 2025), Korea's
TTA guidebook, Japan's AISI guidelines, Singapore's AI Verify, and a combined OECD / EU AI Act /
EO 13960 / AI Bill of Rights document from Jan 2023 — is at
<https://airc.nist.gov/airmf-resources/crosswalks/>. It is a living, community-submitted page; treat
any snapshot of it as a snapshot.

**There is no current NIST-authored AI RMF ↔ EU AI Act crosswalk.** The only NIST-hosted document
touching the Act predates its final text. Every "unified NIST/ISO/EU crosswalk" you will find in a
Google search is a vendor blog post. Some are decent orientation; none are authoritative. Do not put
one in front of a client as a source.

---

## Where 42001 does *not* get you EU AI Act compliance

Worth being precise about, because vendors blur it: **ISO 42001 confers no legal presumption of
conformity with the EU AI Act.** There is meaningful thematic overlap (risk management, data
governance, transparency — commonly estimated around 40–50%), but 42001 is a *management-system*
standard and the Act is *binding product regulation*. Passing one does not discharge the other.

Presumption of conformity will come from harmonized EN standards being developed by **CEN-CENELEC
JTC 21**, once published and cited in the Official Journal. Whether ISO 42001 is adopted as an EN in a
form that carries that presumption was **not confirmed** in this research — one source suggests the
Commission asked for a separate AI-Act-specific QMS standard precisely because 42001's scope and
definitions do not fully align with the Act's high-risk QMS requirement. Check <https://jtc21.eu>
directly before relying on any of this; it moves fast.

---

## What we should actually adopt, and in what order

1. **HIPAA / HITRUST first.** It is the only layer with legal and contractual force in a US
   healthcare engagement, and it is the one the client's gatekeepers will actually raise. It is
   also the one that can kill the deal.
2. **NIST AI RMF now, as the working structure.** Free, no gate, selective by design, and it is the
   vocabulary US healthcare buyers already speak. HITRUST's own AI Risk Management Assessment is
   scored against **NIST AI RMF 1.0 and ISO/IEC 23894** — so AI RMF work feeds directly into a
   HITRUST artifact the client already understands.
3. **ISO 42001 as the structure we grow into**, not a certification we chase in 2026. Its value is to
   the *reusable platform* thesis, not to any single client. Build the artifacts its Clause 6 and Annex
   A.6/A.7 demand — they are the same artifacts AI RMF and HITRUST want — and defer the audit.
4. **EU AI Act: monitor only.** Revisit the moment the platform targets an EU client.

The convergence is the point: **an AI system inventory, a risk register, an impact assessment, model
cards, an eval harness, event logs, and an incident process** satisfy all four layers at once. That
is the entire compliance programme, and none of it is wasted work — most of it is the observability
and evaluation the product needs anyway to prove fit-criteria accuracy.
