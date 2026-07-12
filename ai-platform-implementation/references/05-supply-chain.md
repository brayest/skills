# Supply chain — from git commit to running pod, verified

**Requirement being implemented:** OWASP LLM03 (Supply Chain), SP 800-218A Protect-Software /
Produce-Well-Secured-Software at the platform layer, ISO 42001 A.4.4 (tooling resources) and A.10.3
(suppliers).

The pipeline gates live in `06-cicd` in the `ai-engineering-implementation` skill; this file is the
infrastructure that makes those gates *binding* — so that what runs in the cluster is provably what
went through the pipeline, and the model dependency is governed at the org level where no single
misconfigured account can un-govern it.

---

## 1. Image provenance — sign in CI, verify at admission

- **Build**: pinned base images (by digest), SBOM generated (syft) and stored with the release
  record, vulnerability scan gating the push (fail on critical), **cosign signing** of every image.
  (The Lambda `--provenance=false --sbom=false` rule is for Lambda's manifest quirks; for K8s
  images, keep attestations on — they are the evidence.)
- **Registry**: one blessed registry (ECR; the tenant's own registry in client-tenant deployments), immutable tags,
  ECR scan-on-push as the second scanner. Cross-account pull via the provider-alias pattern the
  monorepo already uses.
- **Admission**: a policy controller (Kyverno) in pilot/prod enforcing — images only from the
  blessed registry, **signature verification against our CI key**, no `latest` tags, and the
  boring-but-critical pod hygiene set (no privileged, no hostPath except the QA staging volume
  pattern, runAsNonRoot, read-only root FS where the services allow).

The property this buys: a change that skipped the eval and red-team gates *cannot run in prod*,
because it was never signed by the pipeline that runs those gates. The gates stop being process and
become physics.

## 2. IaC through the same discipline

Terraform/Terragrunt and Helm are software with root on everything:

- Plans reviewed as PRs; applies from CI only (OIDC deploy role — no human `terraform apply`
  against prod with local credentials).
- **Policy-as-code on the plan**: Checkov/OPA rules asserting the compliance invariants — no
  public buckets, no security groups open to `0.0.0.0/0`, CMK encryption present, Object Lock not
  removed, VPC endpoint policies not widened, invocation logging not disabled. The §1 checklist of
  [04-audit-logging.md](04-audit-logging.md) becomes assertions, so "someone turned off audit
  logging" is a failed plan, not a discovered incident.
- Drift detection scheduled; drift on the boundary resources (endpoint policies, SCPs, bucket
  policies, NetworkPolicies) alerts as a security event, not a hygiene ticket.

## 3. The model as a supplier — governed at the org level

ISO A.10.3 treats suppliers as a controlled relationship; for us the material supplier is the
model, and its governance is layered so no single account misconfiguration breaks it:

| Layer | Mechanism | Owner |
|---|---|---|
| Org | **SCP allowlisting model ARNs + regions** for `bedrock:InvokeModel*`; deny Bedrock API-key auth (`bedrock:BearerTokenType`) | org admin |
| Account | Bedrock model-access grants (only approved models enabled at all) | platform |
| Role | per-service model-ARN allowlists ([02-identity-access.md](02-identity-access.md)) | platform |
| Endpoint | PrivateLink endpoint policy repeating the allowlist | platform |
| Pipeline | model-pin changes ride full eval+red-team (`06-cicd` in the `ai-engineering-implementation` skill) | CI |

<https://builder.aws.com/content/32syXvFuxEUyB40ex4B9ZDDzR4p/service-control-policy-to-govern-amazon-bedrock-models>
(SCP region caveat for marketplace models noted there and in [02-identity-access.md](02-identity-access.md).)

**AWS Config conformance pack for Bedrock** as continuous verification that the account-level
posture (invocation logging on, guardrail attachment, etc.) stays put:
<https://docs.aws.amazon.com/config/latest/developerguide/amazon-bedrock-security-and-governance-best-practices.html>

The supplier-assessment artifact (#14) for Bedrock/Anthropic writes itself from published facts:
AWS's data-use commitment (no training on our prompts, provider-isolated accounts), BAA coverage
via Artifact, HIPAA eligibility (re-verify at decision time), model deprecation policy → our
contingency ([01-architecture.md](01-architecture.md) §5). One page, citations, reviewed annually
and on any model-family change — that satisfies GOVERN 6.1 without a procurement theater exercise.

## 4. Dependencies below the images

- Python/npm lockfiles committed; Dependabot/Renovate PRs ride the normal gates (a langchain-aws
  bump gets smoke evals — it's on the request path).
- **No dynamic model/tool acquisition at runtime.** The agents load tools from the code in the
  image, models from pinned IDs in config. An agent that can be talked into fetching a new tool is
  ATLAS's supply-chain-compromise technique realized; ours structurally cannot, and that sentence
  belongs in the system card.
- Helm chart dependencies pinned by version+digest; third-party charts (Langfuse, collectors)
  vendored or proxied through the blessed registry, not pulled from the internet at deploy time —
  the cluster itself follows the no-internet-egress rule ([03-network-egress.md](03-network-egress.md)).
