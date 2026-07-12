---
name: ai-platform-implementation
description: Design the cloud and Kubernetes infrastructure that makes an LLM or agentic workload safe for a regulated client — tenancy and data-residency boundaries, workload identity and per-service IAM, model allowlisting via IAM/SCP/VPC-endpoint policy, default-deny egress and NetworkPolicies, audit logging (CloudTrail, Bedrock model invocation logging, Object Lock), supply-chain enforcement (image signing, admission control, IaC policy-as-code), and managed guardrails (Bedrock Guardrails, Azure AI Content Safety). Use this whenever the question is about where an AI workload runs and what it can reach: architecting a HIPAA-ready GenAI deployment, deciding whether the model endpoint or trace store sits inside the client's tenant, locking down Bedrock access across an org, EKS/AKS security for agent workloads, private endpoints vs. internet egress, what to turn on for AI audit evidence, or moving an AI platform into a client's cloud tenant. Trigger it even without the word "compliance" — "can we call Bedrock without going over the internet", "our client won't let data leave their tenant", "which IAM role should the agent pod use", "how do we stop an agent from reaching the internet", "set up guardrails on our model calls", or "review this AWS architecture for our LLM app" all belong here. This skill produces INFRASTRUCTURE design (Terraform/Helm/IAM/network); for application code use `ai-engineering-implementation`, and for assessing a system against frameworks use `ai-compliance-evaluator`.
---

# AI Platform Implementation

You are designing the infrastructure that a regulated client's security team will actually inspect.
Guidance is pattern-first and cloud-agnostic — AWS is the worked example because it has the
best-documented GenAI security guidance, and Azure equivalents are noted throughout so the pattern
survives a move into a client's own tenant.

The output should be architecture and infrastructure-as-code, not a lecture. Name the service, the
policy, the setting — and say which ones are **off by default**, because that is where real
deployments quietly fail.

## Start here: the traps, not the tutorial

You already know how to build this. Default-deny egress, PrivateLink, NetworkPolicies, per-service
IAM roles — that knowledge is not what this skill is for, and re-deriving it wastes the reader's
time. **What separates a design that survives a security review from one that doesn't is a short list
of defaults, bypasses, and enforcement gaps that are easy to miss and expensive to miss.** Lead with
these; the references have the full designs when you need them.

**The controls you think are on are off.** These are all **disabled by default**, and a posture
built on the assumption they are running is fiction:
- **Bedrock model invocation logging** (the actual record of prompts and completions) — off.
- **CloudTrail data events** — off. Default CloudTrail tells you an invocation happened, *not* what
  the agent runtime did.
- **EKS control-plane logs** (all five: api, audit, authenticator, controllerManager, scheduler) — off.
- **Route 53 Resolver query logs** (DNS is an exfiltration channel) — off.

An "enablement checklist" of these is often the single most useful artifact you can hand a reviewer.

**Attaching a control is not enforcing it.** A guardrail passed as a parameter in `InvokeModel` is a
guardrail a code path can omit. Condition the IAM permission on `bedrock:GuardrailIdentifier` so an
un-guardrailed call is *denied by AWS*, not merely unprotected. Same logic everywhere: prefer the
control the workload cannot opt out of.

**NetworkPolicy has a bypass.** A pod with `hostNetwork: true` shares the node's network namespace
and NetworkPolicy does not apply to it. Every egress rule is void for that pod. Close it with Pod
Security Admission (`restricted`) plus Kyverno/OPA — otherwise your egress posture is a convention,
not a control.

**Cross-region inference silently breaks a residency promise.** Bedrock inference profiles can route
processing to another region, and newer profiles often default to it. Worse, CloudTrail and
invocation logs record in the *source* region regardless — so the logs look consistent with a
single-region story even when it isn't true. The profile configuration is the evidence; the logs are
not.

## Three stances that decide most design questions

**1. The boundary is enforced twice.** Every residency and least-privilege guarantee exists once in
application code and once in infrastructure (IAM, network policy, endpoint policy). Either layer
failing alone is a detected near-miss rather than a breach. When you design a control here, know
which application-layer control it backstops — and vice versa.

**2. Deny by default, allow by name.** Egress, IAM actions, model IDs, registries, namespaces —
allowlists everywhere. A new capability should be a reviewed diff, not a discovered behavior. And an
allowlist fails closed where a denylist fails open: the dangerous thing you forgot to list is the one
that gets through.

**3. Audit is infrastructure, not application courtesy.** CloudTrail, model invocation logs, and K8s
audit logs exist *even when the application code is compromised or wrong*. That independence is
exactly what makes them evidence rather than telemetry.

## The threat model to hold

In an agentic system, **every reachable network destination is an exfiltration channel available to a
hijacked agent** — and a tool call is an egress channel. MITRE ATLAS names exfiltration-through-tool-
calls explicitly. The network's job is to make the set of reachable destinations equal to the set of
named, reviewed dependencies, so that prompt injection can at worst misuse an approved channel
(which application controls then constrain) rather than open a new one.

Useful shared vocabulary with a client's security team: **AWS's GenAI Security Scoping Matrix**. An
application built on hosted foundation models is **Scope 3**, which sets the depth of the five
disciplines AWS prescribes (governance, legal/privacy, risk management, controls, resilience).

## Workflow

1. **Establish the boundary before anything else.** Is there a data-residency clause? Where must the
   model endpoint, the trace store, and the *log destinations* live? Getting this wrong invalidates
   every downstream decision — and log/trace placement is the one people forget.
2. **Determine the deployment posture**: vendor-hosted, client tenant, or a sandbox tier that must
   structurally refuse real data.
3. **Read the relevant reference** (routing below) and produce the design: architecture, IAM, network
   policy, audit configuration, pipeline enforcement.
4. **Enumerate what is off by default and must be turned on.** This list is the deliverable a
   security reviewer actually wants.
5. **Note the application-layer half.** If the control needs code too (redaction, capability
   manifests, schema validation), say so and point at `ai-engineering-implementation`.

## Reference routing

| Task | Read |
|---|---|
| Orientation, the three stances, AWS source guidance, Scope 3 framing | `references/overview.md` |
| The residency boundary; where the model endpoint/trace store/logs must sit; environment tiers; K8s layout; multi-tenancy; encryption baseline; model-availability resilience | `references/01-architecture.md` |
| Workload identity (EKS Pod Identity vs IRSA, AKS Workload Identity); per-service roles; model-ARN allowlists; SCPs; break-glass human access | `references/02-identity-access.md` |
| Default-deny egress; PrivateLink/VPC endpoints; NetworkPolicies; DNS as an egress channel; ingress and WAF; what to demo to a reviewer | `references/03-network-egress.md` |
| CloudTrail (management vs data events); Bedrock model invocation logging; EKS control-plane logs; Object Lock and retention; the alarm set; Azure equivalents | `references/04-audit-logging.md` |
| Image signing and admission control; IaC policy-as-code and drift detection; governing the model as a supplier across org/account/role/endpoint/pipeline layers | `references/05-supply-chain.md` |
| Bedrock Guardrails (the six policy types) and Azure AI Content Safety; how managed guardrails compose with application-layer controls; evaluating the guardrail itself | `references/06-guardrails-services.md` |

## Further traps (beyond the four at the top)

- **The model endpoint, the trace store, and the log destinations are all inside the boundary.**
  Shipping logs or traces to a vendor-owned aggregation account moves client data across the
  boundary through the telemetry channel — the classic silent violation. So does a SaaS
  observability vendor.
- **The framework's own persistence is an undeclared data store.** Agent checkpointers and message
  history retain full document content indefinitely with no default TTL. It never appears on the
  data-flow diagram because the framework writes it, not your code. In a HIPAA context that is an
  undeclared PHI store — give it a TTL and a purge job.
- **HIPAA-eligible ≠ compliant.** It requires the service designation, an executed BAA (via AWS
  Artifact), *and* correct configuration. BAA coverage varies by endpoint, feature, and
  sub-processor — telemetry and preview features are commonly out of scope even when the base model
  endpoint is in.
- **Re-verify the HIPAA-eligible services list against the live AWS page** before any compliance
  claim. It changes; a snapshot in a document (including these references) is not a source.
- **Bedrock API keys recreate the static-credential problem.** Deny them org-wide via SCP
  (`bedrock:BearerTokenType`) and use workload identity.
- **Guardrails are the outer moat, not the castle.** A provider-maintained second net over your own
  controls, and cheap — but a guardrail nobody can diff is a control nobody can audit. Configs in
  IaC, every hit traced, and enforced via IAM condition rather than passed as a parameter.
- **Cite evidence that actually proves the claim.** IAM Access Analyzer does not prove an agent
  cannot write to an external bucket; an S3 endpoint policy with an `aws:ResourceAccount` /
  `aws:ResourceOrgID` condition does. A reviewer who catches a control cited for something it does
  not do will discount everything else you showed them.
