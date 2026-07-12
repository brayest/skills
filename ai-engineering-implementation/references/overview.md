# Software implementation — compliance requirements as code

Translation of the framework requirements (files `01`–`07` one level up) into **code-level design**
for the platform: agent design, prompt handling, data boundaries, observability, evaluation, and
CI/CD. Infrastructure-level controls (network, identity, cluster, cloud services) live in
the `ai-platform-implementation` skill.

Code examples are Python/FastAPI/LangGraph: pydantic at boundaries, fail-fast, no silent
fallbacks. They are patterns, not drop-in patches.

## Files

| File | Covers | Satisfies |
|---|---|---|
| [01-agent-design.md](01-agent-design.md) | Least-agency, tool binding scope, human-in-the-loop, automation-bias UX | OWASP LLM06/ASI01 · HIPAA minimum necessary · AI 600-1 human-AI configuration · ISO A.9 |
| [02-untrusted-input.md](02-untrusted-input.md) | Prompt injection defenses, instruction/data separation, output handling | OWASP LLM01/LLM05/LLM07 · MEASURE 2.7 |
| [03-data-boundary.md](03-data-boundary.md) | Data classification, egress redaction, de-identification, prompt hygiene | HIPAA · data residency · OWASP LLM02 · ISO A.7 |
| [04-observability.md](04-observability.md) | Decision traces, event logs, version stamping, incident hooks | ISO A.6.2.8 · MANAGE 4.1/4.3 · SP 800-218A RV · AI 600-1 incident disclosure |
| [05-evaluation.md](05-evaluation.md) | Eval harness, golden sets, red-team suite, drift detection | MEASURE 2.1/2.3/2.7/2.11 · ISO A.6.2.4 · LLM09 |
| [06-cicd.md](06-cicd.md) | Pipeline gates: SBOM, eval gates, prompt-change review, model pinning, release records | SP 800-218A · ISO A.6.2.3–2.5 · OWASP LLM03 |

## The design stance

Three decisions run through every file:

1. **The model is untrusted; the boundary is code.** Every guarantee we make to the client is
   enforced by deterministic code around the model — schema validation, scoped credentials, egress
   filters — never by prompt instructions. A prompt is a request; a pydantic validator is a control.
2. **Every LLM interaction is evidence.** Each call is stamped with prompt version, model ID, and
   trace ID, and is reconstructable after the fact. Compliance artifacts fall out of the telemetry;
   they are not written by hand later.
3. **Fail loud.** A redaction failure, a schema mismatch, or a missing config aborts the request.
   Degraded-but-running is the non-compliant state, per both the client's risk posture and our own
   engineering rules.
