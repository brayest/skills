# Audit and logging — evidence that survives a compromised application

**Requirement being implemented:** ISO 42001 A.6.2.8 (event logs), NIST MANAGE 4.3, HITRUST audit
domains, HIPAA audit controls (§164.312(b)), SP 800-218A respond-to-vulnerabilities.

Division of labor with the application traces
(`04-observability` in the `ai-engineering-implementation` skill): application traces explain
*what the agent decided*; infrastructure audit proves *what actually happened at the platform* —
independently of application code being correct or honest. An auditor wants both; an incident
responder needs the second when the first is the thing in question.

---

## 1. The audit surfaces and their switches

Several of these are **off by default** — the compliance posture is only as real as the enablement
checklist:

| Surface | Captures | Default | Action |
|---|---|---|---|
| **CloudTrail management events** | that Bedrock `InvokeModel`/`Converse` calls happened (caller, time, model, region) — *not* payloads | on | keep; org trail |
| **CloudTrail data events** | agent-runtime and async-invoke operations | **off** | enable for Bedrock (and S3 data events on the artifacts bucket) |
| **Bedrock model invocation logging** | full request/response payloads (≤100KB inline, larger → S3) | **off** | enable per account/region → in-tenant bucket only |
| **EKS control-plane logs** | `api, audit, authenticator, controllerManager, scheduler` | **off** | enable all five → CloudWatch |
| **Route 53 Resolver query logs** | DNS egress attempts | off | enable in pilot/prod |
| **RDS/Postgres audit (pgAudit)** | who read/wrote which tables | off | enable for prod, DDL + role changes minimum |

Sources: <https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html>,
<https://docs.aws.amazon.com/bedrock/latest/userguide/logging-using-cloudtrail.html>,
<https://docs.aws.amazon.com/eks/latest/best-practices/auditing-and-logging.html>

**Invocation logging vs. our traces — decide the overlap deliberately.** Bedrock invocation logs
duplicate what our trace payload store holds, with less structure. Two defensible positions:
(a) enable both — invocation logs are the application-independent record (they exist even if our
tracing code lies or dies), retention short; traces are the working record, retention longer; or
(b) traces only, accepting application-dependence of payload evidence. **Take (a) for pilot/prod**;
the storage cost is trivial at our volume and "the platform logs every model call independently of
its own code" is a sentence that does real work in a security review. Both stores live in-tenant
([01-architecture.md](01-architecture.md) §1) and inherit the payload-tier access rules.

## 2. Immutability and retention

The pattern from AWS's HIPAA-ready GenAI reference (layer 7): audit logs → S3 with **Object Lock in
COMPLIANCE mode** + CloudTrail log-file integrity validation.
<https://aws.amazon.com/blogs/industries/building-a-hipaa-ready-generative-ai-architecture-for-healthcare-on-aws/>

- Object Lock COMPLIANCE mode = nobody, including root, shortens retention. That single property
  converts "we keep logs" into "our logs are evidence." The reference architecture uses 6-year
  retention (HIPAA's documentation horizon); **the actual number for us is a client-agreement
  decision** — propose 6 years for audit logs (metadata, no payloads) and a much shorter,
  explicitly-agreed window for payload stores, then write both into the client agreement and the AI
  policy's retention line. Retention chosen by nobody is the finding.
- Integrity validation on (CloudTrail digest files), lifecycle rules as code, and the
  **payload/metadata split governs retention too**: metadata is cheap and safe to keep for years;
  payloads (client content) should age out as fast as the client wants.

## 3. Alerting — the audit log that nobody reads is decoration

Minimum alarm set wired to the incident process
(`04-observability` in the `ai-engineering-implementation` skill §5):

- Bedrock invocation by **any principal other than the two agent roles** (CloudTrail metric filter)
  — this is the "someone found a credential" alarm.
- Invocation of a **model ID outside the allowlist** — should be impossible (IAM+SCP+endpoint
  policy); firing means a policy layer changed. That's a capability-violation incident by
  definition.
- Break-glass role assumption; any change to Object-Locked buckets' policies; NetworkPolicy or
  endpoint-policy modification; `kubectl exec` into agent pods in prod (EKS audit log filter).
- GuardDuty + Security Hub on, findings routed — the reference architecture treats these as
  baseline, and they cost nothing to leave on.

## 4. What the auditor gets

From this layer alone, without touching application code: who called which model when (CloudTrail),
what was sent and returned (invocation logs, governed access), who touched the data stores (S3 data
events, pgAudit), who administered the cluster (EKS audit), that none of it can have been quietly
edited (Object Lock + digest validation), and that deviations page someone (alarm history). Mapped
to HITRUST audit-logging controls, this is most of that domain's evidence — generated by
configuration, not by effort.

**Azure equivalents**, so the posture survives a cloud move: Azure Activity Log + diagnostic
settings → immutable Storage (immutability policies), AI Foundry diagnostic logging for model
calls, AKS control-plane diagnostic logs, Defender for Cloud in place of GuardDuty/Security Hub.
The enablement checklist in §1 is the artifact to port, not the service names.
