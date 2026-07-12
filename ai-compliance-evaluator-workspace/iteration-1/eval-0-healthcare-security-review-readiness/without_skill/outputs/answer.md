# Hospital security review: what they'll ask, and what you're probably missing

## The framing that decides everything

The first question on the call will be some version of **"does your system touch PHI?"** Your instinct is to say no — requirement docs, not patient records. That answer will not survive five minutes. Hospital requirement docs routinely contain: sample patient records in acceptance criteria, screenshots of Epic/Cerner screens, real MRNs in bug-repro steps, test data pulled from prod, clinician names, and free-text descriptions of edge cases that quote actual encounters. Your agent ingests documents from *them*, so **you do not control the input**.

Pick your posture now, because they'll test it:

1. **"We assume PHI is present and handle it as such."** Safest, most credible, forces you to have a BAA and the controls below.
2. **"We contractually prohibit PHI and technically detect/block it."** Only credible if you can *show* the detection and *show* what happens when it fires. Saying "our contract forbids it" with no enforcement is the answer that gets you a 6-month remediation plan instead of a signature.

Go with (1), and layer (2) on top as defense-in-depth. Sign a BAA. Assume it's a Business Associate relationship.

## What they will actually ask

### HIPAA / contractual
- Will you sign a **BAA**? Do you have BAAs with your subprocessors (AWS — yes, covered under the AWS BAA; Bedrock is a HIPAA-eligible service; but *only* if your account is under the AWS BAA and you only use HIPAA-eligible services).
- Which **AWS services in your architecture are HIPAA-eligible**? Every service touching PHI must be on the list. People get caught here on the peripheral stuff — CloudWatch Logs (eligible), a third-party logging/observability SaaS (probably not under BAA), Jira/Linear where the tickets land (Atlassian will sign a BAA on some tiers, not all), an LLM tracing vendor like LangSmith/Langfuse (this is a very common gap — **LangGraph shops leak PHI into LangSmith traces**).
- **Encryption at rest and in transit**, with KMS CMKs — they'll want customer-managed keys, possibly a key you control.
- **Minimum necessary** — can you justify that the agent sees only what it needs?
- **Data retention and deletion** — how long do you hold their docs, prompts, outputs, traces? Can you honor a deletion request? Do you have a documented retention schedule?
- **Breach notification** — your obligations, your timeline, your process.

### AI-specific (this is where most vendors fall over)
- **Does Bedrock train on our data?** Answer: no — Bedrock doesn't use inputs/outputs to train base models, and data isn't shared with model providers. Have the AWS documentation link ready. Also confirm you are **not** using a model with a data-sharing carve-out and that you've disabled/never enabled model invocation logging to a bucket that isn't controlled.
- **Where do the prompts and completions go?** Bedrock model invocation logging (to CloudWatch/S3) is an audit control *and* a PHI store. If you turn it on, that bucket is now a PHI repository — encrypt it, restrict it, retain it deliberately, and put it under the BAA. If you leave it off, you've got no AI audit trail and they'll ask about that instead. Turn it on, and treat the bucket properly.
- **Cross-region inference profiles.** Bedrock's default for many newer models is a cross-region inference profile that can route your invocation to another region in the geography. A hospital that has told you "data stays in us-east" will care. Know whether you're using an inference profile and what regions it spans; pin to a single-region model or an explicitly US-only profile.
- **Prompt injection.** Your agent's *input is a document supplied by a user*. That is the canonical injection vector. "What stops a malicious or careless requirement doc from telling your agent to exfiltrate other tenants' data / call a tool it shouldn't / write a ticket containing a credential?" You need an answer with a mechanism, not an intention.
- **What tools can the agent call?** They'll want the full tool manifest, the blast radius of each, and which ones can write. An agent that creates Jira tickets has a write path into their systems. Can it create tickets in arbitrary projects? Can it @-mention? Can it attach files? Can it call arbitrary URLs?
- **Hallucination / accuracy.** "What happens when it generates a wrong ticket?" They're less worried about this than you think, *because it's a dev-workflow tool with a human in the loop* — lean on that hard. Every generated ticket is reviewed by a human before work starts. Say it explicitly; it downgrades your risk classification substantially.
- **Model versioning.** Which model, pinned to which version? What's your process when AWS deprecates it? Does the model change under you without a change-control?
- **Guardrails.** Do you use Bedrock Guardrails? PII detection/redaction is a built-in there and it's an easy, checkable "yes."

### Platform / EKS
- **Multi-tenancy.** Is this SaaS with other customers on the same cluster? If yes, expect real scrutiny: namespace isolation, NetworkPolicies (default-deny egress is what they want to hear), per-tenant KMS keys, per-tenant S3 prefixes with IAM conditions, and proof that tenant A's document can't end up in tenant B's context window. If you have a shared vector store, tenant filtering at query time is a *soft* control — they'll ask if it's enforced at the IAM/index level.
- **Workload identity** — IRSA or EKS Pod Identity, one role per service, least privilege. No node-role credential inheritance. No static access keys anywhere (you already know this).
- **Egress control.** Can a compromised agent pod reach the internet? Default-deny egress + VPC endpoints for Bedrock/S3/STS. "Our agent calls Bedrock over a PrivateLink VPC endpoint and has no internet route" is a sentence that ends a whole line of questioning.
- **Admission control / supply chain** — image signing, private ECR, SBOM, base-image CVE scanning, no `latest` tags, non-root containers, read-only root FS, seccomp/AppArmor. Also: your Python dependency tree includes LangChain/LangGraph, which pulls a *lot*. They may ask about SCA scanning.
- **Secrets** — External Secrets/Vault/Secrets Manager, not K8s Secrets in git.
- **Control plane** — private endpoint, audit logs to CloudWatch, IMDSv2 enforced.

### Organizational
- **SOC 2 Type II.** They will ask. If you don't have it, say so plainly and say when. HITRUST if you want to skip a lot of questionnaire pain with health systems — expensive, but it's the currency in this market.
- **Pen test** — recent, third-party, with a remediation summary you can share.
- **Vulnerability management SLAs** — critical patched in N days.
- **Access control on your side** — who at your company can see their data? SSO+MFA, JIT/break-glass access, logged and reviewed.
- **Incident response plan** — written, tested, with a tabletop exercise on record.
- **Subprocessor list** — complete. Including AI vendors. Including your observability stack.
- **Vendor risk questionnaire** — they'll send a 300-line spreadsheet. Ask for it *now*, before the meeting.

## What you're most likely missing (ranked)

1. **LLM trace/observability data containing PHI in a non-BAA SaaS.** LangSmith, Langfuse Cloud, Datadog LLM Obs, Helicone — if any of these are in the loop, your prompts (which contain their document text) are leaving the boundary. Self-host it or route it to your own S3/OpenSearch. This is the single most common finding in LangGraph shops and it's the one that will blow up the review.
2. **A prompt-injection defense you can name.** Not "we're aware of it." Something like: untrusted document content is delimited and never merged with the system prompt; the agent has a fixed tool allowlist with no dynamic tool loading; tool outputs are also treated as untrusted; the ticket-writing tool is constrained to one project, one issue type, no attachments; there's an output filter before anything reaches their Jira; and there's a human approving every ticket.
3. **An AI-specific audit trail.** For every generated ticket: which model+version, which prompt version, which source doc + hash, which tools were called with what arguments, what the human reviewer did (approve/edit/reject), timestamp, actor. Immutable-ish store (S3 with Object Lock is a nice thing to be able to say). Right now you probably have LangGraph checkpoints in Postgres and CloudWatch logs, which is *close* but not framed as an audit trail. Frame it as one.
4. **PHI detection on ingest.** A Comprehend Medical / Bedrock Guardrails PII pass on inbound documents, with a defined action (redact, or flag-and-block, or tag-and-proceed-under-BAA). Even if the answer is "we allow it because we have a BAA," having the *detection* means you can prove what was in scope.
5. **A data flow diagram.** One page. Every hop the customer's document takes, every store it lands in, every boundary it crosses, retention at each. They will ask for it, and if you draw it live on the call you will discover a store you forgot about. Draw it this week.
6. **Model/system card.** One page: purpose, model used, inputs, outputs, known limitations, failure modes, human oversight, out-of-scope uses. Cheap to write, disproportionately reassuring, and increasingly a standard ask (NIST AI RMF, ISO 42001, and the EU AI Act have all normalized this).
7. **Eval results.** "How do you know it works?" A golden set of requirement docs → expected tickets, with accuracy/regression numbers, and a CI gate that blocks a prompt or model change that regresses it. Most teams have zero of this and it's a visible maturity signal.
8. **Retention/deletion for LangGraph state.** Checkpointers accumulate full conversation state including document content, indefinitely, by default. Nobody sets a TTL. You probably haven't.

## What to do before the meeting

- Draw the data flow diagram; find the store you forgot about.
- Kill or self-host any LLM tracing SaaS.
- Confirm your AWS account is under the AWS BAA and every service you use is HIPAA-eligible.
- Check whether you're on a cross-region inference profile.
- Turn on Bedrock model invocation logging into an encrypted, access-controlled, retention-bounded bucket.
- Turn on Bedrock Guardrails with PII detection, even minimally.
- Set a TTL on LangGraph checkpoints.
- Write the one-page system card and the tool manifest.
- Ask them for their vendor questionnaire *in advance* and fill it out before you're in the room.

## The meta-point

Go in leading with the human-in-the-loop and the fact that this is a **developer productivity tool, not a clinical system**. No patient-facing output, no clinical decision, no automated action on a patient record. That framing puts you in the lowest-risk tier they have, and most of the scary questions become manageable. What you cannot hand-wave is the data path — because their documents are your input, and they will follow that document all the way through your system and ask where every copy of it lives.
