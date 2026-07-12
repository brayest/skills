# What else the security review needs to see

Your three controls are the right three, but as described, **two of them are opt-out and one is probably wide open.** That's what a good reviewer will find. Fix those first, then hand them the enablement checklist.

## The three gaps in what you already have

**1. The guardrail is a parameter, so a code path can omit it.**
A guardrail ID passed on every `InvokeModel` call is a guardrail that a bug, a new code path, a debugging shortcut, or a compromised container simply doesn't pass — and the call still succeeds. That is a default-allow control. Make it default-deny at IAM so an un-guardrailed call is denied *by AWS*, not merely unprotected:

```json
{
  "Effect": "Allow",
  "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:Converse"],
  "Resource": "arn:aws:bedrock:us-east-1::foundation-model/<approved-model-id>",
  "Condition": {
    "StringEquals": { "bedrock:GuardrailIdentifier": "<guardrail-arn>:<version>" }
  }
}
```

Pin the **version** in the condition too, so a guardrail config change is a reviewed rollout, not a silent behavior shift. (Verify the condition-key name against the current Bedrock service authorization reference before shipping — these move between releases.) Bonus: guardrails can also be attached via an AWS Organizations policy, which turns "every model call passes a guardrail" into an org invariant rather than per-app diligence.

**2. NetworkPolicy has a bypass, and default-deny doesn't close it.**
A pod with `hostNetwork: true` shares the node's network namespace and **NetworkPolicy does not apply to it** — every egress rule is void. Same class of escape via `hostPID`, privileged containers, and hostPath mounts of the node's network config. A posture a workload can opt out of by setting one field in its own pod spec is a convention, not a control.

Close it at admission:
- **Pod Security Admission** in `restricted` mode on the agent namespaces (forbids `hostNetwork`, `hostPID`, `hostIPC`, privileged, host ports).
- **Kyverno/OPA** as the belt to PSA's braces, so the rule is code in the same repo and shows up in the same reviewed diff.

When the reviewer asks "what stops the agent reaching the internet," the honest answer is the NetworkPolicy **plus** the admission policy that stops a pod from escaping it. Showing the first without the second is exactly the gap a good reviewer finds.

**3. Your VPC endpoint policies are probably the default — which allows everything.**
PrivateLink gets the traffic off the internet; it does not constrain *what* you can do over it. Two policies to write:

- **Bedrock interface endpoint policy**: scope to your agent role ARNs and the specific `foundation-model/...` + inference-profile ARNs. This is the third net under the IAM model-ARN allowlist — a leaked credential used from inside the VPC still can't reach an unapproved model, and no credential works from outside the VPC at all.
- **S3 gateway endpoint policy with an `aws:ResourceAccount` / `aws:ResourceOrgID` condition.** This is the one people miss. Tight IAM on *your* buckets does nothing to stop `PutObject` to an *attacker-owned* bucket — S3 is a first-class exfiltration channel and PrivateLink alone doesn't close it.

## What's missing entirely

**Model allowlisting, three layers deep.** `bedrock:InvokeModel` scoped to named model ARNs in the role; an **SCP** allowlisting model ARNs + regions org-wide (so a misconfigured account can't un-govern it); the endpoint policy repeating the list. Also SCP-deny **Bedrock API keys** (`bedrock:BearerTokenType`) — bearer tokens recreate exactly the static-credential problem you avoided with Pod Identity/IRSA.

**DNS is an exfiltration channel.** An agent that can resolve arbitrary names can tunnel data out in queries alone, without ever opening a TCP connection your NetworkPolicy would see. Cluster resolver only, external resolvers blocked in NetworkPolicy, Route 53 Resolver query logs on.

**The audit surfaces that are off by default.** This checklist is, honestly, the single most useful artifact you can hand the reviewer — a posture built on the assumption these are running is fiction:

| Surface | Captures | Default |
|---|---|---|
| Bedrock **model invocation logging** | full request/response payloads | **off** |
| CloudTrail **data events** (Bedrock agent-runtime, S3) | what the agent runtime actually did | **off** |
| **EKS control-plane logs** (all five: api, audit, authenticator, controllerManager, scheduler) | cluster admin actions, `kubectl exec` | **off** |
| **Route 53 Resolver query logs** | DNS egress attempts | **off** |
| pgAudit on RDS | who read/wrote which tables | off |

Default CloudTrail tells you an invocation *happened* — not what the agent did. Ship all of it to an in-tenant S3 bucket with **Object Lock in COMPLIANCE mode** + CloudTrail log-file integrity validation; that's what converts "we keep logs" into "our logs are evidence."

**The alarm set** (an audit log nobody reads is decoration):
- Bedrock invocation by any principal other than the agent roles → "someone found a credential."
- Invocation of a model ID outside the allowlist → should be *impossible*; firing means a policy layer changed.
- Any modification to NetworkPolicies, endpoint policies, SCPs, or Object-Locked bucket policies → security event, not a hygiene ticket.
- `kubectl exec` into an agent pod in prod (EKS audit filter); break-glass role assumption.

**Supply chain — because your egress story depends on the image.** The claim "only the gateway wrapper calls Bedrock" is only true if the running image is the one that went through review. Cosign-sign in CI, verify signatures at admission (Kyverno), blessed registry only, no `latest`. And **no dynamic tool/model acquisition at runtime** — an agent that can be talked into fetching a new tool is ATLAS's supply-chain-compromise technique realized. Add Checkov/OPA on the Terraform plan asserting the invariants above (endpoint policies not widened, invocation logging not disabled, Object Lock not removed) plus drift detection on the boundary resources.

## Three things that quietly break the story

- **Cross-region inference profiles.** Bedrock inference profiles can route processing to another region, and newer profiles often default to it. Worse: CloudTrail and invocation logs record in the *source* region regardless — so the logs look consistent with a single-region story even when it isn't true. **The profile configuration is the evidence; the logs are not.** Check yours.
- **Telemetry is an egress channel.** If traces, prompts, or logs ship to a SaaS observability vendor or a vendor-owned aggregation account, client data crosses the boundary through the telemetry channel. This is the classic silent violation — and it survives every network control you just built, because you allowlisted it.
- **The framework's own persistence is an undeclared data store.** Agent checkpointers and message-history tables retain full document content indefinitely with no default TTL. It never appears on the data-flow diagram because the framework writes it, not your code. Give it a TTL and a purge job before someone else finds it.

## The threat model to state out loud

In an agentic system, **every reachable network destination is an exfiltration channel available to a hijacked agent, and a tool call is an egress channel.** MITRE ATLAS names exfiltration-through-tool-calls explicitly. The network's job is to make the set of reachable destinations equal to the set of named, reviewed dependencies — so prompt injection can at worst misuse an approved channel (which application controls then constrain) rather than open a new one. Every new integration enters as a new named egress in a reviewed diff.

Useful shared vocabulary: this is **Scope 3** in AWS's GenAI Security Scoping Matrix (app built on a hosted foundation model), which sets the expected depth of controls.

## What to actually put in front of them

1. **One diagram**: the boundary, with the named egress flows overlaid (agent → Bedrock endpoint, RDS, S3 endpoint, collector; and nothing else).
2. **Two live proofs**, thirty seconds: shell into an agent pod, `curl https://example.com` → blocked; resolve an external name → blocked. This lands the argument better than any document.
3. **The enablement checklist above**, showing on/off state per surface.
4. **The policies as code** — endpoint policies, SCP, NetworkPolicies, guardrail config, Kyverno rules — in the infra repo with a review history. Allowlists that are versioned artifacts, not console settings.

One warning on framing: **cite evidence that actually proves the claim.** IAM Access Analyzer does not prove an agent can't write to an external bucket; an S3 endpoint policy with `aws:ResourceAccount` does. A reviewer who catches a control cited for something it doesn't do will discount everything else you showed them.

## The application half

Two of these need code, not infra — see `ai-engineering-implementation`: the egress redactor at the model boundary (the Bedrock Guardrails sensitive-information filter is its managed *twin*, in redact mode, not its replacement), and the capability manifest that constrains which tools the agent may call at all. IAM does coarse (service × prefix × action); code does fine (session × record). Say which layer backstops which — that division is the design.
