# Evaluation — the harness that proves the product and satisfies MEASURE

**Requirement being implemented:** NIST MEASURE 2.1 (documented test sets/metrics/TEVV tooling),
2.3 (deployment-like conditions), 2.7 (security testing), 2.11 (fairness); ISO 42001 A.6.2.4
(verification & validation); OWASP LLM09 (Misinformation).

This is the highest-leverage file in the pack: output accuracy (for this platform, fit-criteria
accuracy) is the product's core claim *and* the compliance requirement. One harness serves both.
Design it as product infrastructure that emits compliance artifacts, not the reverse.

---

## 1. Structure

```
evals/
  golden/
    product/                    # requirement doc → expected backlog properties
      case_001/
        input/                  # the requirement doc(s), synthetic (see data rules)
        expected.yaml           # assertions, not verbatim tickets
    qa/                         # ticket + code → expected test-case properties
  datasheet.yaml                # provenance of every golden case (artifact #7)
  rubrics/                      # LLM-judge rubrics, versioned like prompts
  runners/
    run_offline.py              # full golden suite against a candidate build
    run_online.py               # sampled production outputs, async
  reports/                      # generated, timestamped, committed or archived
```

**Assert properties, not transcripts.** LLM output is non-deterministic; golden expectations are
structural and semantic invariants, not string equality:

```yaml
# evals/golden/product/case_001/expected.yaml
must_cover_requirements: [REQ-1, REQ-2, REQ-3]     # every requirement traced to ≥1 ticket
must_not_invent: true                               # no ticket without a source requirement
ticket_count: {min: 4, max: 8}                      # merge/split freedom within bounds
fit_criteria:
  per_ticket_min: 2
  must_be_verifiable: true                          # judge-scored: testable as written?
  accessibility_present_for: [REQ-2]                # the a11y scout did its job
forbidden_content: [PLACEHOLDER, TODO, lorem]
```

## 2. Three metric layers

Per NIST's TEVV framing, distinguish what is *measured* from how:

| Layer | Mechanism | Examples | Trust level |
|---|---|---|---|
| **Deterministic** | Code assertions | schema validity, requirement coverage (IDs traced), count bounds, forbidden strings, latency/token budgets | Ground truth |
| **LLM-as-judge** | Rubric + judge model, versioned | fit-criterion verifiability, faithfulness to source (no invention), test-case correctness vs. code | Calibrated (§3) |
| **Human** | Review records from production ([01 §4](01-agent-design.md)) | edit rate, rejection rate, edit distance | The real signal |

The layers check each other: judge scores that diverge from human edit rates mean the judge rubric
is wrong; deterministic coverage that passes while humans reject tickets means the golden set is
missing a failure mode — add the rejected case.

**Judge calibration (§3 of the eval report, and non-negotiable):** periodically sample N judge
verdicts, have a human score the same outputs blind, report agreement. An uncalibrated judge is a
random number generator with authority. Keep the judge model and rubric version stamped on every
score — a judge-model upgrade invalidates comparisons exactly like an agent-model upgrade.

**Fairness (MEASURE 2.11), scoped honestly:** our outputs are tickets and test cases, not decisions
about people, so demographic fairness metrics mostly don't attach. What does: **consistency** —
equivalent requirements phrased differently (verbosity, ESL phrasing, domain jargon) should produce
equivalently complete backlogs. Build paraphrase pairs into the golden set and measure the delta.
Document this scoping decision in the eval report; "we assessed and here is why the metric set looks
like this" is the defensible position.

### A number without a confidence interval is false precision

The question behind most eval work is "how often is it wrong," and the honest answer has error bars.
Two facts that change how you build the suite:

- **Sample size bounds what you can see.** A ~25% failure rate measured on 50 cases resolves to
  roughly ±12 percentage points at 95% confidence. That means a suite of 50 *cannot* distinguish a
  real improvement from 25% to 20% — the intervals overlap completely. If you plan to gate releases
  on eval deltas, size the set for the delta you care about, or accept that small improvements are
  invisible and stop chasing them. Report a bootstrapped CI alongside every pass rate; "82% → 84% on
  n=50" moved nothing and should not be presented as if it did.
- **Non-determinism is part of the measurement, not noise to suppress.** Run each case **K times**
  (K=5 is a reasonable default) and report both the aggregate pass rate and the **reliable-pass
  rate** — the fraction of cases that pass *all K runs*. A case passing 3 of 5 is precisely the
  "sometimes wrong" a reviewer is complaining about, and it is invisible if you run once. Cases with
  a pass rate strictly between 0 and 1 are your highest-ROI fixes: they are usually underspecified
  prompts rather than model failures.

Resist the urge to set temperature to 0 to make the numbers stable. That hides the variance your
users actually experience rather than fixing it, and it measures a system you do not ship.

## 3. Deployment-like conditions (MEASURE 2.3)

The eval harness invokes **the real graph** — same code path, same `LLMGateway`, same redaction,
same models via Bedrock — against a scratch session. No mock models, no bypassed middleware.
Evaluating a prompt in a notebook against `claude-sonnet` directly tells you nothing about what the
deployed system does; the whole point of the graph (planner → parallel writers → reconcile) is that
system behavior ≠ model behavior.

Practical consequences:
- Eval runs happen in CI against a dedicated environment with the same Helm values as staging.
- Golden inputs are realistic in *size and messiness*, not sanitized minimal cases — a 40-page
  requirements doc with contradictions is the deployment condition.
- Cost is real (Bedrock invocations); budget it. A full suite per release candidate and a smoke
  subset per PR is the standard compromise ([06-cicd.md](06-cicd.md)).

## 4. Online evaluation — drift detection

MANAGE 4.1's post-deployment monitoring, implemented as sampled async evals over production traces:

- Sample K% of production operations (trace refs, not copies) → run the judge rubrics → write
  scores back as trace annotations.
- Trend the scores alongside the human edit rate ([04-observability.md](04-observability.md) §4).
  A drop without a deploy means upstream drift: a silent model revision, or the client's input
  distribution shifting (new team, new document style). Both are findable because every span
  carries `model_id` and `prompt_version`.
- **Data rule:** online eval of client data runs inside the client boundary, same as everything
  else that touches it. Scores and aggregates leave; content does not.

## 5. The eval report — generated, not written

Artifact #8 has no published template; ours is a generated document, one per release candidate:

1. **Scope**: agent, code/prompt version (git SHA), model IDs, date.
2. **Test set**: golden-set version, case count, datasheet reference.
3. **Results**: deterministic pass rates, judge scores with rubric versions, deltas vs. previous
   release, regressions called out explicitly (not netted against improvements).
4. **Judge calibration**: agreement rate, sample size, date of last calibration.
5. **Fairness/consistency**: paraphrase-pair deltas, scoping rationale.
6. **Red-team results**: from the [02 §5](02-untrusted-input.md) corpus — pass/fail per category.
7. **Verdict**: promote / block, against thresholds set *before* the run.

Store with the release record ([06-cicd.md](06-cicd.md)). Two years of these, each tied to a git
SHA, is what "verification and validation" (ISO A.6.2.4) looks like to an auditor — and what
"we measure output accuracy, here is the trend" looks like to a CTO-level reviewer.

## 6. Build order

1. **Golden set v1** — 10–15 synthetic product cases + 5–10 QA cases. Assert deterministic layer
   only. This alone catches most regressions and takes days, not weeks.
2. **Judge layer** — faithfulness + verifiability rubrics, calibrated against human-scored samples.
3. **CI wiring** — smoke on PR, full on release candidate, thresholds enforced.
4. **Online sampling** — after tracing ([04](04-observability.md)) lands.
5. **Grow the set from production**: every human-rejected ticket and every incident becomes a
   golden case. The eval suite converges toward the client's actual failure distribution — which is
   the property that makes it persuasive in the room, not just compliant on paper.
