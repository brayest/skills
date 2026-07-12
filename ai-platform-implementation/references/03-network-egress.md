# Network and egress — the residency clause as routing table

**Requirement being implemented:** the data-residency clause, OWASP LLM02, MITRE ATLAS
exfiltration-through-tool-calls, HIPAA transmission security.

The threat model to hold while reading: **in an agentic system, every reachable network destination
is an exfiltration channel available to a hijacked agent.** The network's job is to make the set of
reachable destinations equal to the set of *named, reviewed* dependencies — so that prompt injection
can at worst misuse an approved channel (which code-level controls then constrain), never open a
new one.

---

## 1. Default-deny egress, allow by name

- **Cluster egress**: no NAT-to-anywhere. Pilot/prod clusters run private subnets with egress
  restricted to named endpoints. The full list of what the platform legitimately needs to reach is
  short enough to write down — Bedrock, S3, RDS, KMS, ECR, CloudWatch, STS — **and every one of
  those has a VPC endpoint**, so the honest target is *zero* internet egress from workload subnets.
- **Bedrock via PrivateLink**: interface endpoint with private DNS, so `bedrock-runtime.*` resolves
  in-VPC with no code changes; endpoint policy scoped to our roles and model ARNs (default policy
  allows everything — scope it):
  <https://docs.aws.amazon.com/bedrock/latest/userguide/vpc-interface-endpoints.html>
- **S3 via gateway endpoint** with a bucket-scoped endpoint policy (`aws:ResourceAccount` condition)
  — blocks the "exfiltrate to attacker-owned bucket" path, which plain S3 egress allows even with
  tight IAM on our own buckets.
- **DNS is egress too**: an agent that can resolve arbitrary names can tunnel data out through
  queries. Private resolver only; block external resolvers in NetworkPolicy; log queries
  (Route 53 Resolver query logs) in pilot/prod.

## 2. In-cluster NetworkPolicies — east-west by name

VPC CNI enforces Kubernetes NetworkPolicy natively (
<https://docs.aws.amazon.com/eks/latest/best-practices/network-security.html>). Baseline per
namespace: default-deny ingress+egress, then the named flows:

```
ui            → gateway:8000
gateway       → product-api:8000, qa-api:8001, RDS, S3-endpoint
product-api   → Bedrock-endpoint, RDS, S3-endpoint, otel-collector
qa-api        → Bedrock-endpoint, RDS, S3-endpoint, otel-collector
otel/traces   → trace-store (observability ns);  trace-store → RDS(own), S3(own)
everything    → kube-dns:53 (cluster resolver only)
```

Notably absent, on purpose: agent→agent (they coordinate through state, not calls),
agent→internet, ui→anything-but-gateway, and **anything→trace-store except the collector** — the
trace store holds client payloads and its network position should say so.

The `qa-api` proxy path (`gateway → qa-api`) is the only cross-namespace agent flow in this
architecture. When a new integration lands (an issue tracker, a design tool — in-tenant),
it enters as a new named egress in a reviewed diff, and its endpoint gets the same treatment: named
FQDN/endpoint, policy row, capability-manifest entry, risk-register line. Four artifacts, one PR.

### NetworkPolicy has a bypass, and you must close it

**A pod with `hostNetwork: true` shares the node's network namespace and NetworkPolicy does not apply
to it.** Every egress rule above is void for that pod. The same class of escape comes from
`hostPID`, `hostIPC`, privileged containers, and hostPath mounts of the node's network config.

This matters more than it sounds: a NetworkPolicy posture that a workload can opt out of by setting
one field in its own pod spec is not a control, it is a convention. Close it at admission:

- **Pod Security Admission** in `restricted` mode on the workload namespaces — it forbids
  `hostNetwork`, `hostPID`, `hostIPC`, privileged, and host ports outright.
- **Kyverno/OPA policy** as the belt to PSA's braces, so the rule is expressed as code in the same
  repo as everything else and shows up in the same reviewed diff.

When a reviewer asks "what stops the agent reaching the internet," the honest answer is the
NetworkPolicy *plus* the admission policy that prevents a pod from escaping it. Presenting the first
without the second is the kind of gap a good reviewer finds and a bad one doesn't — and you would
rather it be found.

## 3. Where the redaction gate sits

The egress redactor (`03-data-boundary` in the `ai-engineering-implementation` skill §2) is
application code, but the network guarantees it can't be bypassed: the *only* route to the model is
the PrivateLink endpoint, and the endpoint policy only admits the agent roles, whose pods only run
images in which the gateway wrapper is the only Bedrock client (lint-enforced, admission-verified —
[05-supply-chain.md](05-supply-chain.md)). Bypass requires defeating code review, image signing,
and network policy at once — that stacked cost is the design.

## 4. Ingress, briefly

Standard and boring, listed for completeness: single ingress (ALB/App Gateway) → `ui`/`gateway`
only; WAF in front (AWS's HIPAA-ready GenAI reference puts WAF + Shield at layer 1 —
<https://aws.amazon.com/blogs/industries/building-a-hipaa-ready-generative-ai-architecture-for-healthcare-on-aws/>);
TLS terminated with tenant-owned certs; auth at the gateway (client SSO in client-tenant
deployments), *before* any request reaches an agent. Rate limits at ingress complement the fan-out caps in
code (LLM10 has both an app and a network face).

## 5. What a reviewer should be shown

One diagram (the §1 boundary drawing from [01-architecture.md](01-architecture.md) with the named
flows from §2 overlaid) plus two live proofs:

- `kubectl` demo: a shell in an agent pod attempting `curl https://example.com` → blocked;
  resolving an external name → blocked. Thirty seconds, and it lands the residency argument better
  than any document.
- The VPC endpoint policies and SCP, as code, in the infrastructure repo — showing the allowlists
  are versioned artifacts with a review history, not console settings.
