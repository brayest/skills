These are two different failure modes — one is a context management problem, one is a prompt/calibration problem. Here's how I'd debug and fix each.

## 1. Support bot forgetting the account number from message 3

At 40+ turns, this is almost certainly a **context window / context management** issue, not a "model is dumb" issue. A few likely causes, roughly in order of probability:

**a) You're not actually keeping full history in the context sent to the model.**
Many bot frameworks summarize or truncate older turns once a conversation gets long (sliding window, token-budget trimming, or a "summarize old messages" step). If message 3 falls outside that window by turn 40, the account number is just gone — the model never sees it again. Check:
- Is there a max-turn or max-token cutoff before you call the model?
- Is there a summarization step, and does the summary prompt explicitly instruct it to preserve identifiers like account numbers, order IDs, etc.? Generic summarization prompts routinely drop "boring" structured data like IDs in favor of narrative gist.

**b) Lost-in-the-middle effect.**
Even if the full history is technically in context, models are measurably worse at retrieving information from the middle of a long context than from the beginning or the very end. A account number mentioned once at turn 3 and never repeated is exactly the kind of detail that gets "buried." This gets worse, not better, as the transcript grows.

**c) No structured state extraction.**
If the account number lives only inside raw chat turns, you're relying on the model to re-find it every single time via long-context retrieval. That's fragile. The fix that scales is to stop treating "remembering the account number" as a context-recall problem at all.

### Fixes, in order of leverage:

1. **Extract and pin key facts outside the raw transcript.** As soon as the account number (or order ID, email, etc.) is provided, extract it into a small structured "session state" object (e.g., `{account_number: "12345", issue_type: "billing"}`) and inject that into the system prompt or a fixed "known facts" block on every single turn — not buried in turn 3 of the history. This is the single highest-leverage fix. Don't make the model re-derive facts from history; hand them back explicitly every turn.

2. **If you must keep raw history, don't blindly truncate/summarize.** If you have a summarization step for old turns, add an explicit instruction: "Always preserve identifiers, account/order/ticket numbers, names, and dates verbatim in the summary — never paraphrase or drop them." Better: extract these fields programmatically (regex/NER on account number patterns) before summarizing, independent of whether the LLM summary keeps them.

3. **Re-anchor critical facts near the end of context.** Since recency and start-of-context are attended to more reliably than the middle, put a compact "here's what we know so far" block right before the latest user turn (not just once at the start). This is the same idea as #1 — a live state block refreshed every turn beats hoping the model finds it in scrollback.

4. **Consider a shorter effective window with retrieval instead of raw replay.** For long support conversations, a common pattern is: keep the last N turns verbatim + a running structured summary/state object for everything older, rather than replaying the entire raw transcript. This bounds cost and avoids lost-in-the-middle entirely.

5. **Verify the bug is in your app, not the model.** Log the exact payload sent to the API on the turn where it forgets. Confirm the account number is literally present in that payload. If it isn't, this is 100% an app-side context assembly bug, not a model limitation — very common with agent frameworks that auto-manage history.

## 2. CI review bot crying wolf on every PR

This is a calibration/precision problem, and it's extremely common with "review this PR for issues" style prompts. A few root causes:

**a) The prompt asks a low-bar question.** Prompts like "review this PR and flag any potential issues" invite the model to always find *something* — style nits, hypothetical edge cases, "consider adding a test," speculative "this could be a problem if X." An LLM optimizing to be helpful and thorough will almost always produce output, because "no issues found" feels like an unhelpful non-answer to it unless you explicitly permit and reward silence.

**b) No severity/confidence gating.** If the bot reports everything it notices with equal weight — a real null-pointer bug and a "you might want to rename this variable" — the signal-to-noise ratio craters and the team (correctly) starts ignoring it, same as alert fatigue in monitoring.

**c) No suppression of low-value categories.** Style, formatting, naming, and speculative "what if" comments are cheap for the model to generate and rarely valuable in CI review, but they dominate output unless explicitly excluded.

**d) Possibly no "approve/no comment" path being taken seriously.** If the tool always posts a comment even when nothing is wrong, or the prompt doesn't strongly permit "this PR looks fine, no issues" as a valid, common, expected outcome, you'll get manufactured findings.

### Fixes:

1. **Raise the bar explicitly in the prompt.** Reframe from "find potential issues" to something like: "Only flag issues you have high confidence are real, concrete problems (bugs, security issues, correctness issues, broken tests). Do not flag style, naming, or speculative concerns. If you find nothing meeting this bar, explicitly say 'No issues found' and do not invent minor comments to seem thorough." Explicitly telling the model that "no issues" is a good, expected, common outcome matters — models default to always producing findings unless told otherwise.

2. **Require severity + confidence on every finding**, and only surface high severity/high confidence ones as PR comments. Have the model emit structured output (e.g., JSON with `severity`, `confidence`, `category`) and filter programmatically before posting — don't let free-text prose decide what's worth surfacing. This also lets you tune the threshold without re-prompting.

3. **Separate categories and gate what gets posted.** Bugs/security > logic errors > missing test coverage > style. Only auto-post the top 1-2 tiers as blocking comments; put lower-tier stuff (if you want it at all) behind a collapsed "nitpicks" section or don't surface it at all.

4. **Give it grounding, not just the diff.** A lot of false positives come from reviewing a diff in isolation without full file context, related tests, or how the changed function is called elsewhere. If your CI bot only sees the diff hunk, it will hallucinate "issues" that are non-issues once you see the full file. Feed it the full changed files (and ideally relevant callers/tests), not just unified diff context lines.

5. **Add a feedback loop.** Let engineers react/dismiss with a reason (false positive, not relevant, style-only). Periodically feed a batch of dismissed comments back into refining the prompt/threshold — this is the fastest way to find what's generating noise.

6. **Test empirically before re-deploying.** Run the revised prompt against 20-30 recent merged PRs you already know were clean, and check the false-positive rate. If it still comments on most of them, the prompt still isn't restrictive enough — iterate before shipping. Treat this like tuning a monitoring alert threshold: you want it to reliably flag the handful of PRs that actually have real bugs and stay silent on the rest.

## Common thread

Both problems come from the same root cause: **relying on the model's default behavior instead of explicitly engineering the context/instructions for your specific reliability bar.** The support bot needs explicit state-passing because raw long-context recall isn't reliable at scale. The review bot needs explicit "silence is a valid, good answer" and confidence/severity gating because free-form "find issues" prompts default to manufacturing findings. Neither is a model capability ceiling — both are fixable with better context engineering and prompt constraints.
