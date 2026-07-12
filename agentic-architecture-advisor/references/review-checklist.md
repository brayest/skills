# Full Review Worksheet

Use this when the user asks for a general review of an agentic Claude system (not a narrow question about one dimension). Go dimension by dimension; skip a section only if it's genuinely not applicable to what's being reviewed (e.g. a single-call classifier has no multi-agent section to review).

For each item that fails, name the anti-pattern directly (see the list in `SKILL.md`) and give a one-line concrete fix — not a vague caution.

## 1. Agent loop & orchestration (`agentic-patterns.md`)
- Is the control flow a workflow or an agent, and is that the right choice for how knowable the steps are ahead of time?
- If it's a loop: are inspect/execute/append/re-call all present, and is there an explicit termination condition?
- If multi-agent: sequential or adaptive, and does that match the dependency structure? Does failure recovery retry only the failed unit?
- Is the token/cost overhead of the current shape (workflow vs. agent vs. multi-agent) justified by the task's value?

## 2. Tool & MCP design (`tool-design.md`)
- Can each tool be told apart from its closest sibling using only its name + description + schema?
- Are parameter names unambiguous?
- Do failures return structured, categorized errors, or raw exception strings?
- Is the MCP transport (STDIO vs SSE) justified by where the server actually runs today?

## 3. Prompt engineering & structured output (`prompt-and-structured-output.md`)
- Any load-bearing vague adjectives ("careful," "thorough," "appropriate") standing in for a checkable rule?
- Is structured output enforced via tool schema, or requested in free text?
- Is a synchronous loop being used for offline, latency-tolerant, independent-item work that should be batched?

## 4. Context engineering & reliability (`context-and-reliability.md`)
- Is anything in context "just in case," with no clear behavioral purpose?
- Do durable facts get re-anchored at the end of context in long conversations, or left to summarization?
- Are cache-control breakpoints on genuinely static content, not on the variable final turn?
- Is there an explicit confidence/ambiguity check that triggers escalation to a human?

## 5. Claude Code / CI workflow (`claude-code-workflows.md`) — if applicable
- Do shared rules live in the project-level CLAUDE.md, not the user-level one?
- Do slash commands' `allowed-tools` match their intended scope?
- Does a CI gate fail only on schema-named categories, not free-text concern?

## Wrap-up

After going through the applicable sections, summarize:
1. The 2-3 highest-impact issues found (not every minor nit).
2. For each, name the anti-pattern and the concrete fix.
3. If nothing significant surfaced, say so plainly rather than manufacturing minor nitpicks to seem thorough.
