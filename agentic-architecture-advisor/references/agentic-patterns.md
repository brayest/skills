# Agentic Patterns — Agent Loop & Orchestration

Source grounding: Anthropic engineering, "Building Effective Agents" and "How we built our multi-agent research system"; CCA-F Domain 1 (Agentic Architecture & Orchestration, 27% of the exam — the single heaviest domain).

## 1. The mechanics of a single agent loop

Claude never loops by itself. Every call to the Messages API returns a `stop_reason`:

- `end_turn` — Claude is done; the response text is the final answer.
- `tool_use` — Claude has paused mid-thought and is asking your code to run a function on its behalf.

Your code owns the loop: **inspect the response → execute the requested tool locally → append the tool result to conversation history as a tool-result message → call the API again with the updated history.** Claude picks up where it left off and either calls another tool or finishes.

This is the entire mechanism behind "agentic" behavior — there is no hidden loop on Anthropic's side. When you're debugging an agent that behaves strangely, check which of the four steps might be missing or wrong:

| Symptom | Likely missing/broken step |
|---|---|
| Agent calls one tool, then goes silent forever | The *inspect* step never fires again — code isn't re-checking `stop_reason` after execution |
| Agent calls the exact same tool with the same arguments repeatedly | The *append* step is missing — the tool result never made it back into history, so the model has no evidence it already ran |
| Agent loops seemingly forever | No termination/iteration cap — the loop needs an explicit max-turns or budget guard even when the model is behaving correctly, because "open-ended" tasks have no natural stopping point otherwise |
| Agent ignores a tool result it clearly received | The result was appended in the wrong role/shape, or truncated before the next call |

## 2. Workflow vs. agent — the decision that comes first

Anthropic's own framing draws a hard line:

- **Workflow**: your code defines the path. LLM calls are one ingredient inside code you control. Five recurring workflow shapes:
  - **Prompt chaining** — break a task into ordered steps, each an LLM call, with programmatic checks between steps.
  - **Routing** — classify the input first, then send it down one of several fixed downstream paths.
  - **Parallelization** — run independent LLM calls concurrently (sectioning) or run the same call multiple times and aggregate (voting).
  - **Orchestrator-workers** — a central call plans and dispatches to worker calls, then synthesizes; the routing decision is made by the model call itself, but the overall shape is still fixed by your code.
  - **Evaluator-optimizer** — one call generates, another call critiques against explicit criteria, loop until the evaluator passes it.
- **Agent**: the model decides the next tool call based on what came back from the last one; your code only supplies the tools, the system prompt, and the guardrails (stop conditions, budgets, allowed actions).

**Default rule**: start with the simplest option that could plausibly pass evaluation — often a single well-tooled prompt, sometimes a workflow. Move to a full autonomous agent only when the number and order of steps genuinely can't be known ahead of time, but you can still verify whether progress is being made at each step. Complexity should be earned by the task, not assumed because "agents" sound more capable.

## 3. Multi-agent orchestration (coordinator + sub-agents)

When one Claude call would have to read many files, run many searches, and synthesize — it fills its own context window before finishing. The fix is a **coordinator** that spawns **sub-agents** (via the Agent SDK's task-spawning tool), each scoped to one piece of work. The coordinator receives back only each sub-agent's compact summary, not its full working context, which is what keeps the coordinator's own context small. This is fundamentally a context-budget optimization — not a way to get more raw capability out of the model.

Two decomposition strategies:

- **Sequential** — finish sub-agent N before spawning N+1. Correct whenever each step genuinely depends on the previous step's output (e.g. "extract data, then transform it, then load it").
- **Adaptive** — the coordinator decides the next sub-agent based on what the last one returned. Correct for open-ended investigation where the shape of the work isn't knowable in advance (e.g. "investigate a competitor's pricing strategy").

Anthropic's own production data on this pattern is a useful sanity check: their multi-agent research architecture measured a large accuracy improvement over single-agent approaches on open-ended research tasks, but at roughly an order of magnitude more total tokens than a single conversational turn. That trade-off is the reason multi-agent orchestration should be reserved for tasks whose value clearly exceeds that token cost — not applied as the default shape for anything with more than one step.

**Partial-failure recovery**: when one sub-agent fails mid-pipeline, the correct recovery is a *targeted retry of just the failed sub-agent* — not restarting the whole job. Sub-agents that already completed successfully may have produced side effects (database writes, sent emails, external API calls); rerunning them duplicates those effects. This is one of the most-tested anti-patterns in this space: "just retry everything" is the tempting, wrong answer whenever any step has a side effect.

## Checklist when reviewing an agent-loop or multi-agent design

- [ ] Is every `stop_reason == tool_use` response followed by execute → append → re-call, with no step skipped?
- [ ] Is there an explicit termination condition (max iterations, budget, or explicit "done" signal) independent of the model's own judgment?
- [ ] Is this task actually agent-shaped, or would a workflow (fixed code path) be simpler, cheaper, and more predictable?
- [ ] If multi-agent: is the decomposition sequential or adaptive, and does that match whether steps depend on each other?
- [ ] If multi-agent: does failure recovery retry only the failed unit, accounting for already-committed side effects from siblings?
- [ ] Does the token/cost overhead of spawning multiple agents get justified by the task's value, or is a single call with good tools enough?
