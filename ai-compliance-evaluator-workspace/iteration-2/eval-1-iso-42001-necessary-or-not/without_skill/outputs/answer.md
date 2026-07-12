# ISO 42001: do you need it to sign?

**No.** Nothing about your situation legally requires ISO/IEC 42001. It's a voluntary management-system standard — no US law, and no EU law, mandates it. If it becomes a blocker, it's because *their procurement policy* made it one, not because of regulation. That's a negotiation, not a compliance problem.

Their counsel is wrong on both of the specific claims.

## "It gives us EU AI Act coverage down the line"

It doesn't. Two separate errors:

1. **The Act doesn't apply to you today.** Territorial scope (Art. 2) is: providers placing AI systems on the EU market, deployers established in the EU, or providers/deployers outside the EU whose system *output is used in the EU*. US-only company, US-only client, internal tool. No EU nexus, no obligations. Nothing to "cover."

2. **ISO 42001 is not a conformity route for the AI Act.** Certification to 42001 gives you **zero presumption of conformity**. Presumption of conformity comes only from *harmonized standards* cited in the Official Journal — those are being drafted by CEN-CENELEC JTC 21 and are not the same document. ISO 42001 is an AIMS (governance/management system, ~ISO 27001 in shape). The Act's Art. 17 QMS requirement partially overlaps with it, but the substantive load — Art. 9 risk management, Art. 10 data governance, Art. 11/12 technical documentation and logging, Art. 14 human oversight, Art. 15 accuracy/robustness, plus conformity assessment and registration — is not satisfied by holding a 42001 certificate.

So: 42001 would be *useful scaffolding* if you ever went into the EU with a high-risk system. It is not "coverage," and buying it now for a hypothetical future is paying years early for a partial discount.

Also worth saying out loud: even if the EU nexus appeared, an internal productivity/AI tool is very likely limited- or minimal-risk under Annex III, meaning transparency obligations and not much else. The high-risk machinery only bites in specific domains (employment/HR screening, credit, education, biometrics, critical infrastructure, etc.). If your tool touches hiring or worker evaluation, tell me — that changes the answer.

## "Fast-track it in a quarter if you throw money at it"

Not really. Certification requires an AIMS that has actually been *operating* and producing records: risk register, AI impact assessments, defined roles, supplier controls, at least one internal audit cycle and one management review, then a Stage 1 (documentation) and Stage 2 (implementation) audit by an accredited certification body. You cannot buy the evidence trail; you have to run it.

Realistic ranges for a small team:

| Starting point | Realistic time to certificate |
|---|---|
| Already have ISO 27001 running | ~4–6 months |
| No existing ISMS | ~9–12 months |
| "Throw money at it" | Compresses consultant hours, not audit cycles or the operating-evidence window |

Money buys you a consultant to write the SoA and the policy set. It does not buy you Stage 2 passing on records that don't exist yet, and accredited-CB availability for 42001 is still a scheduling constraint. Budget realistically $40k–$100k+ all-in for a small team (consultant + CB + internal time), plus annual surveillance audits forever. That is a meaningful recurring tax for a company your size.

## What their legal team actually wants

Almost always: risk transfer and a defensible answer to "what did you do to make sure this AI thing doesn't hurt us." A certificate is just the cheapest proxy for that. Give them the substance directly:

- **NIST AI RMF alignment** — free, US-native, the thing US counsel actually recognizes. Map your practices to Govern/Map/Measure/Manage and hand them a 3–5 page summary.
- **A model/system card** for the tool: intended use, out-of-scope uses, data sources, known failure modes, eval results.
- **Data handling commitments in the contract**: no training on their data, retention limits, subprocessor list (which model provider, which region), zero-data-retention terms with your inference provider if you can get them.
- **Human oversight and an acceptable-use policy** for the tool, in writing.
- **Eval/testing evidence** — even a modest golden-set eval report beats a certificate for a technical reviewer.
- **SOC 2 Type II**, if you have it or can get it. For a US-only internal tool this is far more likely to be what their security org *really* cares about, and it's the more standard ask.

Then, if they still push: offer a **contractual commitment** rather than a condition precedent — "we will achieve ISO 42001 certification within 18 months of contract signature, with a right-to-audit and a service credit if we miss." That unblocks the signature today and defers the spend until the revenue is real.

## What I'd do

Go back and ask one question: **is ISO 42001 a hard requirement in their written vendor policy, or is it their counsel's preference?** Ask for the policy clause. Nine times out of ten there is no clause, and the ask evaporates once you hand over the NIST AI RMF summary, the model card, and solid contractual data terms.

Pursue 42001 when it's a repeated blocker across multiple enterprise deals — i.e., when it's a sales investment with a return — not because one lawyer floated it in one review.
