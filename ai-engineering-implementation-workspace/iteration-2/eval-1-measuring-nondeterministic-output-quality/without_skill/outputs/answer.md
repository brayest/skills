Both halves of your plan will hurt you. Temperature 0 doesn't buy determinism, and it makes you measure a system you don't ship. And 30 cases can't resolve the difference your PO cares about. Here's what to do instead.

## Drop temperature 0

Two problems:

1. **It doesn't actually make output deterministic.** Same prompt, same seed, temp 0 — you still get different tokens run to run. Batching changes the shape of the matmuls, floating-point reduction order isn't associative, MoE routing depends on who else is in your batch. Providers explicitly don't guarantee reproducibility. You'll build the whole harness on "stable numbers," see a diff, and burn a day chasing a phantom regression.
2. **Even if it worked, you'd be measuring the wrong system.** If prod runs at 0.7, an eval at 0.0 tells you about a distribution you never serve. You'd ship a prompt that scores 95% in eval and fails 20% of the time in prod, and you'd have no way to see it coming.

Nondeterminism isn't noise to eliminate. It's the property you're being asked to measure. "Sometimes wrong" *is* the finding — your job is to put a number and a confidence interval on "sometimes."

## Stop diffing, start asserting

Exact-match against an expected ticket is the wrong assertion anyway, even for a deterministic system. Two correct tickets can be worded completely differently. You need to check *properties*, not *strings*.

So decompose "the ticket is wrong" into things you can check independently:

- Does it have a title, description, and acceptance criteria?
- Are the acceptance criteria testable (not "works well")?
- Does it reference only components/services that exist in the input?
- Did it invent a requirement not present in the source?
- Did it drop a requirement that was present in the source?
- Is the scope one ticket, not three smuggled into one?
- Is the estimate/priority field in the allowed enum?

Now "wrong" is a vector, not a boolean. That matters, because your PO can't tell you *how often* it's wrong partly because she can't tell you *what kind* of wrong. When you come back with "12% of tickets hallucinate a component, 8% drop a requirement, 3% have untestable AC," she'll immediately tell you which one she actually cares about — and those get different fixes.

## Get her to label before you build anything

Do not invent 30 test cases from your head. You'll invent the cases your prompt already handles.

Pull 50–100 **real** production inputs and their outputs. Sit with the PO for an hour and have her mark each output good/bad and, for the bad ones, say *why* in her own words. Cluster those "why"s into 5–8 failure modes. That's your taxonomy, and it's grounded in what she actually means by "wrong."

This is the highest-leverage hour in the whole project. Everything downstream is calibrated against those labels.

## Build the graders

Two tiers. Push as much as possible into tier one.

**Tier 1 — deterministic code.** Anything you can check with a parser or a set membership. Schema valid, required fields present, referenced ticket IDs actually exist in the input, no `TODO`/`TBD` in AC, word count sane, priority in enum. These are free, fast, and don't drift. In my experience half of "the output is wrong" collapses into checks like this.

**Tier 2 — LLM judge.** For the genuinely semantic ones: "does this ticket faithfully capture the requirement," "are the AC testable." One judge call per criterion — do *not* ask a judge for a holistic 1–10 score. Holistic scores are mush; they correlate with length and confidence, drift when you touch the judge prompt, and nobody can act on "we went from 7.2 to 6.9." Binary pass/fail per criterion, with a required one-sentence justification, and give the judge the *source requirement* alongside the ticket so it can check faithfulness rather than vibes.

**Then validate the judge.** This is the step everyone skips. Run your judge against the PO's labeled set. If it doesn't agree with her ≥85–90% of the time, you are not measuring ticket quality — you are measuring your judge. Iterate the judge prompt against her labels until it agrees, then freeze it. Keep the labeled set as the judge's own regression test, because you'll change the judge later and you need to know if it moved.

## Size the set properly

30 is too few, and here's the concrete reason. Say the true failure rate is 10%. With n=30, you observe 3 failures, and the 95% confidence interval is roughly **2%–27%**. You cannot distinguish a 10% failure rate from a 25% one. So when you change the prompt and the number moves from 10% to 15%, you have learned nothing — that's inside the noise.

Rough guide for a pass-rate metric:

| n | ±95% CI at ~90% pass rate |
|---|---|
| 30 | ~±11 pts |
| 100 | ~±6 pts |
| 300 | ~±3.5 pts |

Get to **100–200 cases** before you trust a delta, and make sure the set is stratified: mostly the real input distribution (so the number means something to the business), plus a deliberate bucket of the hard cases from your taxonomy (so you can actually detect regressions on the failure modes you're fixing). Keep those as separate slices — don't average them into one number, or a fix that helps the head will mask a regression on the tail.

## Run each case k times

This is the part your temp-0 plan was trying to route around, and it's the part that answers your PO's question directly.

Run every case **k=5 times at production temperature**. Now each case has a pass rate, not a pass/fail, and you get two distinct signals:

- **Aggregate pass rate** (across all n×k runs, with a CI) — "the system produces a correct ticket 87% of the time, ±4." That's the number she's asking for.
- **Per-case consistency** — cases that fail 5/5 are *broken* (prompt or context gap, deterministic fix). Cases that fail 2/5 are *unstable* (the model is on a decision boundary — usually ambiguous input, an underspecified instruction, or a genuinely hard call).

Those two need completely different fixes, and a temp-0 eval would have collapsed them into the same "fail," sent you after the wrong one, and — worse — would have silently reported the 2/5 cases as either pass or fail depending on which side of the coin flip you happened to land on that run.

Report `pass_rate ± CI` per criterion, per slice. Never one scalar.

## Shape of the harness

```python
@dataclass(frozen=True)
class Case:
    id: str
    source_requirement: str   # the real input
    context: dict             # whatever RAG/metadata prod passes
    slice: str                # "prod_sample" | "hard_multiservice" | ...

@dataclass(frozen=True)
class Result:
    case_id: str
    run_idx: int
    criterion: str
    passed: bool
    reason: str

def evaluate(case: Case, output: Ticket, run_idx: int) -> list[Result]:
    results = []
    for check in DETERMINISTIC_CHECKS:      # schema, refs, enums, AC form
        results.append(check(case, output, run_idx))
    for criterion in JUDGE_CRITERIA:        # faithfulness, no-invention, no-omission
        results.append(judge(case, output, criterion, run_idx))
    return results

# n cases x k runs, run concurrently, persist every Result row with
# prompt_version + model_id + timestamp. Aggregate at query time.
```

Persist **every run**, not the aggregate. The moment you only store the summary you lose the ability to ask new questions of old runs, and you will want to — "did the failures cluster on one team's tickets?" is a question you can only answer if you kept the rows. Tag each row with the prompt version and the exact model ID (`claude-sonnet-4-5-20250929`, not `claude-sonnet-4-5`) so a silent model rev doesn't get attributed to your prompt change.

## Then gate it

Once the number is trustworthy, wire it into CI on any change to the prompt, the model pin, or the retrieval layer. Fail the build if aggregate pass rate drops below the CI-adjusted baseline, or if any single criterion regresses beyond noise. That's what turns "our PO thinks it's sometimes wrong" into "we know it's 87% and it can't silently get worse."

## The short version

Keep production temperature. Run 100–200 real cases, 5 times each. Grade with per-criterion assertions (code where possible, a PO-calibrated judge where not). Report pass rate with a confidence interval, sliced by failure mode. Distinguish always-fails from sometimes-fails. Gate it in CI.

The thing to internalize: you don't make a nondeterministic system measurable by forcing it to be deterministic. You make it measurable by sampling it enough times to characterize the distribution — which is the only thing your PO was ever asking about.
