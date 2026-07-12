---
name: agentic-architecture-advisor
description: Reviews and designs Claude-based agentic systems — agent loops, multi-agent orchestration, tool/MCP design, prompt engineering for structured output, and context management/reliability — against Anthropic's own published engineering guidance (Building Effective Agents, Writing Effective Tools for AI Agents, Effective Context Engineering, the Multi-Agent Research System writeup) and the Claude Certified Architect (CCA-F) exam framework. Use this proactively whenever the user is designing, reviewing, or debugging anything agent-shaped with Claude: an agent loop or tool-use loop, a coordinator/sub-agent or multi-agent pipeline, an MCP server or tool definitions, a CLAUDE.md setup, a prompt meant to produce structured/JSON output, a long-running or long-context conversation, or a CI/CD pipeline that runs Claude headlessly. Trigger even when the user doesn't say "architecture" or "best practices" explicitly — e.g. "my agent keeps calling the same tool twice", "should this be one agent or several sub-agents", "Claude's JSON output breaks sometimes", "our support bot forgets the account number after 40 messages", "what transport should my MCP server use", "review this tool schema", "my CI review agent has too many false positives". Do not trigger for questions about a specific non-Claude LLM/framework, or for generic software-architecture questions with no agent/LLM component.
---

# Agentic Architecture Advisor

## Why this skill exists

Claude is a stateless model behind one HTTP endpoint. It has no memory between calls, doesn't loop on its own, and doesn't execute anything — every agentic property (looping, memory, delegation, retries, escalation) is something *your application code* has to build deliberately. Most of the bugs and bad designs in Claude-based systems trace back to one of a small number of well-known failure patterns, and Anthropic has already published detailed guidance on avoiding them. This skill packages that guidance — plus the structured domain breakdown used by Anthropic's own Claude Certified Architect (CCA-F) exam — into a single advisor you can use to design a new system or review/debug an existing one.

Treat this as a second set of eyes, not a rulebook to recite. The goal is to help the user reason about trade-offs the way an experienced Claude agent-systems engineer would, and to name the specific anti-pattern when you see one, rather than issuing vague "be careful" warnings.

## How to use this skill

1. **Figure out which dimension(s) the question actually touches.** Most real questions cross 2-3 dimensions at once (e.g. "my multi-agent pipeline forgets context after a retry" is both orchestration *and* context management). Read the relevant reference file(s) below rather than guessing from memory — they contain the specific mechanics and the concrete anti-pattern names.
2. **If this is a review of existing code/config**, go through the checklist in `references/review-checklist.md` for the dimensions involved, and call out anti-patterns by name with a one-line fix — not a paragraph of hedging.
3. **If this is a new design**, walk the user through the same dimensions as design decisions (workflow vs. agent? sequential vs. adaptive sub-agents? what's worth caching? what does a tool's structured error look like?), citing the trade-off, not just the answer.
4. **Always ground recommendations in mechanism, not vibes.** Anthropic's guidance and the CCA-F framework both work because the reasoning is mechanical (stop_reason values, context-window attention, token cost, tool schema compliance) — explain *why* a pattern works, not just *that* it's recommended, so the user can extrapolate to their own edge cases.

## The five dimensions

| Dimension | Core question | Reference file |
|---|---|---|
| **1. Agent loop & orchestration** | Is this a workflow (you own the control flow) or an agent (the model owns the next step)? If multiple agents, sequential or adaptive decomposition? | `references/agentic-patterns.md` |
| **2. Tool & MCP design** | Will the model reliably pick the right tool and recover from its failures? | `references/tool-design.md` |
| **3. Prompt engineering & structured output** | Are instructions checkable, and is JSON output enforced structurally or just requested? | `references/prompt-and-structured-output.md` |
| **4. Context engineering & reliability** | What's in the context window, what's cached, what happens when it grows past what the model attends to well, and does the system know when to escalate to a human? | `references/context-and-reliability.md` |
| **5. Claude Code / CI-CD workflow config** | Where do shared rules live (CLAUDE.md hierarchy), and is headless/CI usage failing on the right things? | `references/claude-code-workflows.md` |

## First move: workflow vs. agent

Before designing any multi-step Claude system, answer this first — it's the highest-leverage decision and the one people skip. Anthropic's own framing (from "Building Effective Agents"): a **workflow** is code that orchestrates LLM calls through a path *you* define in advance (chaining, routing, parallelizing, orchestrator-worker, evaluator-optimizer); an **agent** is a loop where the model itself decides the next tool call based on what came back, and your code just enforces the goal and the guardrails (max iterations, allowed tools, budget).

Default to the simplest thing that passes evaluation. Use a workflow whenever the steps and their order are knowable ahead of time — it's more predictable, cheaper, and easier to debug. Reserve a full autonomous agent loop for cases where the path genuinely can't be hardcoded (open-ended investigation, unknown number of steps) but progress can still be checked. Reaching for a multi-agent framework by default when a single well-tooled prompt would do is the most common over-engineering mistake in this space — multi-agent orchestration burns roughly an order of magnitude more tokens than a single call, so it needs to earn that cost.

## Common anti-patterns to name on sight

These recur across both Anthropic's engineering writeups and the CCA-F exam's distractor patterns — if you see one, name it directly:

- **Vague-adjective prompting** — "review carefully" / "be thorough" instead of a checkable rule list. Root cause of most false-positive-heavy review agents.
- **Lossy summarization of durable facts** — compressing a long conversation that carries IDs, amounts, or account numbers into a summary instead of extracting them into a small fact block re-anchored at the end of context.
- **Blanket retry after partial failure** — restarting an entire multi-agent job when only one step failed, ignoring that earlier steps may have already produced side effects.
- **Shared config in the wrong CLAUDE.md tier** — team-wide rules placed in the user-level file (never leaves one machine) instead of the project-level file at the repo root.
- **Wrong MCP transport for the topology** — choosing SSE/HTTP for a server that could live in the same process as its client via STDIO, adding needless latency and an auth surface.
- **Ambiguous or overlapping tool descriptions** — multiple tools the model can't reliably distinguish at decision time, because the model only ever sees name + description + schema, nothing else.
- **Unstructured tool error strings** — returning a raw exception instead of a JSON shape the model can branch on (`is_error`, `category`, `retryable`, `retry_after_ms`), which causes either silent give-up or blind infinite retry.
- **Prompted-JSON instead of enforced-JSON** — asking for JSON in free text instead of defining a tool schema and forcing tool choice, which is fine until the model prepends a friendly sentence and the parser breaks in production.
- **Confidently wrong instead of escalating** — an agent that answers past the edge of its own certainty. Treat this as strictly worse than escalating a little too often; the cost asymmetry (bad answer shipped vs. one extra human-review ticket) almost always favors the eager escalation.
- **Multi-agent by default** — reaching for orchestrator/sub-agent complexity for a task a single well-tooled prompt or a plain workflow would solve just as well, at a fraction of the token cost.

## When you're not sure which reference file to open

If the question is about *why the model isn't calling tools right / isn't looping / isn't delegating right* → `agentic-patterns.md`.
If it's about *the model picking the wrong tool, or handling a tool failure badly* → `tool-design.md`.
If it's about *the model's output format, or a prompt being too vague/unreliable* → `prompt-and-structured-output.md`.
If it's about *the model forgetting things, cost, or knowing when to hand off to a human* → `context-and-reliability.md`.
If it's about *CLAUDE.md, slash commands, or running Claude in CI* → `claude-code-workflows.md`.

For a structured pass over an existing design (e.g. "review this agent system"), use `references/review-checklist.md` as your worksheet — go dimension by dimension and only skip a section if it's genuinely not applicable.
