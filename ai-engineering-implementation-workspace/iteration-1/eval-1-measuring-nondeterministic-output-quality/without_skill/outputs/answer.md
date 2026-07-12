# Measuring quality of non-deterministic ticket generation

Stop trying to diff against expected output. Exact-match is the wrong oracle for open-ended generation — two totally valid tickets can share zero tokens. What you actually want is: **freeze the inputs, not the outputs, and score each run against criteria.**

The whole thing is four moves.

## 1. Make the PO's "sometimes wrong" into a taxonomy

You can't measure "wrong." You measure specific failure modes. Sit her down with 40–50 recent generated tickets and have her mark each one accept/reject, and for every reject write one line on *why*. Don't give her a rubric — you're trying to discover it.

Cluster the "why"s. You'll get something like:

| Failure mode | What it looks like |
|---|---|
| Hallucinated scope | References a service/field/screen that isn't in the source |
| Missing acceptance criteria | Ticket has none, or they're untestable |
| Wrong granularity | One ticket that's really five, or a ticket that's a subtask |
| Dropped requirement | Source said X, ticket doesn't mention X |
| Bad title | Doesn't say what changes |

Two things fall out of this for free: the failure taxonomy, **and your first honest base rate** ("13 of 50 rejected = ~26% ± 12pp"). That alone answers the PO's question well enough to justify the rest of the work.

## 2. Build a golden set of inputs

50–100 cases, sampled from real traffic, deliberately over-weighted toward the failure modes above. Each case is:

```jsonc
{
  "id": "gold-042",
  "input": { /* the exact source doc / requirement / transcript */ },
  "notes": "PO rejected the live run: invented an 'audit log' component",
  "must_mention": ["patient consent", "HL7 ingest"],   // optional hard checks
  "must_not_mention": ["audit log"]
}
```

Note there's **no `expected_output`**. That's the point. The input is frozen; the output is graded.

Sample size matters: at n=50 you can resolve a ~25% failure rate to roughly ±12pp. At n=100, ±9pp. If the PO wants to see a 5pp improvement from a prompt change, 50 cases won't show it. Budget accordingly.

## 3. Grade with a layered scorer

Three layers, cheapest first.

**Layer 1 — deterministic checks.** These are free, instant, and catch a shocking amount:
- Schema valid (title, description, AC, story points present)
- ≥1 acceptance criterion, each in a testable form
- No placeholder text (`TODO`, `[insert]`, `Lorem`)
- Every entity named in the ticket appears in the source input (cheap hallucination proxy — string/fuzzy match against a whitelist of components pulled from the source)
- Title < N chars, not a restatement of the description

**Layer 2 — LLM-as-judge, referenced against the input.** Not against a golden output. The judge gets the source doc + the generated ticket + a rubric of **binary** questions:

```
For each, answer YES or NO with a one-sentence justification:
1. Does every requirement in SOURCE appear in the TICKET?
2. Does the TICKET introduce any component, field, or system not present in SOURCE?
3. Are the acceptance criteria testable (a QA engineer could pass/fail them without asking a question)?
4. Is this exactly one unit of work?
5. Does the title state what changes?
```

Binary criteria, one at a time. Do **not** ask for a 1–5 "quality score" — judges anchor to 4, the variance swamps your signal, and nobody can act on "3.2 → 3.4".

**Layer 3 — calibrate the judge.** This is the step everyone skips and it's what makes the number credible. Run the judge over the 50 tickets the PO already labeled in step 1. Compute agreement (Cohen's kappa, or just confusion matrix). If the judge disagrees with the PO, **the rubric is wrong, not the PO** — rewrite the criteria and re-run. Iterate until kappa > ~0.6. Now when you show the PO "our failure rate is 18%", she has a reason to believe it, because she's seen the judge reproduce her own calls.

## 4. Handle the non-determinism head-on — run k times

This is your actual question. Don't fight the variance, measure it.

Run each golden input **k=5 times** at production temperature. Now a case isn't pass/fail, it has a *pass rate*:

```python
# per case
case_pass_rate = sum(grade(gen(case.input)) for _ in range(5)) / 5
# headline metric
suite_score = mean(case_pass_rate for case in golden_set)
```

Report three numbers:

- **Suite pass rate** — `mean(case_pass_rate)`. The headline. "82% of generated tickets meet the bar."
- **Reliable-pass rate** — % of cases that pass **all 5** runs. This is the number the PO actually cares about, because it's "would I trust this ticket without reading it."
- **Flaky cases** — cases with pass rate strictly between 0 and 1. These are gold: they're the inputs where the prompt is underspecified. Fix these before you touch the model.

Bootstrap a 95% CI over the suite score so you don't chase noise. A prompt change that moves 82% → 84% on n=50 moved nothing.

## Sketch of the harness

```python
@dataclass(frozen=True)
class GoldenCase:
    id: str
    source: str
    must_mention: list[str]
    must_not_mention: list[str]

def evaluate(case: GoldenCase, k: int = 5) -> CaseResult:
    runs = [generate_ticket(case.source) for _ in range(k)]
    grades = []
    for ticket in runs:
        checks = deterministic_checks(ticket, case)      # layer 1
        if not checks.all_pass:
            grades.append(Grade(passed=False, reason=checks.first_failure))
            continue                                      # don't pay for a judge on a broken ticket
        grades.append(judge(source=case.source, ticket=ticket))  # layer 2
    return CaseResult(case_id=case.id, grades=grades)

# suite
results = [evaluate(c) for c in golden_set]              # parallelize; this is embarrassingly parallel
report(results)   # suite pass rate + CI, reliable-pass rate, per-criterion breakdown, flaky list
```

The per-criterion breakdown is what makes this actionable — "we fail criterion 3 (untestable AC) on 22% of runs" is a prompt fix, not a vibe.

## Wire it up

- **CI gate.** Any prompt edit, model version bump, or retrieval change runs the suite. Block the merge on a regression outside the CI. Pin the model ID explicitly — a silent provider-side model update is exactly the kind of thing this catches.
- **Production feedback loop.** Put a thumbs-down + one-line-reason on every generated ticket in the PO's UI. Every rejection gets promoted into the golden set. In three months your golden set is the real distribution, not your guess at it.
- **Pairwise for close calls.** When absolute scores are too noisy to compare prompt A vs B, show the judge both outputs for the same input and ask which is better. Pairwise preference is far more sensitive than absolute scoring for A/B decisions.

## The order to do this in

Step 1 alone (PO labels 50 tickets) takes an afternoon and gives you a number you can put in front of her this week. Everything after that is about making the number cheap to recompute so you can actually improve it. Don't build the harness before you've done the labeling — you'll build the wrong rubric.
