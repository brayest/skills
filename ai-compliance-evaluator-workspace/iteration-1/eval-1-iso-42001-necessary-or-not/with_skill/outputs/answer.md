# Do you need ISO 42001 before they'll sign?

**No.** Nothing obligates it, and you couldn't get it in time even if you wanted to. Certification requires an *audited, running* management system — realistically 6–12 months of accumulated evidence (internal audits, management reviews, monitoring records) before a Stage 2 audit is even passable, plus a two-stage audit and real money. If their legal team is holding a signature on it, they are holding it on something you cannot deliver on any deal timeline. That fact alone reframes the conversation.

## What actually binds you

| Layer | Applies? | Why |
|---|---|---|
| **EU AI Act** | No | US-only deployment. Law, but not your law. Revisit if they ever deploy in the EU. |
| **ISO/IEC 42001** | Not required | Certifiable, but voluntary and contractual-only. Nobody *needs* it; a client can *demand* it. |
| **NIST AI RMF** | Yes, in practice | Voluntary and non-certifiable — but it's the vocabulary US buyers speak, and it's what you should build against now. |
| **Sector law (HIPAA, GLBA, FERPA…)** | **Unknown — this is the real question** | If the tool touches regulated data, *this* is the layer with teeth, not ISO. |

The single most important thing to establish before answering their legal team: **what data goes into this tool, and does it make or influence decisions about people?** An internal tool that summarizes their own engineering docs is a fundamentally different compliance object than one that screens résumés or touches patient records. If there's PHI in scope, HIPAA — not ISO 42001 — is what should be occupying both of you, and a BAA plus a data-flow diagram is a hundred times more relevant than a certificate.

## What's likely really going on

"Do you have ISO 42001?" from a legal team is usually a proxy question. They have been told to ask *something* about AI governance and 42001 is the only name they know. What they are actually trying to answer is:

1. **Where does our data go?** (Does it leave our tenant? Does it train someone's model? Who can see it?)
2. **How do we know the AI isn't making things up?** (What happens when it's wrong, and who's accountable?)

Both have engineering answers, not paperwork answers. A certificate is a slow, expensive, indirect way of implying those answers. You can just *give* them the answers.

## What to hand them instead — days of work, not months

These are cheap, real, and more persuasive to a reviewer than a certificate:

- **Data-flow diagram with the trust boundary drawn on it.** Every byte of their data, where it goes, where it stops. This single artifact answers question #1 and it is the one their security team actually wants. Half a day.
- **System card for the tool.** Models used, prompts, what it does, intended use, **known limitations, and what it must never be trusted to do.** That last field is the most valuable one and the one everyone omits. ~1 day. Doubles as your best client-facing explainer.
- **Eval harness + a first evaluation report.** The proof that the output is accurate. This is the highest-value item on the list — it's NIST AI RMF MEASURE 2.1/2.3, it's ISO 42001 A.6.2.4 if you ever do pursue it, and it's the thing your value case rests on anyway.
- **Event logs / decision traces.** You want these for product reasons regardless. They're also the backbone of every future audit and incident artifact.
- **AI system inventory.** One row per AI component; owner, docs, data sources. An hour.
- **Model/vendor assessment.** One page on your model provider (hosted API? Does it train on your inputs? What's the retention?). Their legal will ask.

That set is roughly a week of work and it's *the same work* your engineering roadmap already wants. It maps cleanly onto NIST AI RMF, which is free, immediate, and — importantly — is the structure ISO 42001 is built on. So none of it is wasted if you certify later.

## Two things to say to their legal team, carefully

**Be precise, not evasive.** Don't say "ISO 42001 isn't necessary." Say: *"We're not certified, and here's why that shouldn't block the signature — plus here's the evidence that answers what the certificate would only imply."* Then show the artifacts. A vendor who hands over a data-flow diagram and an accuracy report is in a stronger position than one who waves a certificate and can't explain either.

**Offer a contractual bridge if they need one.** If their legal genuinely can't get past it, the standard move is contract language rather than certification: data-handling and residency commitments, no-training-on-client-data, incident notification timelines, an audit right, and — if they insist on ISO — a good-faith commitment to build against 42001's structure with a review at renewal. That is a negotiable term. A certificate is not, on this timeline.

## Where the answer would flip

Pursue certification only if: (a) they contractually require it and will wait 6–12 months (rare, and you should test whether it's a real requirement or an unexamined checkbox); or (b) you're going to sell this platform to *many* clients, in which case 42001 becomes a sales asset that pays for itself across deals rather than a tax on one. For a small team, one client, one internal tool, US only — it's the wrong investment right now. Build the artifacts, defer the audit.

## Caveats worth stating

- If this tool touches PHI, financial data, or makes employment/credit/housing/insurance decisions about individuals, come back to me — the analysis changes materially and there may be a layer with actual legal force that neither of you has named yet.
- If their contract has a data-residency clause, that clause is probably stricter than any framework and overrides everything above.
- ISO 42001 is paywalled; the summary above is from certification-body sources, not the standard's text. If you ever do go for it, buy the standard (~CHF 180) rather than implementing from anyone's summary, including mine.
