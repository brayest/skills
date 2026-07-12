# Identity and access — least privilege as the platform's spine

**Requirement being implemented:** HIPAA minimum-necessary at the infrastructure layer, OWASP LLM06
(Excessive Agency) enforced below the application, ISO 42001 A.4/A.9, GOVERN 6 (third-party model
access governed), the no-access-keys rule.

The principle from `01-agent-design` in the `ai-engineering-implementation` skill — the capability
manifest — exists here as its enforcing twin: **one IAM role per service, whose policy is the
manifest compiled to infrastructure.** The manifest catches bugs; the role catches everything,
including a fully compromised container.

---

## 1. Workload identity — no keys, anywhere

- **In-cluster (AWS today): EKS Pod Identity** for new clusters — AWS's simpler successor to IRSA
  (no OIDC provider per cluster, roles reusable across clusters via the single
  `pods.eks.amazonaws.com` principal, credentials issued per-node by the EKS agent):
  <https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html>. IRSA remains the fallback
  where Pod Identity isn't supported (Fargate, Windows, non-EKS). Either way the property that
  matters is the same: **credentials are scoped to the service account, short-lived, and never in
  env vars or files.**
- **Local dev**: the `~/.aws` credential chain via mounted profile (already the repo rule).
- **CI**: OIDC federation from the CI provider to a deploy role — no long-lived deploy keys.
- **Bedrock API keys: banned org-wide.** Bedrock now supports bearer-token API keys; they recreate
  exactly the static-credential problem. Deny via SCP on `bedrock:BearerTokenType` /
  `bedrock:CallWithBearerToken` condition keys:
  <https://aws.amazon.com/blogs/security/securing-amazon-bedrock-api-keys-best-practices-for-implementation-and-management/>
- **Azure equivalent**: AKS Workload Identity (federated managed identities); the Helm values that
  name a service account annotation on EKS name a client ID there.

## 2. Per-service roles — the compiled capability manifests

Four services, four roles, no sharing:

| Role | May | May not (deny or absent) |
|---|---|---|
| `ui` | nothing on AWS | everything — it talks only to the gateway |
| `gateway` | S3 `Get/Put` on `sessions/*` (uploads), RDS connect | **any `bedrock:*`** — the gateway routes, it never invokes models |
| `product-agent` | `bedrock:InvokeModel*` on **named model ARNs only**; S3 `Get/Put` on `sessions/*`; RDS connect | S3 delete-bucket-level, any other model ID, any network write elsewhere |
| `qa-agent` | same shape, its own paths + read on the code-staging prefix | write access to product artifacts |

Details that carry the audit weight:

- **Model allowlisting by resource ARN**: `bedrock:InvokeModel` scoped to specific
  `foundation-model/...` and inference-profile ARNs. An agent physically cannot call a model that
  hasn't been through the eval pipeline. Backstop it org-wide with an SCP allowlist so even a
  misconfigured role can't reach unapproved models or regions:
  <https://aws.amazon.com/blogs/security/implementing-least-privilege-access-for-amazon-bedrock/>
  (SCP caveat: third-party marketplace models evaluate marketplace actions as `us-east-1` — region
  conditions must target the Bedrock actions themselves, not the subscription actions.)
- **S3 paths mirror the manifest**: the product agent's policy grants `sessions/${aws:PrincipalTag/...}`-
  style prefixes where feasible; at minimum, prefix-scoped to `sessions/*` with object tagging by
  `data_class` and a bucket policy that denies untagged writes. Per-session IAM scoping is not
  practically expressible — which is exactly why the application-layer manifest check exists
  (`01-agent-design` in the `ai-engineering-implementation` skill §2). Two layers, honestly
  divided: IAM does coarse (service × prefix × action), code does fine (session × record).
- **VPC endpoint policy as the third net**: the Bedrock PrivateLink endpoint's resource policy
  repeats the model-ARN allowlist, so a leaked credential used from inside the VPC still can't
  reach other models, and no credential works from outside the VPC at all
  ([03-network-egress.md](03-network-egress.md)).

## 3. Human access

- **No standing human access to production data.** Break-glass role, MFA, time-boxed sessions,
  every assumption CloudTrail-logged and alerted on. With a team of one this feels ceremonial; it
  is precisely what a HITRUST-certified client's security review asks about first, and "the
  engineer can read our requirements DB whenever" is the wrong answer even when the engineer is
  trustworthy.
- **Trace-store payload tier** (`04-observability` in the `ai-engineering-implementation` skill
  §3) gets its own role; access to raw prompts is logged access, distinct from dashboard access.
- The client's future platform team gets read access defined *now* (dashboards yes, payloads by
  their own policy) — access design is part of the handover deliverable, not an afterthought.

## 4. What this maps to

| Control | Satisfies |
|---|---|
| Pod Identity / no static credentials anywhere | HIPAA safeguards · the no-keys rule · HITRUST access-control domain |
| Role-per-service, deny-by-absence | LLM06 below the app layer · minimum necessary |
| Model-ARN allowlists in role + SCP + endpoint policy | GOVERN 6.1 (third-party model use governed) · change-controlled model adoption |
| Break-glass + logged payload access | HITRUST · ISO A.9 · the client conversation |
