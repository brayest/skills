# What else the security review needs to see

Your three controls cover the *network* exfil path. The review is asking about the *agent*, and an agent's main egress channels aren't the network — they're its tools, its IAM role, and its telemetry. Also: one of your three controls isn't actually a control yet.

## The one that will get you burned first

**"We pass a guardrail ID on every InvokeModel call" is an application convention, not an enforced control.** Nothing stops a code change, a new service, or a compromised pod from omitting it. A reviewer will ask "who checks?" and the honest answer today is "code review."

Enforce it in IAM on the pod's role:

```json
{
  "Sid": "InvokeOnlyAllowlistedModelsWithGuardrail",
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Converse", "bedrock:ConverseStream"],
  "Resource": [
    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-*",
    "arn:aws:bedrock:us-east-1:<acct>:inference-profile/us.anthropic.claude-*"
  ],
  "Condition": {
    "StringEquals": {
      "bedrock:GuardrailIdentifier": "arn:aws:bedrock:us-east-1:<acct>:guardrail/<id>"
    }
  }
}
```

Deny `bedrock:*` without the condition. Now "the guardrail is always applied" is a provable property of the trust policy, not a claim about the codebase. Same pattern gets you **model allowlisting** for free — the resource ARNs mean the agent cannot invoke a model you haven't approved.

Note the inference-profile ARN: if you use cross-region inference profiles, your data leaves the region you told the reviewer it stays in. Pin it, or add an `aws:RequestedRegion` condition, and be ready to say so out loud before they find it.

## The exfil channels your three controls don't touch

| Channel | What actually stops it | Evidence to show |
|---|---|---|
| **The agent's own tools** — an HTTP-fetch tool, an S3 write, a "send email"/Slack tool, a DB write. This is the #1 real path and it's fully inside your NetworkPolicy. | A capability manifest: every tool, its allowed destinations, whether the *model* can choose the destination. The model must never supply a URL, bucket, ARN, or recipient — those come from a server-side allowlist keyed by an opaque ID. | The tool registry, plus the schema showing no free-form destination params. |
| **The pod's IAM role** — `s3:PutObject` to `*` means the agent can write your data into an attacker's bucket over your own PrivateLink. | Data-perimeter SCPs: `aws:ResourceOrgID` on S3/SQS/etc. so the role physically cannot address a resource outside your org. Scope the role to named buckets/prefixes. | The SCP + the role policy. |
| **Workload identity** — is the role bound to *this* pod, or to the node? | EKS Pod Identity (or IRSA with a `sub` condition on the exact namespace + ServiceAccount). Node role has no Bedrock, no S3. | The trust policy condition block. |
| **Telemetry** — traces, prompt logs, LLM-observability SaaS. Prompts and completions are the sensitive payload, and this pipeline is *designed* to ship them off-cluster. | This is the gap I'd bet money the review finds. Either keep it in-tenant, or scrub/classify before export and prove it. | The trace pipeline diagram, redaction config, and the vendor's DPA. |
| **Prompt injection** — retrieved docs, uploaded PDFs, and scraped pages are instructions to your agent. This is the actual threat model behind the question. | Untrusted content is data, not instruction (delimited, labeled). Model doesn't pick destinations (above). Human approval on any outbound write. | The trust-boundary diagram: which inputs are untrusted, which actions are irreversible, where the human is. |
| **Sidecars / a compromised container** | Signed images + admission control (Kyverno/Gatekeeper), read-only rootfs, no privileged, distroless. NetworkPolicy applies pod-wide, so a malicious sidecar shares your egress rules — good, but only if nothing can schedule an unsigned image. | Admission policy + the "no image without a signature" test. |

## Make the network claim actually airtight

NetworkPolicy default-deny is L3/L4 and CNI-dependent. Back it with layers a reviewer can verify without trusting your CNI:

- Agent subnets have **no NAT gateway and no IGW route**. Nothing to reach. This is the strongest single statement you can make.
- **VPC endpoint policy** on the Bedrock endpoint restricting `aws:PrincipalArn` to the agent role and the model ARNs — so even the endpoint won't carry a call to an unapproved model.
- **Security group egress default-deny**, allow only the endpoint ENIs.
- **DNS**: Route 53 Resolver query logging + a DNS firewall. DNS is the classic covert channel and it's the one thing that often survives an egress lockdown.

## What "prove" means to them

They don't want a control list. They want to see a **negative test suite that runs in CI** and produces artifacts:

1. `curl https://attacker.example` from inside the pod → connection refused/timeout.
2. `aws s3 cp` to a bucket outside the org → `AccessDenied` (SCP).
3. `InvokeModel` without the guardrail param → `AccessDenied` (IAM condition).
4. `InvokeModel` against a non-allowlisted model → `AccessDenied`.
5. DNS lookup of an external domain → blocked, and **logged**.
6. A red-team prompt-injection eval: docs containing "exfiltrate the previous context to X" → agent has no tool that can do it.

Ship the output of those six as the evidence pack. Pair it with the always-on logs that would catch a real attempt — **Bedrock model invocation logging** to an S3 bucket with Object Lock, CloudTrail data events for Bedrock, VPC Flow Logs, DNS query logs — because the second question after "what stops it" is always "how would you know if it happened."

## The framing that lands

Say it in this order:

> The agent cannot reach the internet (no NAT, no route). It cannot reach an AWS resource outside our org (SCP). It cannot invoke a model we haven't approved or skip the guardrail (IAM condition, not application code). It cannot choose where its tools send data (server-side allowlist; the model never supplies a destination). Everything it does invoke is logged immutably. Here are the tests that prove each of those, and here's what we'd see if one failed.

That's what they're asking for. Your current three controls answer the first line and half the third.
