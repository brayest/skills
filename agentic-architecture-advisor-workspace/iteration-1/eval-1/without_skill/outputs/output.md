# Pipeline architecture: single call vs. coordinator + sub-agents

**Use a coordinator with sub-agents for the web-research portion; keep file reading and final synthesis in the coordinator itself.** This is the "orchestrator-workers" pattern.

Why not a single call:
- Web research is open-ended — you don't know in advance how many searches/fetches you'll need, and raw fetched pages (HTML, long articles) are noisy. Stuffing all of that into one context window pollutes it and makes the final synthesis worse, not better.
- Research sub-tasks (e.g., "find X," "verify Y," "compare Z") are largely independent, so they parallelize well. Running them concurrently cuts wall-clock latency significantly vs. a single agent doing sequential searches.
- Each sub-agent can return a condensed, cited summary instead of raw scraped content — this is the main context-management win: the coordinator's context stays small and clean, holding only synthesized findings, not intermediate HTML/search-result noise.

Why not full sub-agents for everything:
- The 10 internal files are a fixed, known set — not an open-ended discovery task. Unless individual files are large enough to blow your context budget, just have the coordinator read them directly. Spinning up sub-agents for a deterministic, bounded read adds coordination overhead (latency, cost, another place for instructions to get lost) with no real benefit. Only delegate file reads if you need per-file summarization to fit context.
- Final synthesis needs the full picture (internal file content + all research summaries) in one place to reason coherently — that's a job for the coordinator, not something to split further.

Recommended shape:
1. Coordinator reads the 10 internal files directly (or delegates per-file summarization only if they're large/verbose).
2. Coordinator fans out N research sub-agents in parallel, each scoped to a specific, well-defined sub-question (not "go research the topic" — narrow, concrete briefs with enough context to make judgment calls, per Anthropic's own multi-agent research guidance). Each sub-agent does its own searches/fetches and returns a short, cited synthesis — not raw pages.
3. Coordinator combines internal-file findings + sub-agent syntheses into the final report.

Trade-off to flag: multi-agent orchestration adds real overhead — spin-up latency, token cost of running multiple agents, and risk of information loss at the coordinator/sub-agent boundary if task briefs are vague. If your web research is actually just 2-3 targeted lookups, skip the sub-agent machinery entirely and do it inline in a single call — simpler to build, debug, and maintain solo. Reach for sub-agents when the research is genuinely broad/parallelizable (multiple independent threads, uncertain number of searches), not by default.

# MCP transport for a local wiki server

**Use stdio.** Since the wiki server runs on the same laptop as Claude Code, Claude Code spawns it as a child process and talks to it over stdin/stdout. This is the standard, lowest-friction choice for local MCP servers:

- No network/port management, no auth handshake — the parent process (Claude Code) owns the child's lifecycle (start/stop/restart), which simplifies deployment and debugging.
- Lowest latency, since there's no HTTP stack involved.
- This is what nearly all local MCP servers (filesystem, git, local databases) use.

Reach for **Streamable HTTP** only if:
- The wiki server needs to be reachable by multiple clients or from a different machine/network (not the case here — same laptop).
- You need the server to run as a long-lived, independently-managed daemon rather than being spawned per-session.

(SSE is the older remote transport, now effectively superseded by Streamable HTTP — not relevant for a same-machine setup either way.)

For your case — single laptop, single client — stdio is the right and simplest answer.
