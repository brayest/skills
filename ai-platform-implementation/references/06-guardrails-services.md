# Managed guardrails — Bedrock Guardrails and where they fit

**Requirement being implemented:** defense-in-depth for OWASP LLM01/LLM02/LLM09, AI 600-1
pre-deployment testing and content themes, and — tactically — the ability to say "yes, we use the
cloud provider's native AI safety controls" in a security review, which lands disproportionately
well relative to its cost.

Position honestly held throughout: **managed guardrails are the outer moat, not the castle.** Our
primary controls are the application-layer ones (capability manifests, redaction gateway, schema
validation, evals). Guardrails add a provider-operated, independently-updated layer that catches
some of what ours miss and — importantly for governance — is *attachable as policy* rather than
shipped as code.

---

## 1. What Bedrock Guardrails actually provides

Six policy types (exact names, per
<https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html>):

| Policy | Function | Relevant to us? |
|---|---|---|
| **Content filters** | harmful-content categories (Hate, Insults, Sexual, Violence, Misconduct, **Prompt Attack**), tunable strength, input+output | **Prompt Attack filter: yes** — a managed injection classifier we don't maintain. Harm categories: low value on requirement docs, cheap to leave on low. |
| **Denied topics** | natural-language topic blocks | Marginal for v1. For healthcare deployments, a "no clinical/diagnostic content" topic is a *very* good control to be able to show. |
| **Word filters** | exact-match blocklists (10k entries) | Client-named markers (project codenames, internal hostnames) as a cheap belt-and-suspenders on top of our redactor. |
| **Sensitive information filters** | managed PII entity detection + custom regex, redact or block | **Yes — the managed twin of our egress redactor.** Different engine, provider-maintained: exactly what defense-in-depth wants. |
| **Contextual grounding checks** | RAG grounding + relevance scoring, block below threshold | Not yet (no RAG). **The day retrieval lands, this is the managed hallucination control** — flag it in the LLM08/LLM09 plan now. |
| **Automated Reasoning checks** | formal-verification-style validation of responses against defined policy rules | Watch. New; if it matures, verifying ticket outputs against structural rules is our shape of problem. |

Two platform facts that matter more than any single filter:

- **Org-wide enforcement**: Guardrails can be attached via AWS Organizations policy, so "every
  model call in these accounts passes a guardrail" is an org invariant, not per-app diligence:
  <https://docs.aws.amazon.com/organizations/latest/userguide/orgs_manage_policies_bedrock.html>
- **AWS's own OWASP mapping names Guardrails as the control** for prompt-injection filtering and
  sensitive-output blocking (best practice 4.2 in the Agentic AI Security guidance):
  <https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-security/owasp-top-ten.html>
  — meaning our stack matches AWS's published prescriptive posture, which is a sentence worth
  putting in front of a reviewer verbatim.

## 2. How it composes with our layers

Request path, outermost-in:

```
ingest screen (ours) → prompt construction w/ fencing (ours) → egress redactor (ours)
  → Guardrail input policies (AWS)  → model → Guardrail output policies (AWS)
  → schema validation (ours) → persistence w/ provenance (ours)
```

### Attaching a guardrail is not enforcing one

The single most important thing in this file: **a guardrail the application chooses to pass is a
guardrail the application can forget to pass.** If the guardrail ID is a parameter in your
`InvokeModel` call, then a bug, a new code path, a debugging shortcut, or a compromised container
simply omits it — and the call still succeeds. That is a default-allow control, and it will not
survive a serious review.

Make it **default-deny at the IAM layer**: condition the agent role's `bedrock:InvokeModel*`
permission on the guardrail being present, so a call *without* the guardrail is denied by AWS rather
than merely unprotected.

```json
{
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Converse"],
  "Resource": "arn:aws:bedrock:us-east-1::foundation-model/<approved-model-id>",
  "Condition": {
    "StringEquals": { "bedrock:GuardrailIdentifier": "<guardrail-arn>:<version>" }
  }
}
```

Now "every model call passes a guardrail" is an *invariant enforced by the cloud provider*, not a
promise your codebase makes. Pin the guardrail **version** in the condition too, so a guardrail
config change is a reviewed, deliberate rollout rather than a silent behavior shift under a
floating pointer. Verify the exact condition-key name against the current Bedrock service
authorization reference before shipping — this is precisely the sort of detail that shifts between
service releases.

Rules of composition:

- **Guardrail hits are trace events.** A guardrail block/redaction lands on the LLM span
  (`guardrail_action` field) exactly like our redactor's report — same monitoring, same incident
  triggers. A rising Prompt Attack hit rate is the same alarm whether our heuristic or AWS's
  classifier saw it first, and *disagreement between the two layers is itself the interesting
  signal* (one engine is drifting or being evaded).
- **Blocks fail loud.** A guardrail intervention on the output side means the generation failed —
  surface it as a failed operation with a trace ID, never silently retry into a degraded answer.
- **Guardrail configs are IaC.** Versioned, reviewed, drift-detected like endpoint policies
  ([05-supply-chain.md](05-supply-chain.md) §2). A guardrail nobody can diff is a control nobody
  can audit.
- **Don't double-block.** Our redactor blocks hard identifiers pre-egress; the Guardrail PII filter
  runs in *redact* mode as backstop, not block mode — otherwise legitimate synthetic-data demos
  trip on lookalike patterns and the team learns to route around the control, which is how controls
  die.

## 3. The Azure equivalent

Direct equivalent: **Azure AI Content Safety** (harm categories, Prompt Shields for
injection, groundedness detection) attached at the AI Foundry endpoint. The mapping is
close enough that the composition diagram above survives unchanged — which is the point of keeping
our own layers primary and the managed layer swappable. Write the guardrail policy once as a
provider-neutral YAML (categories, thresholds, PII entities, topics) and compile it to
Bedrock/Azure configs in the values layer, same pattern as every other provider binding.

## 4. Eval the guardrail too

A guardrail is a model making decisions about our traffic; it gets the same treatment as any model:
the red-team corpus runs **with guardrails attached** (measuring the stack, not the parts), a small
benign-traffic corpus watches the false-positive rate, and guardrail config changes ride the
pipeline with eval gates like a prompt change. Threshold tuning without an eval run is the same sin
as a model bump without one.

---

## Bottom line

Turn on: Prompt Attack filter, sensitive-information filter in redact mode, minimal word filter —
attached org-wide, configs in IaC, hits traced. Defer: denied topics until a deployment context
calls for them (e.g. the clinical-content topic in healthcare), contextual grounding until RAG,
Automated Reasoning until it proves out.
Cost is near-zero engineering; yield is a provider-maintained second net plus alignment with AWS's
own prescriptive guidance — the rare compliance control that is genuinely cheap.
