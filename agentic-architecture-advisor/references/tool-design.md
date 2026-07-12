# Tool & MCP Design

Source grounding: Anthropic engineering, "Writing effective tools for AI agents"; CCA-F Domain 4 (Tool Design & MCP Integration, 18% of the exam).

## What the model actually sees

At the moment it decides which tool to call, the model has exactly three pieces of information about each tool: its **name**, its **description**, and its **input schema**. Nothing else — no internal implementation, no comments in your code, no tribal knowledge. Every design decision below follows from that constraint.

## Choosing which tools to build at all

Prefer tools with high leverage — ones that give the model a genuinely new capability or collapse several manual steps into one — over thin wrappers around an existing API endpoint. A tool that just mirrors a REST call one-to-one often makes the model do more work (chaining several such calls, reasoning about pagination itself) than a slightly higher-level tool that does the chaining and returns a distilled result.

Return meaningful, human-readable context from tools, not raw technical payloads. The model reasons better over `"customer_status": "past_due"` than over an opaque internal enum ID it has to have separately memorized the meaning of. Be mindful of token cost on the way back too — support pagination, truncation, or filtering parameters so one tool call can't silently dump an enormous payload into context.

## Writing descriptions that disambiguate

If you ship three tools whose descriptions all amount to "returns user information" (e.g. `get_user`, `look_up_user`, `find_customer`), the model effectively guesses between them — this is scored as a design defect, not a model failure. Write every tool description like an API doc entry aimed at a new colleague who has zero context on your system:

1. One sentence on what the tool does.
2. One sentence on *when to use this one specifically* versus its siblings — the disambiguation rule the model needs at decision time.
3. One example invocation with realistic (not placeholder) arguments.
4. The error conditions the tool can return.

Avoid ambiguous parameter names. Prefer `user_id` over `user` — the latter could mean a display name, a full user object, or an ID, and the model has to guess which. Any contextual assumption, unit, format, or jargon term specific to your domain needs to be spelled out explicitly in the description; don't assume the model shares tribal context with your team.

## Structured error responses

When a tool fails, return a JSON object the model can branch its own reasoning on — not a raw exception string or stack trace. A well-shaped tool error includes:

- `is_error: boolean` — explicit signal that this is the failure path, not a normal result that happens to contain the word "error."
- `category: string` — a small closed vocabulary (`rate_limited`, `not_found`, `permission_denied`, ...) the model can match against a named recovery branch.
- `retryable: boolean` — whether retrying at all makes sense.
- `retry_after_ms: integer` (when applicable) — how long to wait before retrying.

Without this shape, the model either gives up immediately on a transient, recoverable failure, or starts an unbounded retry loop against a failure that will never succeed — and you find out about it later in the logs, not at design time.

## Iterating on tool design like a product

Anthropic's own process for refining tools is "prototype → evaluate → collaborate": build a first version, run it against realistic tasks and measure where the model struggles or picks the wrong tool, then revise the description/schema based on those concrete failures — the same loop you'd use to improve any developer-facing API, just with the model as the "developer." Small wording refinements to tool descriptions have measurably moved agentic benchmark performance in Anthropic's own evaluations, so this iteration is worth doing deliberately rather than writing descriptions once and moving on.

## MCP transport selection

MCP (Model Context Protocol) exists so a tool/data-source integration written once works across any MCP-compliant client (the API, the Agent SDK, Claude Code, etc.) without bespoke glue code per surface. Two transports:

| Transport | Where the server runs | Overhead | Default when |
|---|---|---|---|
| **STDIO** | Same process tree as the client, over stdin/stdout | Zero network latency, zero auth surface | The server can live on the same machine as its client |
| **SSE / HTTP** | A different host from the client | Network round-trips, and you must design an auth scheme | Only when the server genuinely must live elsewhere — e.g. a centralized connector serving many users from one shared host |

The most common mistake here is choosing SSE "for consistency" or "in case we need it remote later" when the server currently runs on the same machine as its client. That's needless latency and an unnecessary auth surface for no present benefit — pick STDIO by default and only move to SSE when co-location genuinely stops being true.

## Checklist when reviewing tool/MCP design

- [ ] Could a human unfamiliar with this codebase tell, from the description alone, when to use this tool vs. its closest sibling?
- [ ] Are parameter names unambiguous (`user_id`, not `user`)?
- [ ] Does a failure return a structured, categorized error the model can branch on, not a raw exception?
- [ ] Does the tool return human-readable, right-sized context, with pagination/filtering if the underlying data could be large?
- [ ] Is the transport (STDIO vs SSE) actually justified by where the server has to run today, not by future-proofing?
- [ ] Has this tool's description been iterated against at least one real failure case, or is it still the first draft?
