# Do you need ISO 42001 to get this signed?

**No.** Nothing in your situation legally requires it, and it is almost certainly not what their legal team actually needs.

## Why not

- **ISO/IEC 42001 is voluntary.** It's a certifiable management-system standard (an AIMS, same shape as ISO 27001's ISMS). No US law mandates it. There is no US federal AI statute that would force it on you, and the state-level stuff that exists (Colorado AI Act, NYC Local Law 144, Illinois BIPA/AIVIA, the California ADMT rules) is scoped to specific *use cases* — consequential decisions in hiring, lending, housing, insurance, education, healthcare; biometrics; automated employment screening — not to "we built an internal tool."
- **The EU AI Act doesn't reach you.** US only, internal tool, no EU users or EU market placement. Out of scope.
- **It's an internal tool.** No consumer surface, no automated decisions about the public, presumably a bounded user population inside their org. Whatever risk exists is contract-and-security risk, not regulatory risk.
- **The economics are absurd for your size.** Realistically $40–120k and 6–12 months (gap analysis, build the AIMS, run it long enough to produce evidence, Stage 1 + Stage 2 audit, then annual surveillance). You'd be certifying a management system your team is too small to actually operate. And you can't produce it before signature anyway — so if they truly gate on it, the deal is dead regardless.

## What's actually happening

Legal saw "AI" and reached for the only AI acronym they know. This is a *reassurance* request wearing a *certification* costume. The real question underneath is: **"if this thing does something dumb or leaks our data, are we exposed, and can we show our board we did diligence?"**

Answer that question and the ISO ask usually evaporates.

## What to give them instead

Ship an **AI governance package** — a few days of writing, not a year of audit:

| Artifact | What it says |
|---|---|
| **System/model card** | What the tool does, what it explicitly does *not* do, intended users, known limitations and failure modes. |
| **Data flow + handling doc** | What data goes in, where it's processed, which model provider, retention, whether it trains on their data (get the provider's zero-retention / no-training terms in writing and attach them). |
| **Human-in-the-loop statement** | The tool assists; a human makes the call. This is the single most load-bearing sentence for a lawyer. |
| **Eval + testing summary** | Your golden set, accuracy/failure rates, what you test before each release. Even a modest one beats nothing. |
| **Security posture** | Access controls, logging, tenancy/isolation, secrets, incident response and who they call. |
| **NIST AI RMF mapping** | One page mapping what you already do to Govern / Map / Measure / Manage. Free, US-native, from NIST, and *not* certifiable — which is the point: you can claim alignment honestly without an auditor. |

## What to actually say to them

> ISO 42001 is a voluntary certification, not a legal requirement — nothing in US law obligates it for an internal-use AI tool, and it isn't something any vendor can hold at our stage. What we can give you now is a full AI governance package: system card, data flow and retention terms, our human-in-the-loop design, eval results, security controls, and a NIST AI RMF mapping. If AI governance certification becomes a hard procurement requirement for you down the road, we're open to a roadmap commitment in the contract.

## Where to hold the line vs. where to give

- **Give freely:** documentation, evals, security detail, the AI RMF mapping, and contractual reps (accuracy disclaimers, data-use restrictions, no-training warranty, breach notification, human-review requirement).
- **Consider:** a contractual **commitment** to pursue certification by a date, or on a revenue/headcount trigger. Cheap now, real to them.
- **Push back on:** certification as a condition precedent to signature. It's not achievable on any deal timeline and it's not proportionate to an internal tool.

## The one thing that would change my answer

If the "internal tool" actually touches **hiring, promotion, credit, insurance, housing, or clinical decisions** — even internally — the regulatory picture changes fast (Colorado AI Act, NYC LL144, HIPAA, EEOC/ADA scrutiny). Still not ISO 42001, but then you have real, specific obligations to meet. Also: if they're a **US subsidiary of an EU parent**, their legal may be pre-positioning for EU AI Act pressure from HQ, in which case a roadmap commitment is worth offering unprompted.

If any of that applies, tell me and I'll redo this.
