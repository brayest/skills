# Agent design — least-agency in code

**Requirement being implemented:** OWASP LLM06 (Excessive Agency), OWASP ASI01 (Agent Goal Hijack),
HIPAA minimum-necessary, ISO 42001 A.9 (responsible use), NIST AI 600-1 human-AI configuration.

The principle: an agent's *capability set* — not its instructions — defines its blast radius. Prompt
injection is inevitable in some fraction of inputs; the design goal is that a fully hijacked agent
still cannot do anything consequential.

---

## 1. Capability manifests per agent

Make each agent's permissions an explicit, versioned, reviewable artifact — not an emergent property
of whatever code paths exist. One manifest per agent, checked into the repo, loaded at startup:

```python
# product_api/app/agent/capabilities.py
from pydantic import BaseModel

class CapabilityManifest(BaseModel):
    """What this agent may see and do. Reviewed like an IAM policy."""
    agent: str                        # "product-agent"
    readable_stores: list[str]        # ["s3://{bucket}/sessions/{session_id}/*"]
    writable_stores: list[str]        # ["s3://{bucket}/sessions/{session_id}/tickets/*"]
    db_tables_read: list[str]         # ["sessions", "requirements", "tickets"]
    db_tables_write: list[str]        # ["tickets"]
    tools: list[str]                  # names of LangGraph tools it may bind
    model_ids: list[str]              # allowed Bedrock model IDs
    may_call_network: bool = False    # anything beyond the model endpoint

PRODUCT_AGENT = CapabilityManifest(
    agent="product-agent",
    readable_stores=["s3://{bucket}/sessions/{session_id}/"],
    writable_stores=["s3://{bucket}/sessions/{session_id}/tickets/"],
    db_tables_read=["sessions", "requirements", "tickets"],
    db_tables_write=["tickets"],
    tools=["save_ticket", "delete_ticket", "load_analysis"],
    model_ids=["us.anthropic.claude-sonnet-*", "us.anthropic.claude-haiku-*"],
)
```

Two uses. First, **enforcement**: tool wrappers check the manifest before executing (below). Second,
**evidence**: the manifest *is* the "intended use and capability" section of the system card, and the
diff history of this file is the audit trail of capability changes. When an auditor asks "what can
this agent do," the answer is a file, not an investigation.

The manifest must be scoped **per session/tenant**, not per bucket. `readable_stores` templated on
`{session_id}` means a hijacked Product agent can corrupt one session, not the backlog of every
client team. The infrastructure half (an IAM role that actually enforces the same boundary) is in
`02-identity-access` in the `ai-platform-implementation` skill — the manifest is
defense-in-depth *inside* that role, catching bugs the role is too coarse to catch.

## 2. Tools enforce, prompts request

Every LangGraph tool validates against the manifest and its own input schema before acting. The tool
is the security boundary; the model's arguments are untrusted input:

```python
def save_ticket(state: GraphState, ticket: TicketDraft) -> Ticket:
    # 1. Capability check — is this write inside the manifest?
    path = f"sessions/{state.session_id}/tickets/{ticket.ticket_id}.json"
    require_writable(PRODUCT_AGENT, path)          # raises CapabilityViolation

    # 2. Ownership check — deterministic, from server-side state, never from model output.
    #    The session_id comes from the authenticated request context, NOT from the LLM.
    if ticket.session_id != state.session_id:
        raise CapabilityViolation("ticket targets a foreign session")

    # 3. Schema validation — pydantic, strict; reject, don't coerce.
    validated = Ticket.model_validate(ticket.model_dump())
    ...
```

The invariant worth writing on the wall: **identifiers that scope data access (session_id, tenant_id,
user_id) always come from the authenticated request context and are threaded through graph state.
They never come from model output.** An LLM asked to emit a session ID will eventually emit someone
else's.

## 3. The QA agent's code mount — the concrete excessive-agency case

A wholesale volume-mount of the repo into the QA container is the textbook case. Under least-agency
the QA agent should see **exactly the code under evaluation for the ticket it is working**, nothing
else:

- Resolve the ticket → changed files (from the PR diff) → stage *those files* into a per-job
  ephemeral directory. That directory is the agent's entire filesystem view.
- **Allowlist, never denylist.** A denylist of dangerous paths (`.env`, `.git`, `*.pem`) fails open:
  the one you forget — `.env.local`, `.aws/credentials`, `id_rsa` — is the one that leaks. An
  allowlist of staged files fails closed, which is the only direction worth failing.
- Deny path traversal *structurally*, and get the check order right:

```python
def read_source(state: JobState, rel_path: str) -> str:
    """The model supplies rel_path. Treat it as hostile."""
    root = state.job_root                      # server-side, never model output
    candidate = (root / rel_path)

    # Symlink check FIRST — .resolve() dereferences symlinks, so checking
    # is_symlink() after resolving inspects the *target* and always says False.
    # That ordering is a dead guard; it is the classic version of this bug.
    if candidate.is_symlink():
        raise CapabilityViolation(f"symlink rejected: {rel_path}")

    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise CapabilityViolation(f"path escapes job root: {rel_path}")

    # The real protection: it must be a file we deliberately staged.
    if resolved not in state.staged_files:
        raise CapabilityViolation(f"file not in scope for this ticket: {rel_path}")

    return resolved.read_text()
```

Stage with `follow_symlinks=False` so a symlinked file never enters `staged_files` in the first
place. The containment check and the staged-file allowlist are what actually carry the protection —
the symlink check is defense in depth, and it only works if it runs before resolution.

This is the difference between "the QA agent read the repo's `.env` because a code comment told it
to" and that attack being structurally impossible.

## 4. Human-in-the-loop as a designed gate, not a courtesy

AI 600-1 treats human oversight as a governance control. Two implementation requirements follow:

**a. Consequential actions are gated in code.** The agent proposes; a human approves; *then* the
system commits. A propose→approve→commit flow (chat agent writes a spec, user approves, pipeline
runs) is already this shape — keep it that way as capabilities grow. The gate is a state in the graph
(`awaiting_approval`), not a UI convention, so it cannot be bypassed by calling the API directly.

**b. Make disagreement cheap, or the gate is theatre.** Automation bias is the named risk: a PO
rubber-stamping 40 tickets is not oversight. Concretely:

- Per-item accept/edit/reject — never a single "approve all" as the primary action.
- Show the agent's *confidence and provenance* per ticket (which requirement lines produced it), so
  review is targeted rather than exhaustive.
- **Record the review**: `reviewed_by`, `reviewed_at`, `edited: bool`, per ticket. This is the
  human-oversight record (artifact #13) and it is also the most honest metric of output quality —
  the edit rate *is* the fit-criteria accuracy proxy.

```python
class TicketReview(BaseModel):
    ticket_id: str
    reviewer: str            # from auth context
    action: Literal["accepted", "edited", "rejected"]
    edit_distance: float     # 0.0 = untouched; a cheap automation-bias signal
    reviewed_at: datetime
```

A climbing accepted-untouched rate with no sampled deep reviews is your automation-bias alarm —
surface it on the same dashboard as quality metrics ([05-evaluation.md](05-evaluation.md)).

## 5. Agent-to-agent and memory surfaces

Persisted intermediate state is an injection/poisoning surface (OWASP LLM04, ATLAS memory
poisoning). In this architecture that means cached analysis artifacts and agent-authored
instruction files (e.g. `analysis.json`, `requirements_agent.md`) — content the agent *wrote in a
past turn* and *trusts in a future turn*:

- Validate them on **load**, not just on save (schema for the JSON; size/structure limits for the
  markdown). State written by an older code version, or tampered with in S3, must fail loudly.
- Stamp provenance into the artifact (`written_by`, `prompt_version`, `trace_id`) so a poisoned or
  stale artifact is attributable.
- Treat them as untrusted when composing prompts — same delimiting rules as user input
  ([02-untrusted-input.md](02-untrusted-input.md)). "The agent wrote it" is not a trust argument;
  the agent wrote it *under the influence of user input*.

## 6. What this buys, framework by framework

| Control | Satisfies |
|---|---|
| Capability manifest + enforcement | LLM06, ASI01 least-agency; ISO A.9.4 intended use; the "capabilities" section of the system card |
| Server-side identifier threading | HIPAA minimum necessary; multi-tenant isolation |
| Scoped code staging for QA agent | LLM06; minimum necessary applied to source code |
| Graph-state approval gates | AI 600-1 human oversight; EU AI Act Art. 14 shape |
| Review records + edit-rate metric | Artifact #13 human-oversight records; automation-bias monitoring |
| Load-time validation of persisted agent state | LLM04 poisoning; ATLAS memory poisoning |
