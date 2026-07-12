# Architecture — tenancy, residency, and the boundary

**Requirement being implemented:** client data-residency constraints, HIPAA Security Rule
(safeguards around ePHI-class data), ISO 42001 A.6 (lifecycle/deployment), AWS GenAI Scoping Matrix
Scope 3 disciplines.

---

## 1. The boundary, drawn precisely

A residency clause says client data never leaves the client's environment. Architecturally that
means one thing: **the compliance boundary is a tenant, and every component that touches client data
— including the model endpoint, the trace store, and the logs — lives inside it.**

```
┌─ Client tenant (boundary = everything client data touches) ──────────────┐
│                                                                          │
│  K8s cluster (EKS / AKS)                                                 │
│   ├─ ui, api (gateway), product-api, qa-api                              │
│   ├─ trace store (self-hosted: Langfuse/Phoenix + OTLP)                  │
│   └─ eval runners (online sampling)                                      │
│                                                                          │
│  Postgres (RDS/Azure DB) · S3/Blob (artifacts) · KMS/Key Vault           │
│  Model endpoint: Bedrock via PrivateLink │ Azure AI Foundry endpoint     │
│  Logs/audit: CloudTrail + invocation logs → locked bucket IN-tenant      │
│                                                                          │
└──── egress: default-deny; named endpoints only ──────────────────────────┘
        ▲
        │  what crosses OUT: nothing containing client data.
        │  Aggregated metrics/eval scores may cross by explicit agreement.
```

Three placements people get wrong, called out explicitly:

- **The model endpoint is inside the boundary.** On AWS: Bedrock reached via a VPC interface
  endpoint (PrivateLink) in the same region — traffic never touches the public internet, and AWS's
  data-use commitment (prompts/completions **not** used to train models, not shared with model
  providers; providers run in AWS-isolated accounts) plus the BAA make the service side defensible:
  <https://aws.amazon.com/bedrock/amazon-models/privacy/>. On Azure: the AI Foundry endpoint inside
  the client's own subscription — the cleanest possible residency story, which is why a
  client-tenant deployment is the strongest production posture for residency-constrained clients.
- **The trace store is inside the boundary** (payloads contain client prompts —
  `04-observability` in the `ai-engineering-implementation` skill §3). No SaaS observability.
- **Log destinations are inside the boundary.** Model invocation logs and CloudTrail land in a
  bucket in the same account/region. Shipping logs to a vendor-owned aggregation account would move
  client data across the boundary in the telemetry channel — the classic silent violation.

### The residency trap: cross-region inference profiles

This is the one that silently breaks a residency promise you have already made in writing, so treat
it as a first-class check rather than a footnote.

Bedrock's **cross-region inference** routes a request to a different region for processing when
capacity demands it. Data stays on the AWS backbone and stays encrypted — but the **processing
region changes**, and abuse-detection storage (where it exists) occurs in the *destination* region.
Many newer models are consumed through an **inference profile** rather than a bare model ID, and
newer profiles commonly default to cross-region behavior. So a team can promise "your data stays in
us-east-1," pin what looks like a region-specific model, and be wrong — without changing a line of
code.

What to do:

- **Know which you are on.** Inspect the model IDs and inference profiles actually in use. A profile
  ARN is not the same commitment as a single-region foundation-model ARN.
- For a residency-constrained client: **single-region model IDs, or at most a geographic (e.g. US)
  inference profile — never Global.**
- **Constrain it in policy, not in prose:** the model-ARN allowlists in the agent role, the SCP, and
  the VPC endpoint policy should name the exact single-region or geographic profile ARNs, so a
  Global profile cannot be invoked even if application config drifts.
- **The audit nuance that misleads people:** CloudTrail and invocation logs record in the **source**
  region regardless of where inference actually ran. So your logs will *look* consistent with a
  single-region story even when processing crossed a boundary. The logs are not evidence for this
  particular claim — the profile configuration is.

<https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html>

Azure has the same shape of decision: a **Global** deployment of a model in AI Foundry versus a
**Regional/Data Zone** deployment. Same question, same answer for a residency-constrained client —
pick the regionally-bounded option and verify it, do not inherit the default.

## 2. Environment tiers and the data rule per tier

| Tier | Where | Data allowed | Purpose |
|---|---|---|---|
| **dev / CI** | vendor sandbox | `SYNTHETIC` only — enforced at the API (`03-data-boundary` in the `ai-engineering-implementation` skill §1), not just agreed | development, eval suite, red team |
| **demo** | vendor sandbox, isolated namespace | `SYNTHETIC` only; **no connections to client systems** | client demo sessions |
| **pilot / prod** | **client tenant** | client data | the real thing |

The two-enforcement rule applies to the tier boundary too: the API refuses non-synthetic data
classes in sandbox tiers (code), *and* the sandbox has no network route or credential to any client
system (infrastructure). A developer cannot violate the residency clause by accident; they would
have to defeat both layers deliberately.

## 3. Kubernetes layout — isolation inside the cluster

Per the EKS best-practices guidance (private clusters, network policy, audit logging —
<https://docs.aws.amazon.com/eks/latest/best-practices/network-security.html>):

- **Private cluster**: API server endpoint private-only in pilot/prod; no public control plane.
- **Namespace per surface** (`platform-ui`, `platform-gateway`, `agents-product`, `agents-qa`,
  `observability`), with default-deny NetworkPolicies between them
  ([03-network-egress.md](03-network-egress.md)). The gateway→qa-api proxy path is a named allow,
  not an open east-west network.
- **Node isolation for agent workloads** is not required at this scale — the agents are I/O-bound
  API callers, not GPU tenants. Revisit if self-hosted models ever enter the picture; the isolation
  unit then becomes the node group.
- **Multi-tenancy** (the reusable-platform future): tenant = namespace set + own Postgres
  database + own S3 prefix + **own KMS key** + own IAM role chain. Key-per-tenant is the control
  that makes "delete tenant" and "prove tenant isolation" both one-step answers. Do not build
  row-level multi-tenancy inside one database for regulated clients; the isolation story is too
  hard to audit.

## 4. Encryption baseline

Boring, mandatory, and mostly one-time:

- **At rest**: KMS CMKs (not AWS-owned default keys) for S3, RDS, EBS, and **EKS secrets envelope
  encryption** (default on k8s ≥1.28; verify on cluster creation —
  <https://docs.aws.amazon.com/eks/latest/userguide/envelope-encryption.html>). CMKs because key
  policy = a second, IAM-independent access-control layer, and because revocation is a real
  offboarding story for the client.
- **In transit**: TLS everywhere including in-cluster (mesh or per-service certs — at this service
  count, cert-manager per-service is simpler than adopting a mesh for compliance's sake).
- **Azure equivalents**: Key Vault + CMK on Storage/Database, AKS secrets encryption, Private Link
  to AI Foundry. The pattern survives a cloud move because it was chosen at the pattern level; only
  provider bindings change (which is the Terragrunt/Helm-values layer's job).

## 5. Resilience (Scoping Matrix discipline 5, GOVERN 6.2)

The contingency that actually matters at Scope 3 is **model availability, deprecation, and behavior
change**, not zonal failure:

- Multi-AZ for the boring parts (RDS, nodes) — table stakes, cheap.
- **Model contingency is a tested procedure, not an architecture**: pinned model IDs, a documented
  fallback model per agent, and the eval suite as the gate that validates a fallback actually
  works before it's needed (`06-cicd` in the `ai-engineering-implementation` skill §4). Bedrock model
  EOL announcements feed the risk register with a date attached.
- Degraded mode is a *product* decision made now: if the model endpoint is down, the platform
  queues work and says so — it does not fall back to a weaker unevaluated model silently. (Fail
  loud, applied at the architecture level.)
