# Context Engineering & Reliability

Source grounding: Anthropic engineering, "Effective context engineering for AI agents" and "How we built our multi-agent research system"; CCA-F Domain 5 (Context Management & Reliability, 15% of the exam — the lightest weight, but cross-cutting: it applies to every other domain).

## Context engineering, not just prompt engineering

The framing that matters here: the question isn't "what words do I put in the prompt" but "what configuration of context — system prompt, tools, examples, message history, retrieved documents — is most likely to produce the behavior I want, given a limited and costly window." Context is a finite resource with real dollar cost per token, and every component competes for the model's attention inside it. Keep each component informative but tight; don't include content "just in case" — it isn't free, and past a certain point more context measurably degrades attention to what actually matters (see below).

## Lost-in-the-middle

An empirical, cross-model-family finding: a model attends most strongly to content near the very start and very end of a long context window, and comparatively weakly to content buried in the middle. This isn't specific to Claude — it holds across long-context model families generally.

**Where this bites**: a long-running conversation (e.g. a support agent 40 turns in) "forgets" a detail — an account number, an order ID, an amount — that was stated once, early, and now sits in the attention-poor middle of the window.

**The tempting, wrong fix**: summarize the whole conversation periodically. Summarization is lossy by construction, and it disproportionately drops exactly the kind of content that matters most here — precise numbers and identifiers — because summarization heuristics are built to compress prose, not preserve exact tokens.

**The correct fix**: identify the durable facts (IDs, amounts, decisions already made) and copy them into a small, structured block — often called a case block — re-anchored at the *end* of the context on every turn, so the model's attention reliably lands on it regardless of how long the conversation gets. This is cheap (it's small) and doesn't depend on the model "remembering" — it depends on where the content physically sits.

## Prompt caching

Every input token costs money on every call. If a large, byte-identical prefix (a system prompt, a set of few-shot examples) gets resent on every call, you pay full price for it every time. A cache-control breakpoint marks a prefix for reuse: the model's internal state at that point is cached for a short window (minutes, with a longer-duration option at extra write cost), and subsequent calls that reuse the exact same prefix pay a small fraction of standard input price on the cached portion, with a modest premium on the initial cache-write call.

**What's worth caching**: content that's identical across calls — system prompts, tool definitions, few-shot examples, large reference documents reused verbatim.
**What's not worth caching**: the final user turn — it's different every time by definition, so caching it just pays the write premium on an entry that will never be hit again.

## Multi-agent context economics

Multi-agent orchestration (see `agentic-patterns.md`) exists partly *as* a context-management technique: spawning sub-agents lets a coordinator receive back a compact summary instead of filling its own window with every intermediate file read or search result. But it isn't free — Anthropic's own production numbers put multi-agent token consumption roughly an order of magnitude above a single conversational call. Treat "should this be one call, a workflow, or a multi-agent system" partly as a context/cost question, not just a capability question.

## Escalation and knowing the limits of confidence

A reliable agent has to recognize when it's operating past the edge of what it actually knows, and hand off rather than guess. The asymmetry that should drive design: an agent that *confidently answers wrong* ships a bad outcome directly to whoever's relying on it; an agent that *escalates a bit too eagerly* costs one extra human-review ticket. Those two failure modes are not equally bad, and systems should be tuned toward the cheaper one.

**Pattern**: an explicit confidence/ambiguity check at the end of the agent's reasoning, with two triggers for hand-off: (a) the model's own stated confidence falls below a threshold you've defined, or (b) the model detects ambiguity in the request it can't resolve from the conversation history alone. Either trigger routes to a human with a structured summary — what the agent knew, what it tried, and where it got stuck — so the human doesn't have to re-derive context from scratch.

## Checklist when reviewing context management / reliability

- [ ] Is anything in the system prompt or context there "just in case," with no clear behavior it drives?
- [ ] Do durable facts (IDs, amounts) in a long conversation get re-anchored near the end of context, or are they relying on the model finding them wherever they landed originally?
- [ ] Is periodic summarization being used on a conversation that carries exact identifiers/amounts that summarization would silently drop?
- [ ] Are cache-control breakpoints placed after content that's actually identical across calls (system prompt, tools, few-shot), and not on the variable final user turn?
- [ ] Does the system have an explicit confidence/ambiguity check that triggers escalation, or does it always attempt an answer regardless of certainty?
- [ ] If this is multi-agent, is the token/cost overhead actually justified by the task's value, given roughly 10x cost over a single call?
