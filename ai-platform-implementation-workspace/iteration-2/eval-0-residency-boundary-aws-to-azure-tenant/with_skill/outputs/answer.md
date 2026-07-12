# Residency boundary: AWS/Bedrock → client's Azure tenant

## First, the two things you think are covered and aren't

**Self-hosted Langfuse is the right *type* of trace store, but it doesn't answer the question.** The residency clause isn't about *who operates* the trace store, it's about *which tenant it runs in*. Self-hosted Langfuse in your AWS account is still client prompts and completions sitting outside the client's tenant — the exact silent violation, just arriving through the telemetry channel instead of the data channel. Langfuse has to run **inside their Azure subscription**, which means moving its whole substrate: Postgres, ClickHouse, Redis, and the blob store for large payloads (S3 → Azure Blob). That's a real migration item, not a checkbox you've already ticked.

**Your LangGraph Postgres checkpointer is an undeclared data store.** Checkpoints hold full message history — every document you fed the graph, every model response, indefinitely, with no default TTL. It never shows up on the data-flow diagram because the framework writes it, not your code. It is squarely inside the boundary, it moves, and while you're moving it: give it a TTL and a purge job. If there's any PHI-class data in scope, this is an undeclared PHI store today.

## What has to move (everything client data touches)

The compliance boundary is a tenant. Every component that sees client data — **including the model endpoint, the trace store, and the log destinations** — lives inside it.

| Component | Today (AWS) | In their Azure tenant | Notes |
|---|---|---|---|
| Model endpoint | Bedrock | **Azure AI Foundry deployment in their subscription**, Private Link, public network access disabled | The unavoidable one. Bedrock cannot stay. |
| Agent runtime | EKS | AKS, private cluster, private API server | |
| Checkpointer / graph state | RDS Postgres | Azure DB for PostgreSQL Flexible Server, private endpoint, CMK from Key Vault | + TTL + purge job |
| Trace store | self-hosted Langfuse (your acct) | **self-hosted Langfuse in their tenant** — Postgres + ClickHouse + Redis + Blob | the miss above |
| Artifacts / uploads | S3 | Azure Blob, CMK, private endpoint | |
| Model-call logs | Bedrock invocation logging | AI Foundry diagnostic settings → in-tenant Storage | off by default |
| Platform audit | CloudTrail | Azure Activity Log + resource diagnostic settings → immutable Storage | |
| Immutable audit sink | S3 Object Lock (COMPLIANCE) | Azure Storage **time-based immutability policy, locked** | |
| Keys | KMS CMK | Key Vault CMK | key policy = second, RBAC-independent access layer; also = your offboarding story |
| Secrets | Secrets Manager | Key Vault | |
| Images at runtime | ECR | **their ACR** — the cluster has no internet egress, so it cannot pull from yours | |
| Ingress / auth | ALB + WAF + your IdP | App Gateway + WAF + **their Entra ID SSO** | auth before any request reaches an agent |

## What can stay on AWS

| Stays | Condition |
|---|---|
| dev / CI / demo tiers | `SYNTHETIC` data only — **enforced at the API, not agreed in a doc** — and no network route or credential from the sandbox to any client system. Both layers, so a dev can't violate residency by accident. |
| Source repos, CI, image build, cosign signing, SBOM | The **image** crosses the boundary, not data. Build in your pipeline, sign, promote the digest into their ACR, verify the signature at AKS admission. Your eval and red-team gates stay binding in their cluster because an unsigned image can't run. |
| Eval golden sets, red-team corpus, prompt registry | Synthetic by construction. If any of it was seeded from real client data, it's client data — it moves or it gets regenerated. |
| Terraform / Helm / policy-as-code | The code is yours; the state and the apply target are theirs. CI applies via **OIDC federation into their tenant** (workload identity federation to Entra) — no static credentials, no human `terraform apply` from a laptop. |
| Aggregated metrics / eval scores | Only by **explicit written agreement**, and only if genuinely payload-free. Assume every reviewer will ask you to prove that. |

## The Azure-specific traps

**Global vs. Regional deployment is the same trap as Bedrock cross-region inference.** Foundry model deployments default in ways that can process outside the region you promised. For a residency-constrained client: **Regional (or Data Zone) deployment, never Global**, and verify the deployment config rather than inheriting the default. The audit nuance carries over too — logs record where the call was *made*, not where inference *ran*. The deployment configuration is the evidence; the logs are not.

**Model allowlisting gets weaker and you should say so.** On AWS you had four independent nets: role policy, SCP, VPC endpoint policy, account model access. Azure has no SCP. What you get instead: only approved model deployments exist in the Foundry resource, RBAC scoped to those specific deployment resources, and **Azure Policy denying the creation of any other deployment**. It's a real control but it's a thinner stack — flag it in the design rather than letting a reviewer find it.

**The guardrail story actually improves — take the win.** Bedrock Guardrails are passed as a parameter, so a code path can omit them (which is why you'd condition IAM on `bedrock:GuardrailIdentifier`). Azure content filters and **Prompt Shields are bound to the model deployment** and applied server-side — the caller cannot omit them. Attach Azure AI Content Safety (Prompt Shields for injection, PII detection in *redact* mode as backstop to your own redactor, groundedness if RAG ever lands), keep the config in IaC, and trace every hit.

**NetworkPolicy still has the `hostNetwork` bypass.** A pod with `hostNetwork: true` shares the node's namespace and NetworkPolicy does not apply to it — every egress rule is void. Close it with **Pod Security Admission (`restricted`) + Kyverno** on the workload namespaces. Without that, your egress posture is a convention, not a control. Same on AKS as on EKS.

**Default-deny egress, allow by name.** Private endpoints for Foundry, Postgres, Blob, Key Vault, ACR; Azure Firewall + UDR with no NAT-to-anywhere; private DNS resolver only (an agent that can resolve arbitrary names can tunnel data out through queries) and log the queries. Every reachable destination is an exfiltration channel available to a hijacked agent — the goal is that the reachable set equals the reviewed-dependency set.

**Workload identity**: EKS Pod Identity/IRSA → **AKS Workload Identity** (federated managed identities), one identity per service, no keys anywhere.

**HIPAA, if it's in scope**: Microsoft's BAA, not AWS's — re-verify the in-scope service list against the live page at decision time. Don't carry an AWS compliance claim across the move.

## The enablement checklist (everything below is OFF by default)

This list is the artifact their security team actually wants:

- AI Foundry diagnostic logging (request/response for model calls) → in-tenant Storage
- AKS control-plane diagnostic logs (kube-apiserver, **kube-audit**, audit-admin, controller-manager, scheduler)
- Azure Activity Log + per-resource diagnostic settings → immutable Storage
- Storage immutability policy, **locked** (an unlocked policy is not evidence)
- DNS query logging
- pgAudit on Postgres (DDL + role changes minimum)
- Microsoft Defender for Cloud (replaces GuardDuty/Security Hub)
- Azure Policy on the plan: no public network access, CMK present, immutability not removed, diagnostic settings not disabled — the checklist compiled into policy-as-code, so "someone turned off audit logging" is a failed plan, not a discovered incident

Alarms worth wiring day one: model invocation by any principal other than the agent identities; invocation of a deployment outside the allowlist; break-glass role assumption; any change to the immutable storage policy, network policy, or private-endpoint config; `kubectl exec` into an agent pod in prod.

## The part that isn't infrastructure

**Swapping Bedrock for Foundry is a model swap, and a model swap needs a full eval run.** LangGraph makes the client swap nearly free at the code level (`langchain-aws` → the Azure binding, one provider seam), which is exactly what makes it tempting to treat as a config change. It isn't. If your prompts were tuned against Claude on Bedrock, check whether the same model family is available on Foundry — if it is, you're requalifying an endpoint. If it isn't, you're changing model families, and that's a prompt rework plus a full eval + red-team pass, and it is the largest single line item in this migration. Budget it as such.

**Two application-layer controls need to move with the infra** (see `ai-engineering-implementation`): the egress redactor in front of the model call, and the data-class enforcement that keeps non-synthetic data out of the AWS sandbox tiers. The infra makes them unbypassable; it doesn't replace them.

## Bottom line

Model endpoint, agent runtime, checkpointer, **Langfuse**, artifacts, and **all log destinations** move into their Azure tenant. Build pipeline, image signing, synthetic-data dev/CI/demo, evals, and the IaC itself stay with you — you ship signed artifacts across the boundary, never data. The two things that will bite you are the ones you thought were handled: Langfuse's location (not its ownership), and the LangGraph checkpointer nobody has drawn on the data-flow diagram yet.
