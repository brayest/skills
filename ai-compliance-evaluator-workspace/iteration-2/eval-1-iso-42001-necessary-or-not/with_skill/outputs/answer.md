# ISO 42001 — do you need it?

**No.** Nothing requires it, and both of their counsel's supporting claims are wrong. But don't just say no — say no and hand them something better, or you lose the argument on optics.

## What actually binds you

| Layer | Applies to you? |
|---|---|
| **EU AI Act** (law, penalties to €35M / 7% turnover) | **No.** US-only, internal-facing. No EU nexus, no obligation. |
| **HIPAA / sector law** | Only if the tool touches PHI or a regulated decision. You haven't said it does — confirm. |
| **ISO/IEC 42001** (certifiable management-system standard) | **Voluntary.** No law requires it. It is a procurement preference, not a legal gate. |
| **NIST AI RMF** (voluntary, non-certifiable) | Your best play — free, immediate, and the vocabulary US buyers already speak. |

Order matters: the only layer that can kill a deal or draw a penalty is law and contract. 42001 is neither. It is a thing their counsel would *like* to see, which is a negotiation, not a requirement.

## The two claims from their counsel — both wrong

**"It gives us EU AI Act coverage down the line."** It does not. **ISO 42001 confers no presumption of conformity with the EU AI Act.** They are different legal instruments: 42001 is a *management-system* standard (how you run the org), the Act is *binding product regulation* (what the system must be). Thematic overlap is real — commonly estimated 40–50% on risk management, data governance, transparency — but passing one discharges nothing under the other. Presumption of conformity will come from harmonized EN standards from **CEN-CENELEC JTC 21** once cited in the Official Journal, and there is reporting that the Commission asked for a *separate* AI-Act-specific QMS standard precisely because 42001's scope doesn't align with the Act's high-risk QMS requirement. If you want to be gracious about it: 42001 is useful *groundwork* for a future EU posture. It is not coverage, and nobody should be writing "coverage" into a contract.

**"Fast-track it in a quarter if we throw money at it."** Structurally impossible. Certification is a two-stage audit. Stage 1 reviews your documents. **Stage 2 tests whether the management system has actually been operating** — sampled Annex A controls, interviews with control owners, and evidence from Clauses 8–10: internal audit reports, management review minutes, monitoring records, corrective actions. Those are *records that accumulate over time*. Money buys consultants who write policies fast; it cannot manufacture a history of the PDCA loop having turned. Realistically you need **6–12 months of a running AIMS** before a Stage 2 is passable. A team that shows up in month three with a beautiful binder and no operating evidence fails — that is the classic failure mode auditors are trained to look for.

Worth also flagging: the standard is paywalled (~CHF 180). Anyone quoting you a quarter-long timeline has probably not read Clause 9.

## What they're actually asking

Strip the framing and a client's legal team wants three answers, none of which a certificate provides:

1. **Where does our data go?**
2. **How do we know the AI isn't making things up?**
3. **Who is accountable when it is?**

Those have engineering answers, not paperwork answers. Give them the evidence directly and the certificate stops being interesting.

## The counter-offer (weeks, not quarters)

Propose this as your governance package, and offer it *in writing in the contract* as an alternative to a 42001 precondition:

**Days:**
- **AI system inventory** — one row per AI component: owner, documentation, incident-response plan, data dictionary, source link. ~1 hour while it's still one or two rows.
- **System card** for the tool — models used, prompts, what the system does, intended use, known limitations, and **what it must never be trusted to do**. That last field is the one everyone leaves out and the one that buys the most credibility. ~1 day, and it doubles as the client-facing explainer.
- **Data-flow diagram with the boundary drawn on it.** This single artifact answers question #1 and is what their security team actually wants. ~half a day.

**Weeks:**
- **Eval harness + a first evaluation report.** The highest-value item on the list — it is the only thing that answers question #2 with a number instead of an assurance. You were going to build this anyway to know the tool works.
- **Event logs / decision traces.** Product need and compliance artifact, one build.
- **Least-agency review of the tool's permissions** — scope what the AI can read and write to what the task needs.
- **AI risk register + an impact assessment** for the system.
- **Incident log and response plan.**

That set satisfies the substance of ISO 42001's Clause 6 and Annex A.6/A.7, maps cleanly to NIST AI RMF (GOVERN 1.6, MAP 1.1/5.x, MEASURE 2.1/2.3, MANAGE 4.1/4.3), and gives their counsel something to attach to the file. The honest framing to them: *"Doing AI RMF properly gets you most of the way to 42001's substance and none of the way to its certificate. We're offering you the substance now instead of the certificate in a year."*

## Contract language, if they won't drop it

Don't accept it as a condition precedent to signature. Offer, in descending order of what you'd concede:

1. **Evidence in lieu** — the artifact package above, delivered on a schedule, with a right for them to review it.
2. **Commitment clause** — "Vendor will maintain an AI management system aligned to ISO/IEC 42001 and will pursue certification within N months of [trigger]," where the trigger is something real, like the tool going beyond internal use or the contract crossing a value threshold.
3. **Certification as a milestone**, funded — if they genuinely need the certificate, it's a line item in the SOW, not a free precondition. A small team's 42001 programme is real money and 6–12 months of someone's calendar. Price it.

## Before you send anything, confirm three things

- **Does the tool make or influence decisions about people?** (hiring, performance, credit, care, access). This is the hinge. If yes, the impact-assessment burden goes way up and their counsel's instincts are more defensible than I'm giving them credit for.
- **Does it touch PHI or other regulated data?** If yes, HIPAA is the layer with teeth and it should be the first thing you address — not 42001.
- **Is the client themselves ISO 27001 / HITRUST certified?** If so, the real driver is probably their *supplier management* clause, and what they need is evidence mappable into their own assessment — not a certificate from you. That's a much cheaper conversation, and it's usually the actual answer.

Also worth a direct question to their counsel: **is this a line item on a vendor questionnaire, or a considered requirement?** Nine times out of ten it's the former, and the honest counter-offer above closes it.

---

*Caveat: ISO/IEC 42001 and 42005 are paywalled standards. The above describes their structure from certification-body sources. If you do decide to pursue certification, buy the standard before doing any implementation work — don't build from summaries, including this one.*
