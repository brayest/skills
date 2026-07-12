# NIST AI Risk Management Framework (AI RMF 1.0)

**What it is:** NIST AI 100-1, released January 2023. Voluntary guidance for incorporating
trustworthiness into the design, development, use, and evaluation of AI systems.
<https://www.nist.gov/itl/ai-risk-management-framework>

**What it is not:** a checklist, a control catalogue, or a certification. NIST never introduces a
certification mechanism anywhere in the Framework, the Roadmap, or the Playbook. Nobody can "certify"
us against AI RMF, and any vendor claiming to is selling something else. You demonstrate AI RMF
adoption through **artifacts**, not a certificate.

That property is exactly why it is the right thing for us to adopt *first*: zero gate, immediate
structure, and it is the vocabulary US federal and healthcare buyers already use.

---

## 1. The seven characteristics of trustworthy AI

Everything in the framework serves these. They are the "what good looks like" list:

1. **Valid and reliable** — it works, and keeps working. (The foundation; the others are meaningless
   without it.)
2. **Safe** — it does not endanger life, health, property, or environment.
3. **Secure and resilient** — it withstands attack and degrades gracefully.
4. **Accountable and transparent** — someone owns it, and its existence and behaviour are visible.
5. **Explainable and interpretable** — its mechanism and its meaning can be conveyed.
6. **Privacy-enhanced** — anonymity, confidentiality, and control are preserved.
7. **Fair, with harmful bias managed** — equity is addressed; bias is measured, not assumed absent.

NIST is explicit that these **trade off against each other** — optimizing explainability can cost
accuracy; maximizing privacy can cost fairness measurement (you cannot measure bias across a
protected class whose data you refused to collect). The framework asks you to make those trade-offs
*deliberately and on the record*, not to pretend they do not exist.

**For an agentic delivery platform:** #1, #4, and #6 dominate. Output accuracy (e.g. fit-criteria
accuracy) *is* validity — and typically the client's core concern. Transparency is the product
thesis of governed AI. Privacy is the HIPAA constraint.

---

## 2. The four core functions

<https://airc.nist.gov/airmf-resources/airmf/5-sec-core/>

| Function | Question it answers |
|---|---|
| **GOVERN** | Who is accountable, under what policy, with what risk tolerance? |
| **MAP** | What is this system, in what context, and what could it do to whom? |
| **MEASURE** | How do we test and quantify that — and keep testing? |
| **MANAGE** | What do we do about what we found, and how do we respond when it goes wrong? |

**GOVERN is cross-cutting** — NIST describes it as "infused throughout" and as the enabler of the
other three. It is not a phase you complete. The intended sequence is: stand up GOVERN, then MAP →
MEASURE → MANAGE, iterating and cross-referencing.

**Application is selective by design.** NIST states that users may apply the functions "as best suits
their needs... based on their resources and capabilities" — you may adopt a subset of categories and
subcategories. A one-engineer platform team is *expected* to scope down. Doing so is compliant use,
not cutting corners.

### Subcategories we can cite by ID

These were verified against the Playbook. They are the ones that map directly onto obligations we
already have. (The full Core has many more; these are the load-bearing ones for this platform.)

| ID | Requirement | Why it binds us |
|---|---|---|
| **GOVERN 1.1** | Legal and regulatory requirements are understood, managed, documented | HIPAA/HITRUST. Also the client's own AI policy, however vague. |
| **GOVERN 1.6** | Mechanisms are in place to **inventory AI systems**, resourced by risk priority | We need an AI system registry. Two agents = two entries, minimum. |
| **GOVERN 6.1** | Policies for **third-party** AI: transparency, training data/algorithm disclosure, testing | Bedrock, Sonnet/Haiku, any model we call. |
| **GOVERN 6.2** | Contingency plans for high-risk third-party failures; redundancy | Bedrock outage / model deprecation. Cloud-agnostic design already partly serves this. |
| **MAP 1.1** | Document intended purpose, context of use, **and limitations** | The "what this agent must never be trusted to do" statement. |
| **MAP 4.1** | Map technology and legal risks, including third-party data or software | |
| **MAP 5.1 / 5.2** | Document likelihood and magnitude of impacts; engage stakeholders regularly | The client's POs and QA engineers — the people whose work the agents shape — are the stakeholders. |
| **MEASURE 2.1** | **Test sets, metrics, and TEVV tooling are documented** | Cites model cards and datasheets for datasets as the accepted formats. |
| **MEASURE 2.3** | Performance measured under conditions **similar to deployment** | Evaluating on toy examples does not count. |
| **MEASURE 2.7** | Security tests and metrics tracked, **including red-teaming** | Prompt injection testing lives here. |
| **MEASURE 2.11** | Fairness assessed: name the harm types, name the affected groups, quantify | |
| **MANAGE 4.1** | **Post-deployment monitoring** — periodic red-teaming, dataset-change monitoring, drift | Catches degradation, adversarial attacks, near-misses. |
| **MANAGE 4.3** | **Incident tracking** — reports, severity, response, version history | NIST points at the AI Incident Database and AIAAIC repository as models. |

Note: NIST does **not** name a "risk register" as a Core artifact. That is an implementation
convention (a good one) that organizations build to operationalize GOVERN and MAP. Vendors present it
as an AI RMF requirement; it is not.

---

## 3. The Playbook — where the actual actions live

<https://airc.nist.gov/airmf-resources/playbook/> · PDF, CSV, Excel, JSON exports available.

For every subcategory, the Playbook gives four things:

- **About** — context.
- **Suggested Actions** — concrete, voluntary steps.
- **Transparency and Documentation** — self-interrogation prompts. These are the most useful part:
  they are literally the questions an auditor or a client's security reviewer would ask. E.g. under
  GOVERN 1.1: *"Has the system been reviewed for its compliance to applicable laws, regulations,
  standards, and guidance?"*
- **References** — external sources.

NIST's own framing: the Playbook is *"neither a checklist nor set of steps to be followed in its
entirety"*; borrow "as many – or as few – suggestions as apply."

**Practical use for us:** export the Playbook as CSV, filter to the ~13 subcategories above, and use
the Transparency & Documentation prompts as the question set for our own gap analysis. That *is* the
gap analysis. Google DeepMind's submission to NIST is exactly this — a spreadsheet mapping their
posture against AI RMF subcategories, and it is a reusable template:
<https://airc.nist.gov/docs/Template_Google_DeepMind_gap_analysis-NIST_AIRMF_1.0.xlsx>

---

## 4. Profiles — current vs. target

<https://airc.nist.gov/airmf-resources/airmf/6-sec-profile/>

- A **Current Profile** states how AI is managed today and the risks that follow.
- A **Target Profile** states the outcomes we want.
- The delta between them "reveals gaps to be addressed" and becomes a prioritized, resourced action
  plan.

This is a genuinely cheap and high-value exercise, and it is the closest thing AI RMF has to a
deliverable. NIST does not publish a filled-in example; Georgetown CSET publishes a usable template
(with fields — stakeholder, lifecycle stage, priority — that are CSET's additions, not NIST's):
<https://cset.georgetown.edu/wp-content/uploads/NIST-AI-RMF-Profile-Template.pdf>

Real submitted profiles worth reading: City of San Jose (a filled playbook spreadsheet), and the PEAT
inclusive-hiring framework. <https://airc.nist.gov/airmf-resources/usecases/>

---

## 5. The Generative AI Profile (NIST AI 600-1) — the part that actually applies to us

Released 26 July 2024. <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>

This is the companion that takes AI RMF from "AI in general" to "the thing we are building." It
catalogues **12 GenAI-specific risks** and maps **200+ suggested actions** onto GOVERN/MAP/MEASURE/
MANAGE.

The 12 risk categories include: **confabulation (hallucination)**, **data privacy**, **information
security**, **information integrity**, **harmful bias and homogenization**, **data poisoning**,
**intellectual property**, **human-AI configuration** (over-reliance, automation bias),
**value chain and component integration**, **environmental impact**, **dangerous/violent/hateful
content**, and **CBRN uplift**.

> Confidence note: the 12 are named consistently across sources but the exact canonical wording of
> each should be taken from the PDF before it goes in a client deliverable. CBRN and a couple of
> others are plainly irrelevant to a ticket-writing agent — say so explicitly in our profile rather
> than silently dropping them. "Assessed, not applicable, here's why" is a stronger audit position
> than omission.

The ones that are unambiguously ours: **confabulation** (a hallucinated fit criterion is the exact
failure mode the client fears), **human-AI configuration** (a PO rubber-stamping generated tickets is
automation bias, and it is the risk that quietly destroys the value case), **data privacy**,
**information security**, and **value chain** (Bedrock).

AI 600-1 organizes mitigation around four themes worth stealing wholesale as our headings:
**Governance, Content Provenance, Pre-deployment Testing, Incident Disclosure**.

---

## 6. Related NIST publications we should be using

| Doc | What it gives us |
|---|---|
| **SP 800-218A** — Secure Software Development Practices for Generative AI (July 2024) <https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-218A.pdf> | Extends the SSDF with AI-specific practices. Explicitly addresses *system producers building on foundation models* — that is exactly us. See [05-engineering-controls.md](05-engineering-controls.md). |
| **AI 100-2e2025** — Adversarial ML taxonomy <https://csrc.nist.gov/pubs/ai/100/2/e2025/final> | Attack taxonomy: evasion, poisoning, privacy, misuse — for both predictive and generative AI. |
| **Crosswalks** <https://airc.nist.gov/airmf-resources/crosswalks/> | Community-submitted mappings to ISO 42001, ISO 23894, ISO 42005, EU AI Act, and others. See [03-crosswalk.md](03-crosswalk.md). |

---

## 7. What "doing AI RMF" actually means for this team

Concretely, and in the order I'd do it:

1. **An AI system inventory** (GOVERN 1.6). Per the Playbook, each entry holds: system documentation,
   incident response plan, data dictionaries, links to source, and named AI-actor contacts. Two
   entries today: Product agent, QA agent.
2. **A Current/Target Profile** over the ~13 subcategories above. One spreadsheet. This is the gap
   analysis and the roadmap in one artifact.
3. **A GenAI risk register** seeded from AI 600-1's 12 categories, with "not applicable + rationale"
   allowed and encouraged.
4. **Model cards** for each agent — the Playbook names them under MEASURE 2.1 as the accepted format.
5. **An eval harness** (MEASURE 2.1, 2.3). This is not a compliance chore we bolt on; it is the same
   work as proving output accuracy, which is the client's core concern and the value case. The
   compliance framing just pays for it twice.
6. **Red-team results** for prompt injection (MEASURE 2.7).
7. **Drift/quality monitoring and an incident log** (MANAGE 4.1, 4.3).

Items 5 and 7 are the ones we do not have yet, and they are the ones that both the compliance story
and the product story depend on. That convergence is the argument for doing them now rather than
after the pilot.
