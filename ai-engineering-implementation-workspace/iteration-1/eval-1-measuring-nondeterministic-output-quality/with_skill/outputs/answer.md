# Measuring ticket-generation quality when the output is non-deterministic

You're right that you can't diff against expected output — and you shouldn't try. String equality is the wrong assertion for LLM output. **Assert properties, not transcripts.** A generated ticket is correct if it satisfies structural and semantic invariants, not if it matches a stored string.

But before you build any of that: your PO is already a measuring instrument you haven't wired up. Start there.

---

## Step 0 (this week): make the PO's review emit a number

She reviews tickets today and forms an opinion. The reason she can't quantify it is that her review isn't recorded. Instrument it and you get a real quality metric in days, before any eval harness exists.

```python
class TicketReview(BaseModel):
    ticket_id: str
    trace_id: str            # links back to the generation run
    reviewer: str            # from auth context, never model output
    action: Literal["accepted", "edited", "rejected"]
    edit_distance: float     # 0.0 = untouched
    reject_reason: Literal["hallucinated", "wrong_scope", "unverifiable_criteria",
                           "duplicate", "missed_requirement", "other"] | None
    reviewed_at: datetime
```

**Edit rate + reject rate is your fit-criteria accuracy proxy.** It's the most honest metric in the system because it's produced by the person who actually knows.

Two design constraints, or the number is garbage:

- **Per-item accept/edit/reject. No "approve all" as the primary action.** A PO rubber-stamping 40 tickets isn't oversight, and it produces a fake 0% edit rate. Automation bias is the named failure here (NIST AI 600-1) and it corrupts your metric before it corrupts your product.
- **Show provenance per ticket** — which requirement lines produced it — so review is targeted, not exhaustive. Cheap disagreement is what makes the signal real.

Watch the *accepted-untouched* rate specifically. If it climbs toward 100%, that's not quality improving; that's your reviewer disengaging.

The `reject_reason` enum is what turns "sometimes wrong" into "23% of rejections are hallucinated tickets, 40% are missed requirements." That tells you which failure mode to engineer against. It's also, mechanically, what generates your golden set (see step 2).

---

## Step 1: the golden set — assert invariants

```
evals/
  golden/
    case_001/
      input/            # the requirement doc (synthetic or de-identified)
      expected.yaml     # assertions, not tickets
  rubrics/              # LLM-judge rubrics, versioned like prompts
  runners/run_offline.py
  datasheet.yaml        # provenance of every case
  reports/
```

```yaml
# evals/golden/case_001/expected.yaml
must_cover_requirements: [REQ-1, REQ-2, REQ-3]   # every req traced to >=1 ticket
must_not_invent: true                            # no ticket without a source requirement
ticket_count: {min: 4, max: 8}                   # merge/split freedom, within bounds
acceptance_criteria:
  per_ticket_min: 2
  must_be_verifiable: true                       # judge-scored: testable as written?
forbidden_content: [PLACEHOLDER, TODO, lorem, "as discussed"]
```

Nothing here breaks when the model rephrases a title. Everything here breaks when the model drops REQ-2 or invents a ticket about a caching layer nobody asked for — which is what "wrong" actually means to your PO.

Two invariants carry most of the weight:

- **Coverage**: every requirement ID appears in ≥1 ticket. Deterministic, exact, and it catches the "missed requirement" failure directly.
- **Groundedness**: every ticket cites the requirement span it came from. Make the model emit that citation as a required field, then *verify it in code* against the source document. A ticket whose cited span doesn't exist is a hallucination you caught for free, no judge needed.

Requirement IDs are the trick that makes all of this deterministic. If your input docs don't have them, a preprocessing pass that assigns stable IDs to requirement statements is the highest-leverage thing you can build — it converts a fuzzy semantic problem into set membership.

---

## Step 2: three metric layers

| Layer | Mechanism | Measures | Trust |
|---|---|---|---|
| **Deterministic** | Code assertions | schema validity, requirement coverage, count bounds, citation validity, forbidden strings, token/latency budgets | Ground truth |
| **LLM-as-judge** | Versioned rubric + judge model | criteria verifiability, faithfulness to source, ticket scope sanity | Calibrated (below) |
| **Human** | `TicketReview` from production | edit rate, reject rate, edit distance | The real signal |

The layers check each other, and that cross-check is the point:

- Judge scores diverging from PO edit rate → your rubric is wrong.
- Deterministic coverage passing while the PO rejects tickets → your golden set is missing a failure mode. **Add the rejected case.**

That last line is the engine. Every ticket your PO rejects becomes a golden case. The suite converges on your actual failure distribution instead of one you imagined.

**Judge calibration is non-negotiable.** Periodically sample N judge verdicts, have the PO score the same outputs blind, report agreement. An uncalibrated judge is a random number generator with authority. Stamp judge model + rubric version on every score — a judge-model upgrade invalidates historical comparisons exactly like an agent-model upgrade does.

---

## Step 3: handle the non-determinism head-on

Non-determinism isn't only an obstacle to measurement — it's a thing to measure.

**Run each golden case K times (K=5).** Report pass rate per case, not pass/fail. A case that passes 5/5 is fixed; 3/5 is your actual reliability, and 3/5 on a coverage assertion is a bug your PO is feeling as "sometimes wrong." Variance *is* the complaint. Setting temperature to 0 hides it rather than fixing it, and doesn't make output deterministic anyway.

Then track two numbers per release: mean score, and the pass rate at K runs. A change that raises the mean while lowering 5/5 consistency is a regression your PO will notice and your averages won't.

**Consistency under paraphrase.** Take a requirement doc, rewrite it (more verbose, terser, different jargon), and assert the two produce equivalently complete backlogs. Same coverage set, similar ticket count. Fragility to phrasing is a very common "it's wrong sometimes" root cause, and it's invisible unless you test for it.

---

## Step 4: evaluate the real system, not a model call

The harness must invoke **the real graph** — same code path, same gateway, same prompt templates, same model IDs, same retry/validation middleware — against a scratch session. No mock model, no bypassed middleware, no notebook calling the API directly.

System behavior ≠ model behavior. If your pipeline is planner → writers → reconcile, most of your defects live in the seams, and a bare model call tests none of them.

Corollary: golden inputs must be realistic in **size and messiness**. A 30-page requirements doc with contradictions and a stale appendix is the deployment condition. A clean 200-word synthetic spec tests nothing your PO cares about.

---

## Step 5: keep it honest in production

Once tracing is in place (every span stamped with `prompt_version`, `model_id`, `trace_id`), sample K% of production generations, run the judge rubrics async, write scores back as trace annotations. Trend judge scores next to the PO's edit rate.

A quality drop with no deploy means drift — a silent model revision upstream, or your input distribution shifting (new team, new doc template). Both are diagnosable *only* because every span carries the model ID and prompt version. If you're not stamping those today, do it before anything else in this document; it's the cheap prerequisite for all of it.

---

## Build order

1. **`TicketReview` instrumentation.** Days. Gives your PO a number this sprint and answers her question directly.
2. **Golden set v1**: 10–15 cases, deterministic layer only (coverage, citation validity, count bounds, schema). Days, not weeks. Catches most regressions.
3. **Judge layer** for verifiability and faithfulness, calibrated against PO-scored samples.
4. **CI wiring**: smoke subset per PR, full suite per release candidate, thresholds set *before* the run. A model-pin bump rides these gates like any other change — it's a release, not a config flip.
5. **Online sampling** once traces land.
6. **Feed rejections back** into the golden set, forever.

---

## What this doesn't cover

- **Cost.** The full suite hits real models K times per case. Budget it; that's why smoke-on-PR / full-on-RC is the standard split.
- **The trace store's data classification.** If traces contain the client's requirement docs, your observability vendor is an egress path. Relevant if those docs are sensitive — different conversation, but don't let it surprise you later.

The reframe to give your PO: you're not asking her *how often* it's wrong. You're asking her to press one of three buttons per ticket, and the system will tell both of you how often it's wrong — with a breakdown by failure mode, and a trend line.
