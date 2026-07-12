# Prompt Engineering & Structured Output

Source grounding: CCA-F Domain 3 (Prompt Engineering & Structured Output, 20% of the exam); Anthropic engineering guidance on tool use for structured output.

## Vague adjectives are the root cause of most "the model is unreliable" complaints

An instruction like "review this PR carefully" or "check this thoroughly" has no shared, checkable definition. The model has to interpret "careful," and it will interpret broadly — pattern-matching anything remotely cautionary — which is exactly why such prompts produce a flood of false positives almost immediately.

**The fix**: replace every evaluative adjective with a numbered list of categorical rules, each one answerable yes/no by reading the input directly — no judgment call required.

- Vague: "review carefully for problems."
- Checkable: "Flag if any function exceeds 40 lines. Flag if a new third-party dependency is added. Flag if a public type signature is removed."

This single change is the highest-leverage fix in this whole domain, and it recurs everywhere a "too many false positives" complaint shows up — including CI review agents (see `claude-code-workflows.md`) and content-moderation-style filters. If someone describes a Claude-based system as producing "too much noise" or "flagging everything," look first for an adjective doing load-bearing work in the prompt that should be a checklist instead.

## Structured output: enforce it via tool-use, don't request it in free text

There are two ways to get JSON (or any structured shape) out of a model call:

1. **Prompted** — ask for JSON in the instructions and hope the model complies. This works most of the time, until the model prepends something conversational ("Sure, here's your JSON:") and a naive downstream parser breaks in production, usually at the worst possible moment.
2. **Enforced via tool schema** — define a tool whose input schema *is* the JSON shape you want, include it in the tools array, and force tool choice so the model must call that tool. The model then returns a tool-use block whose input already conforms to your schema. This is far more reliable because tool-call compliance is a capability Anthropic specifically trains and evaluates the model against, at a much higher bar than free-text format-following.

**When schema drift still happens** (rare, but possible even with enforced tool-use): don't retry blindly. Run the output through your schema validator, and on failure, append the validator's *specific* error message as a new turn ("your previous response failed validation with this exact error...") referencing the model's own prior output, then call again. Giving the model the precise broken field, in the context of what it just produced, drives a much higher correction rate on the retry than a generic "please try again."

## Batch processing for high-volume, non-interactive prompting

If the workload is (a) offline — no user waiting synchronously, (b) tolerant of latency measured in hours, and (c) made of independent prompts where order doesn't matter, a batch-submission API (submit many prompts, collect results later) is usually the right shape rather than a tight synchronous loop — it's meaningfully cheaper per token and better suited to the access pattern. The canonical scenario is "classify N documents/records overnight" — reach for batch processing, not a real-time loop, whenever all three conditions hold. If any one condition doesn't hold (there's a user waiting, or later prompts depend on earlier results), batching is the wrong tool.

## Checklist when reviewing a prompt or structured-output design

- [ ] Does the prompt contain adjectives like "careful," "thorough," "appropriate," or "reasonable" describing the desired judgment, with no checkable rule behind them?
- [ ] Is structured/JSON output requested in free text, or enforced via a tool schema + forced tool choice?
- [ ] If validation ever fails on model output, does the retry include the specific validator error, or is it a blind re-ask?
- [ ] Is a synchronous per-item loop being used for a workload that's actually offline, latency-tolerant, and made of independent items — i.e., should this be batched instead?
- [ ] If this is a review/classification/filtering prompt with a "too much noise" complaint, has every subjective adjective been converted to an explicit, checkable rule?
