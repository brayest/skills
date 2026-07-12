# "What stops the agent from sending data somewhere it shouldn't?"

Reframe the question for them first, because it's the frame that makes the rest of the answer legible:

> In an agentic system, **every reachable network destination is an exfiltration channel available to a hijacked agent** — and a tool call is an egress channel. So the control isn't "we trust the model not to." The control is that the set of destinations the agent pod can reach equals the set of named, reviewed dependencies. Prompt injection can at worst misuse an approved channel; it cannot open a new one.

That's MITRE ATLAS's exfiltration-through-tool-calls and OWASP LLM02, and it's the standard a security reviewer is (usually without saying so) actually testing you against.

Then show four layers, in this order, because each one is what makes the previous one's failure survivable.

---

## 1. The network: default-deny egress, allow by name

This is the load-bearing answer. Everything else is depth.

- **No NAT-to-anywhere.** Agent workloads run in private subnets. The list of things the platform legitimately needs to reach is short enough to write on a napkin — Bedrock, S3, RDS, KMS, ECR, CloudWatch, STS — **and every one of those has a VPC endpoint.** So the honest target is *zero* internet egress from workload subnets, not "restricted" egress. If you're running a NAT gateway for the agent nodegroup today, that's the finding, and it's the one to fix before the review.
- **Bedrock over PrivateLink.** Interface endpoint with private DNS, so `bedrock-runtime.*` resolves in-VPC with no code change. The model call never touches the internet.
- **S3 via gateway endpoint with an endpoint policy carrying an `aws:ResourceAccount` condition.** This one is worth calling out explicitly to the reviewer: tight IAM on *your* buckets does nothing to stop `PutObject` to an attacker-owned bucket. The endpoint policy is what closes that path.
- **DNS is egress too.** An agent that can resolve arbitrary names can tunnel data out through queries alone. Cluster resolver only, external resolvers blocked in NetworkPolicy, Route 53 Resolver query logs on in prod.

**In-cluster, NetworkPolicy default-deny ingress+egress per namespace**, then the named flows only. VPC CNI enforces NetworkPolicy natively on EKS. What's absent on purpose is as important as what's present — show them the deny list, not just the allow list:

```
gateway     → agent-api:8000, RDS, S3-endpoint
agent-api   → Bedrock-endpoint, RDS, S3-endpoint, otel-collector
otel        → trace-store
everything  → kube-dns:53 (cluster resolver only)

absent on purpose: agent→internet, agent→agent, anything→trace-store except the collector
```

## 2. Identity: the agent's role is the capability list, compiled

- **EKS Pod Identity** (or IRSA), one role per service, no sharing. Credentials scoped to the service account, short-lived, never in env vars or files.
- **The gateway role has no `bedrock:*` at all** — it routes, it never invokes. Only the agent role can call a model.
- **`bedrock:InvokeModel*` scoped to named model ARNs.** The agent physically cannot call a model that hasn't been through your eval pipeline.
- **Ban Bedrock API keys org-wide via SCP** (`bedrock:BearerTokenType` / `bedrock:CallWithBearerToken` condition keys). They're new, and they recreate exactly the static-credential problem you eliminated with Pod Identity. A reviewer who knows Bedrock will ask.

## 3. The endpoint policy: the same allowlist, a third time

The Bedrock PrivateLink endpoint's resource policy repeats the model-ARN allowlist and scopes to your agent roles. The point of the repetition — say this out loud in the review — is that **a leaked credential used from inside the VPC still can't reach other models, and no credential works from outside the VPC at all.** Model access is governed at four layers (SCP → account model grants → role → endpoint policy) so that no single misconfiguration un-governs it.

## 4. Guardrails: the outer moat, not the castle

Bedrock Guardrails, attached **org-wide via Organizations policy** so "every model call in these accounts passes a guardrail" is an org invariant rather than per-app diligence. Turn on: the **Prompt Attack** filter (a managed injection classifier you don't maintain), the **sensitive-information filter in redact mode** (managed twin of your own egress redactor — different engine, provider-maintained, which is exactly what defense-in-depth wants), and a small word filter for client-named markers. Configs in IaC, hits traced.

Be honest about the ordering: this is the provider's second net over your controls, not your primary one. Reviewers respect that framing more than they respect "we use AWS Guardrails" as a headline.

---

## The enablement checklist — this is the deliverable they actually want

The controls that matter most are **off by default**, and "we have CloudTrail" does not mean the agent runtime is logged. Walk in with this table filled out:

| Surface | Default | You need |
|---|---|---|
| CloudTrail management events (who called which model, when) | on | keep, org trail |
| **CloudTrail data events** (Bedrock agent-runtime, S3 object-level) | **off** | enable |
| **Bedrock model invocation logging** (full request/response payloads) | **off** | enable → in-tenant bucket only |
| **EKS control-plane logs** (all five: api, audit, authenticator, controllerManager, scheduler) | **off** | enable all five |
| Route 53 Resolver query logs (DNS egress attempts) | off | enable in prod |
| GuardDuty + Security Hub | varies | on, findings routed |

Ship audit logs to **S3 with Object Lock in COMPLIANCE mode** + CloudTrail log-file integrity validation. Object Lock COMPLIANCE mode means nobody, including root, can shorten retention — that single property is what converts "we keep logs" into "our logs are evidence."

And the trap that bites people at exactly this point: **the trace store and the log destinations are inside the boundary too.** If your OTel/Langfuse traces or your logs ship to a vendor-owned aggregation account, you have built an exfiltration channel with your own telemetry pipeline and it will not survive the review. Check this before they do.

## The alarm set

An audit log nobody reads is decoration. Minimum:

- Bedrock invocation by **any principal other than the agent roles** — the "someone found a credential" alarm.
- Invocation of a **model ID outside the allowlist** — should be impossible across four policy layers; if it fires, a policy layer changed, and that's a capability-violation incident by definition.
- NetworkPolicy or VPC-endpoint-policy modification. Object Lock bucket policy changes.
- `kubectl exec` into an agent pod in prod (EKS audit log filter).

---

## What to actually put in front of them in the room

One diagram (the boundary, with the named flows from §1 overlaid) and **two live proofs**:

1. **The 30-second `kubectl` demo.** Shell into an agent pod. `curl https://example.com` → blocked. `dig example.com` against an external resolver → blocked. `aws s3 cp` to a bucket outside the allowed account → denied by endpoint policy. This lands the argument better than any document you can write, and it's the one thing a skeptical reviewer remembers.
2. **The policies as code, in the repo, with a review history.** VPC endpoint policies, the SCP, NetworkPolicies, the guardrail config — all Terraform, all PR-reviewed. This is the difference between "we configured it" and "a new destination is a reviewed diff, not a discovered behavior." Back it with Checkov/OPA rules on the plan asserting the invariants (endpoint policies not widened, invocation logging not disabled, Object Lock not removed) and drift detection on the boundary resources alerting as a **security** event, not a hygiene ticket.

## The one gap to name yourself

IAM and the network do **coarse** (service × prefix × action × destination). They cannot express "this agent may only touch *this session's* records." That fine-grained half is application code — a capability manifest, an egress redactor in front of the model call, schema validation on outputs. Say so, and say which layer backstops which; a reviewer trusts the architect who volunteers the boundary of their own control far more than the one who claims the infrastructure handles everything.

If you want to build that half, it's the `ai-engineering-implementation` skill's territory.

## The sentence to close with

> "Bypassing this requires defeating code review, image signing, admission control, IAM, the endpoint policy, and NetworkPolicy simultaneously. Each of those failures is independently logged and alarmed. That stacked cost is the design."

Useful shared vocabulary if their team has an AWS background: this is **Scope 3** on AWS's Generative AI Security Scoping Matrix, and the stack above maps 1:1 onto AWS's own prescriptive guidance for agentic AI security. Saying "our controls match AWS's published posture for our scope" does real work in a review.
