# Infrastructure implementation — compliance requirements as platform

Translation of the framework requirements into **infrastructure and architecture**: tenancy and
residency, identity, network, audit, supply chain, and managed guardrail services. Code-level
controls live in the `ai-engineering-implementation` skill.

**Cloud stance:** the platform is cloud-agnostic on a Kubernetes core by design — that is itself a
compliance decision (it is what makes deployment into a client-owned tenant on any cloud possible).
Guidance here is written pattern-first, with AWS as the worked example because that is where the
best-documented GenAI security guidance exists. Each AWS control names its Azure equivalent where
the mapping matters for a client-tenant deployment.

**Primary AWS sources** (all verified July 2026):

- **Generative AI Security Scoping Matrix** — <https://aws.amazon.com/ai/security/generative-ai-scoping-matrix/> (and the newer Agentic AI Scoping Matrix)
- **Prescriptive Guidance: Agentic AI Security** — includes a full OWASP LLM Top 10 → AWS controls mapping: <https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-security/owasp-top-ten.html>
- **Security Reference Architecture for Generative AI** — <https://docs.aws.amazon.com/prescriptive-guidance/latest/security-reference-architecture-generative-ai/introduction.html>
- **Well-Architected Generative AI Lens** (Nov 2025) — <https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html>
- **HIPAA-ready GenAI architecture for healthcare** — <https://aws.amazon.com/blogs/industries/building-a-hipaa-ready-generative-ai-architecture-for-healthcare-on-aws/>

Where we sit in AWS's own taxonomy: **Scope 3** of the Scoping Matrix (application built on
pre-trained foundation models via Bedrock). That scoping determines the discipline depth AWS
prescribes — we own governance, legal/privacy, risk, controls, and resilience for the *application
and data*, while model training risk stays with the provider. Cite the scope in client
conversations; it is a shared vocabulary their security team may already use.

## Files

| File | Covers | Satisfies |
|---|---|---|
| [01-architecture.md](01-architecture.md) | Tenancy, residency boundary, environment tiers, client-tenant deployment | Data residency · ISO A.6 · Scoping Matrix |
| [02-identity-access.md](02-identity-access.md) | Workload identity, per-service roles, model access policy | HIPAA min-necessary · LLM06 · GOVERN 6 |
| [03-network-egress.md](03-network-egress.md) | Private endpoints, default-deny egress, NetworkPolicies | Data residency · LLM02 · ATLAS exfil-via-tool-call |
| [04-audit-logging.md](04-audit-logging.md) | CloudTrail, model invocation logging, immutable audit, trace store hosting | ISO A.6.2.8 · MANAGE 4.3 · HITRUST |
| [05-supply-chain.md](05-supply-chain.md) | Image signing, admission control, IaC pipeline, model pinning at org level | LLM03 · SP 800-218A |
| [06-guardrails-services.md](06-guardrails-services.md) | Bedrock Guardrails and managed-control equivalents | LLM01/02/09 defense-in-depth · AI 600-1 |

## The design stance

1. **The boundary is enforced twice.** Every data-residency and least-privilege guarantee exists
   once in code (the `ai-engineering-implementation` skill) and once in infrastructure (IAM, network policy,
   endpoint policy). Either layer failing alone is a detected near-miss, not a breach.
2. **Deny by default, allow by name.** Egress, IAM actions, model IDs, registries, namespaces —
   allowlists everywhere. A new capability is a reviewed diff, not a discovered behavior.
3. **Audit is infrastructure, not application courtesy.** CloudTrail, model invocation logs, and
   K8s audit logs exist even when application code is compromised or wrong — that independence is
   what makes them evidence.
