Two unrelated bugs, but both are named anti-patterns with mechanical causes and known fixes.

## 1. Support bot forgetting the account number

**Cause: lost-in-the-middle.** Claude (like every long-context model) attends strongly to the start and end of the context window and weakly to content buried in the middle. The account number was stated once, in message 3, and now — 40+ turns later — it's sitting deep in attention-poor territory. This isn't a "memory" failure, it's a retrieval-attention failure, and it gets worse the longer the conversation runs.

**The trap to avoid:** don't fix this by periodically summarizing the conversation to keep it short. Summarization is lossy by construction — it's tuned to compress prose, not preserve exact tokens — and it will drop precisely the kind of content that matters here (IDs, numbers). You'd be trading a lost-in-the-middle bug for a summarized-away bug.

**The actual fix:** extract durable facts (account number, order IDs, amounts, decisions already confirmed) into a small structured "case block" — a few lines, not prose — and re-inject it at the *end* of the context on every single turn, right before the current user message. Something like:

```
[CASE FACTS — confirmed this session]
account_number: 48213-B
issue_opened: 2026-07-06
prior_resolution_attempts: 2
```

Because it's re-anchored at the end on every call, the model's attention lands on it regardless of how long the conversation has gotten — you're not relying on the model "remembering," you're relying on where the content physically sits in the window on that call. This is cheap: it's a few lines added per turn, not a growing transcript.

Practically: as soon as the customer states an identifier, your app code (not the model) should parse it out and add it to a durable fact store keyed to the conversation, then render that store into the case block on every subsequent call. Don't ask the model to "remember to mention it later" — that's asking a stateless function to have state.

## 2. CI review bot flagging almost every PR

**Cause: vague-adjective prompting.** Somewhere in that bot's prompt is almost certainly language like "review this PR carefully for potential issues" or "flag anything concerning." "Carefully," "potential," "concerning" have no shared, checkable definition — the model has to interpret them, and it interprets broadly, pattern-matching anything remotely cautionary. That's exactly why it reads as "flags everything": it's doing what a vague instruction like that produces every time, and the team disengaging is the predictable next step — a review nobody trusts is worse than no review.

**The fix has two layers, and you need both:**

1. **Replace every evaluative adjective with a numbered, yes/no-checkable rule list.** Not "check for security issues" — instead: "Flag if user input reaches a SQL query without parameterization. Flag if a new endpoint has no auth decorator. Flag if a secret-looking string (matches `[A-Za-z0-9/+]{40}`) is added to a non-test file." Each rule should be answerable by reading the diff directly, no judgment call.

2. **Enforce structured output and gate the build on named categories, not free text.** If the pipeline is currently parsing prose and failing the build whenever Claude "expresses concern" in any form, that's the second half of the bug — even a well-scoped prompt will still hedge sometimes, and hedge-triggered failures are what actually train the team to ignore it. Define a tool schema like:

```json
{
  "issues": [
    {"category": "security_violation" | "breaking_api_change" | "missing_test" | "style_nit", "detail": "...", "line": 42}
  ]
}
```

Force tool choice so Claude must return this shape (don't just ask for JSON in free text — that breaks the moment the model prepends "Sure, here's the review:"). Then have the pipeline fail the build **only** on categories you've explicitly named as blocking (e.g. `security_violation`, `breaking_api_change`), and surface everything else (`style_nit`, `missing_test`) as non-blocking comments. This turns "almost every PR gets flagged" into "only PRs with an actual named problem block."

**One more thing worth checking**: if this CI bot's rules live in `~/.claude/CLAUDE.md` on one person's machine rather than a project-level `CLAUDE.md` at the repo root, they never reach CI at all — CI runs headless with no access to anyone's home directory config. Shared review rules belong in the repo, committed, or they're not really "the team's" rules.

## If you want to go further
Both fixes are code/prompt-structure changes, not "make the model try harder." If you want, I can help draft the actual case-block extraction logic for the support bot, or the specific rule list + tool schema for the CI reviewer — tell me which one first.
