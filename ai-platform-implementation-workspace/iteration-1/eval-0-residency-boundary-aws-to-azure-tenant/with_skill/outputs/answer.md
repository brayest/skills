# Residency boundary: what moves into the Azure tenant, what stays on AWS

**Short answer:** everything that *touches client data* moves — and that list is longer than people expect, because it includes the model endpoint, the trace store, and the log destinations. Everything that touches only *your* code and *synthetic* data stays: CI, image build, dev/demo tiers, eval corpora, Terraform. Bedrock does not move — you replace it, because there is no way to put a Bedrock endpoint inside an Azure subscription.

Before you design anything, ask one question that could collapse this whole exercise (below, §5).

---

## 1. Draw the boundary first — it invalidates every downstream decision if you get it wrong

The compliance boundary is **the client's Azure tenant**, and the rule is: *every component that touches client data lives inside it.*

```
┌─ Client Azure tenant (boundary) ──────────────────────────────────┐
│                                                                   │
│  AKS: ui · gateway · product-api · qa-api                         │
│  Trace store (self-hosted Langfuse/Phoenix + OTLP)                │
│  Azure Database for PostgreSQL · Blob (artifacts) · Key Vault CMK │
│  Model endpoint: Azure AI Foundry, private endpoint               │
│  Guardrail: Azure AI Content Safety at the endpoint               │
│  Logs: Activity Log + Foundry diagnostics → immutable Storage     │
│                                                                   │
└── egress: default-deny; named private endpoints only ─────────────┘
        ▲
        │ what crosses OUT: nothing containing client data.
        │ Aggregated metrics / eval scores only, by explicit written agreement.
```

## 2. What has to move

| Component | Today | In their tenant | Why it's non-negotiable |
|---|---|---|---|
| **Model endpoint** | Bedrock | **Azure AI Foundry** endpoint in *their* subscription, private endpoint, public network access disabled | Prompts and completions are client data. A PrivateLink-to-your-Bedrock story still terminates in *your* AWS account's region — that is data leaving their tenant. This is the item with no workaround. |
| **Agent + gateway runtime** | EKS | **AKS**, private cluster, private API server | It holds the payloads in memory and on disk |
| **Trace store** | wherever it is now | **Self-hosted in-tenant.** No SaaS observability — no Langfuse Cloud, no Datadog LLM Obs, no vendor-side OTLP collector | Spans carry the raw prompts. This is the #1 silently-violated boundary. |
| **Log destinations** | CloudTrail / Bedrock invocation logs → your bucket | **Foundry diagnostic settings + Activity Log + AKS control-plane logs → immutable Storage in their tenant** | Shipping model-invocation logs to a vendor-owned aggregation account moves client data across the boundary *through the telemetry channel*. This is the one everybody forgets. |
| **Primary data stores** | RDS, S3 | Azure Database for PostgreSQL, Blob, **customer-managed keys in their Key Vault** | Obvious, but the *key* matters: CMK in their Key Vault gives them an IAM-independent revocation story — "delete the key" is a real offboarding answer |
| **Managed guardrail** | Bedrock Guardrails | **Azure AI Content Safety** (Prompt Shields, PII detection, groundedness) attached at the Foundry endpoint | Guardrail evaluation sees the prompt |
| **Ingress / auth** | your ALB + WAF | App Gateway/Front Door + WAF, **their SSO**, tenant-owned certs | Auth happens before any request reaches an agent |
| **Registry (prod pulls)** | your ECR | **Their ACR**, images promoted in signed | Cluster follows the no-internet-egress rule, so it can't pull from your ECR anyway |

## 3. What can stay on AWS

Only if the tier **structurally cannot hold client data** — enforced twice: the API refuses non-`SYNTHETIC` data classes *and* the sandbox has no network route or credential to any client system. A developer must not be able to violate the residency clause by accident.

| Stays | Condition |
|---|---|
| **dev / CI tier** (including Bedrock for dev-time model calls) | `SYNTHETIC` data only, enforced at the API, not by agreement |
| **demo tier** | synthetic only, isolated namespace, **zero connections to client systems** |
| **CI pipeline**: build, SBOM, vuln scan, cosign signing, eval + red-team gates | CI never sees client data. It produces signed artifacts; the tenant verifies signatures at admission. |
| **Terraform/Terragrunt + Helm charts, prompts, agent code, eval golden sets, red-team corpus** | These are your IP, not their data |
| **Aggregated metrics / eval scores crossing back to you** | Only by explicit written agreement, and only aggregates. Nail this down in the contract *now* — it's the difference between "we monitor the deployment" and a residency breach. |

## 4. What actually changes in the code — and how to size it in an hour

If you built on Kubernetes with a provider-bindings layer, this is a values-layer port, not a rewrite:

- **Model client**: `bedrock-runtime` → Azure AI Foundry SDK. **This is only cheap if every Bedrock call already goes through one wrapper.** Go grep for `bedrock-runtime` / `InvokeModel` / `Converse` across the services right now — if it appears in more than one module, that scattered call surface *is* your migration cost, and it's also the thing that makes your egress redactor bypassable. Fix it by collapsing to a single gateway client either way.
- **Workload identity**: EKS Pod Identity/IRSA → **AKS Workload Identity** (federated managed identity). Same property, different annotation: the Helm values that name a role ARN name a client ID instead. No static keys, on either cloud.
- **Object storage / secrets clients**: S3 → Blob, Secrets Manager → Key Vault.
- **Model family**: check whether the exact model you evaluated is available in Foundry **in their required region**. If not, a model swap rides the full eval + red-team gate like any other model change — budget for that, don't discover it.
- **Unchanged**: agent loop, prompts, schema validation, capability manifests, redaction gateway, business logic.

Two things you inherit from Bedrock that you must re-establish on Azure, not assume:
- **The data-use commitment.** AWS's is published (prompts not used for training, providers in isolated accounts). Get the Azure/Foundry equivalent in writing for the specific models and features you use — and note that BAA/DPA coverage varies by *endpoint and feature*; preview features and telemetry are commonly out of scope even when the base endpoint is in.
- **Single-region processing.** Bedrock's Global cross-region inference has an Azure analog in Global vs. Data Zone vs. Regional deployments. For a residency-constrained client: **Regional deployment only.** Never Global.

## 5. Challenge the premise before you spend a quarter on this

Ask the client: **"tenant" or "cloud"?** Those are different clauses.

- If the clause is *"our data stays in infrastructure we own and control"* — an **AWS account inside their organization**, with your platform deployed into it, satisfies it. Bedrock stays, the port collapses to a deploy-target change, and you keep every control you already built. Many "no data leaves our tenant" clauses are actually this, written by someone who assumed Azure because that's what the rest of the company runs on.
- If the clause is genuinely *"Azure, our subscription, our EA"* — then §2 is the real scope and the model layer swap is unavoidable.

The cost difference between those two readings is enormous. Get the answer in writing before you architect. Also settle now, not at handover: which region, who operates the platform after go-live, and what read access their platform team gets (dashboards yes; raw prompt payloads under their own policy, with logged access).

## 6. Off by default on Azure — the enablement checklist a reviewer actually wants

The AWS half of this you already know. These are the Azure equivalents, and the compliance posture is only as real as this list:

| Control | Default | Action |
|---|---|---|
| **Foundry diagnostic settings** (model request/response logging) | **off** | enable → immutable Storage account in-tenant |
| **Foundry public network access** | **enabled** | disable; private endpoint only |
| **AKS control-plane diagnostic logs** (kube-apiserver, audit, controller-manager, scheduler) | **off** | enable all → Log Analytics in-tenant |
| **Storage immutability policy (WORM), locked** | **off** | enable — this is the Object Lock COMPLIANCE-mode equivalent, and it's what converts "we keep logs" into "our logs are evidence" |
| **CMK on Storage / PostgreSQL / AKS secrets (KMS etcd encryption)** | platform-managed keys | switch to CMK in their Key Vault |
| **AKS NetworkPolicy** (Cilium or Azure NPM) | **no policy = allow-all** | default-deny ingress+egress per namespace, then named flows |
| **Egress** | NAT-to-anywhere | default-deny; private endpoints for Foundry, Storage, PostgreSQL, Key Vault, ACR — target *zero* internet egress from workload subnets |
| **DNS** | resolves anything | private resolver only, external resolvers blocked in NetworkPolicy, query logging on. **DNS is an exfil channel** — an agent that can resolve arbitrary names can tunnel data out. |
| **Azure AI Content Safety** attached at the endpoint | not automatic | attach; Prompt Shields + PII in *redact* mode (not block — false positives teach the team to route around the control) |
| **Defender for Cloud** | partial | on, findings routed |

Retention: propose long (multi-year) for audit **metadata**, and a short, explicitly-agreed window for **payload** stores. Write both into the client agreement. Retention chosen by nobody is the finding.

## 7. Alarms that must survive the move

- Model invocation by **any identity other than the two agent workload identities** — the "someone found a credential" alarm.
- Invocation of a **model deployment outside the allowlist** — should be impossible (RBAC + policy + private endpoint); firing means a policy layer changed.
- Break-glass role assumption; changes to immutable-storage policies; NetworkPolicy or private-endpoint policy modification; `kubectl exec` into agent pods in prod.

## 8. What to show their security team

One boundary diagram (§1) with the named flows overlaid, plus two live proofs that land better than any document:

1. `kubectl` into an agent pod → `curl https://example.com` blocked, external DNS resolution blocked. Thirty seconds.
2. The private-endpoint policies, Azure Policy assignments, and NetworkPolicies **as code in the IaC repo** — allowlists as versioned artifacts with a review history, not console settings. Back them with policy-as-code assertions on the plan (Checkov/OPA): diagnostic logging can't be disabled, immutability can't be removed, endpoints can't be widened — so "someone turned off audit logging" is a failed plan, not a discovered incident.

---

**The application-layer half:** the redaction gateway, capability manifests, data-class enforcement at the API, and schema validation are code, not infrastructure — the network only guarantees they can't be *bypassed*. Those belong in `ai-engineering-implementation`.
