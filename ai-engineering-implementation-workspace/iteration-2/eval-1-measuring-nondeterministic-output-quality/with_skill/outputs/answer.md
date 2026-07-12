# Measuring "sometimes wrong" on non-deterministic output

Your instinct to build a test set is right. The two design choices around it — temperature 0 and n=30 — will both quietly defeat the thing you're trying to measure. Fix those and the rest falls out.

## Don't set temperature to 0

Temperature 0 makes the *numbers* stable, not the *system* stable. You'd be measuring a configuration you don't ship, and the variance your PO is complaining about is precisely the thing you'd be suppressing. "Sometimes wrong" is a statement about run-to-run variance. Deleting the variance from the measurement means you can no longer see the bug.

Ship temperature stays ship temperature in the eval. You get stability from **repetition**, not from determinism: run each case **K times** (K=5 is a fine default) and report two numbers.

- **Aggregate pass rate** — passes / (cases × K). The headline.
- **Reliable-pass rate** — fraction of cases that pass *all K runs*. This is the number that maps to your PO's complaint.

A case that passes 3 of 5 is literally "sometimes wrong." Run once and it's invisible; it shows up as a coin flip in your pass rate and you'll chase it as noise. Cases with a per-case pass rate strictly between 0 and 1 are your highest-ROI queue — they're almost always an underspecified prompt (the model is filling a gap you left, differently each time), not a model capability failure. Fixing those is cheap and it's usually most of the complaint.

## Don't diff against expected output — assert properties

You can't string-match ticket text, and you shouldn't try. Golden expectations are structural and semantic invariants — what must be *true* of a correct backlog, not what it must *say*.

```yaml
# evals/golden/product/case_012/expected.yaml
must_cover_requirements: [REQ-1, REQ-2, REQ-3]   # every requirement traced to >=1 ticket
must_not_invent: true                             # no ticket without a source requirement
ticket_count: {min: 4, max: 8}                    # merge/split freedom, within bounds
acceptance_criteria:
  per_ticket_min: 2
  must_be_verifiable: true                        # judge-scored
forbidden_content: [TODO, PLACEHOLDER, lorem, "as appropriate"]
```

Three layers, and they check each other:

| Layer | Mechanism | Examples | Trust |
|---|---|---|---|
| Deterministic | Code assertions | schema valid, requirement coverage (IDs traced), count bounds, forbidden strings, token/latency budget | Ground truth |
| LLM-judge | Versioned rubric + judge model | is this acceptance criterion actually testable as written? is this ticket faithful to the source, or invented? | Only as good as its calibration |
| Human | Review records from prod | edit rate, reject rate, edit distance | The real signal |

Build the deterministic layer first. It's days of work, no judge infrastructure, and it catches most regressions. Add the judge only for the properties you genuinely cannot assert in code (verifiability, faithfulness).

**If you add a judge, calibrate it.** Periodically sample ~30 judge verdicts, have a human score the same outputs blind, and report agreement. An uncalibrated judge is a random number generator with authority. Stamp the judge model ID and rubric version on every score — a judge-model upgrade invalidates comparisons exactly like an agent-model upgrade does.

## n=30 is too small for what you'll want to do with it

Binomial error bars are brutal at these sizes. A 20% failure rate measured on 30 cases has a 95% CI of roughly ±14 points — your true failure rate is somewhere in 6%–34%. That set can tell you "it's bad" (which your PO already told you) but it *cannot* tell you whether last week's prompt change helped. "23% → 19% on n=30" moved nothing and must not be reported as if it did.

Two honest options:

- **Size for the delta you care about.** If you want to detect a 5-point improvement, you need low hundreds of cases, not 30.
- **Keep 30, and use it as a regression tripwire only** — big breakages, not tuning. Be explicit about that in the room so no one gates a release on a 4-point move.

Report a bootstrapped confidence interval next to every pass rate. It's ten lines of code and it's the difference between a metric and a vibe.

Also: K=5 reps do not buy you sample size. 30 cases × 5 runs is still 30 independent cases; the reps measure *reliability per case*, not *coverage of the input distribution*. Two different axes, both needed.

## Run the real system, not a bare model call

The eval must invoke the actual code path — same graph, same retrieval, same middleware, same model IDs, real (not sanitized) inputs. System behavior ≠ model behavior. A prompt that scores well in a notebook tells you nothing about the pipeline you ship. And make the golden inputs realistic in size and messiness: a 40-page requirements doc with internal contradictions *is* the deployment condition. A clean 1-page synthetic spec is not.

## The runner

```python
# evals/runners/run_offline.py
import asyncio, statistics
from collections import defaultdict

K = 5

async def run_case(case, k):
    result = await generate_backlog(case.input, session=scratch_session())  # the REAL graph
    checks = deterministic_checks(result, case.expected)      # dict[str, bool]
    checks |= await judge_checks(result, case.expected, rubric_version=RUBRIC_V)
    return CaseRun(case_id=case.id, k=k, checks=checks, passed=all(checks.values()),
                   model_id=result.model_id, prompt_version=result.prompt_version)

async def main(cases):
    runs = await asyncio.gather(*[run_case(c, k) for c in cases for k in range(K)])

    by_case = defaultdict(list)
    for r in runs:
        by_case[r.case_id].append(r.passed)

    aggregate     = statistics.mean(r.passed for r in runs)
    reliable      = statistics.mean(all(v) for v in by_case.values())
    flaky         = {cid: statistics.mean(v) for cid, v in by_case.items()
                     if 0 < statistics.mean(v) < 1}          # <-- the work queue
    per_check     = {name: statistics.mean(r.checks[name] for r in runs)
                     for name in runs[0].checks}             # <-- which failure mode

    report(aggregate=aggregate, ci=bootstrap_ci(by_case),
           reliable_pass=reliable, flaky=flaky, per_check=per_check)
```

`per_check` is what turns "sometimes wrong" into something actionable. "17% of runs invent a ticket with no source requirement; 31% produce acceptance criteria the judge rules untestable" is a sprint. "The tickets are sometimes wrong" is not.

## The fastest path to an actual number is not the eval suite

Your PO can't tell you how often because nothing is recording her. **Instrument the review step.** Per-ticket accept / edit / reject, with the reviewer, timestamp, and edit distance:

```python
class TicketReview(BaseModel):
    ticket_id: str
    reviewer: str                                    # from auth context, never from the model
    action: Literal["accepted", "edited", "rejected"]
    edit_distance: float                             # 0.0 = untouched
    reviewed_at: datetime
```

Two weeks of this gives you the real failure rate on the real input distribution, from the person who actually defines "wrong" — and it costs less than the eval harness. Caveats that matter: no "approve all" as the primary action (a rubber stamp records 0% failure and teaches you nothing), and a climbing accepted-untouched rate with no spot checks is an automation-bias alarm, not a quality win.

Then close the loop: **every rejected ticket becomes a golden case.** Your suite converges on the client's actual failure distribution instead of the one you imagined, and it grows past n=30 on its own.

## Order of work

1. Instrument review (accept/edit/reject + edit distance). Ships this week, gives you the number your PO can't.
2. Golden set v1: 10–15 cases, deterministic assertions only, K=5, real graph, ship temperature. Report aggregate + reliable-pass + per-check + CI.
3. Triage the flaky band (0 < pass rate < 1). Expect prompt underspecification. This is where the complaint actually lives.
4. Judge layer for verifiability/faithfulness, calibrated against human-scored samples.
5. CI: smoke subset per PR, full suite per release candidate, thresholds set *before* the run. A model pin bump rides the same gate — it's a release, not a config flip.

## Not covered

Where eval inputs and traces live is a data-boundary question, not an eval question — if the requirement docs are client data, golden inputs need de-identification or synthesis, and the trace/report store inherits their classification. Worth resolving before you start copying real requirement docs into `evals/golden/`.
