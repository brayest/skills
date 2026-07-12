# Pipeline shape

Use a **workflow**, not a coordinator + sub-agents. The steps are knowable in advance — read files, research, synthesize — so you should own that control flow in code rather than handing step-sequencing to a model loop. Concretely, this is **prompt chaining with a parallelization step**:

1. **Read the ~10 internal files** — this is plain I/O, not an LLM call at all. Load them in your code.
2. **Web research** — if the queries are fixed/known, run them in parallel (sectioning) as direct calls, not agent-decided. If you genuinely don't know what to search for until you've digested the internal files first, use one LLM call to plan the queries, then execute them — still your code driving it, not an autonomous loop.
3. **Synthesis** — one LLM call with the internal file contents + research results in context, producing the report.

This is a single well-tooled pipeline, not a multi-agent system, for two mechanical reasons:

- **Token cost**: multi-agent orchestration (coordinator spawns sub-agents, each with its own context window, reporting back summaries) runs roughly an order of magnitude more tokens than a single-call/workflow approach. Anthropic's own research-agent data shows that cost is justified for open-ended investigation where the number of steps genuinely can't be predicted — not for a fixed "read → research → write" shape like yours.
- **The steps here are knowable ahead of time.** Multi-agent decomposition exists to solve a *context-budget* problem (one call would blow its context window reading everything and researching before it ever gets to write), not to get more raw capability. ~10 files plus a research pass is very unlikely to blow a modern context window if you're reasonably terse about what you paste in.

**When this would flip to multi-agent**: if "do some web research" is actually open-ended — you don't know how many searches, follow-up questions, or sources you'll need until you see what the first few return — that's adaptive, not sequential, and is the one legitimate trigger for an orchestrator-workers shape (a coordinator that decides the next search based on what came back, returning only distilled findings to keep its own context small). If that's the case: use it for the *research* step only, not the whole pipeline — still chain that step's summarized output into a plain synthesis call at the end.

**Practical default**: single call or a short chain of calls (file digest → research plan → research execution in parallel → synthesis), no sub-agent spawning. Reserve the upgrade to orchestrator-workers specifically for the research step, and only if you find in practice that the query set can't be front-loaded.

# MCP transport for the internal wiki server

**STDIO.** The deciding fact is co-location: the wiki server and Claude Code run on the same laptop. STDIO means the server lives in the same process tree as the client, communicating over stdin/stdout — zero network latency, zero auth surface to design or maintain.

SSE/HTTP is the wrong choice here and is the single most common mistake in MCP transport selection: reaching for it "for consistency" or "in case we need it remote later" when the server currently runs on the same machine as the client. That buys you nothing today and forces you to build an auth scheme you don't need yet. Only move to SSE/HTTP if the wiki server genuinely stops being local — e.g. you later centralize it to serve multiple users' machines from one shared host. If that day comes, migrate then; don't pre-pay the cost now.

So: build it as a local STDIO MCP server. If you later need to share it across a team from a central host, that's the trigger to revisit and switch to SSE/HTTP with proper auth — not before.
