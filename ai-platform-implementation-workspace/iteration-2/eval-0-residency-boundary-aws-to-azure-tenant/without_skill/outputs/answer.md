# Residency boundary: AWS/Bedrock → customer's Azure tenant

## First, the correction

**Self-hosting Langfuse does not mean you're covered on traces.** Self-hosting is about *who operates the software*, not *where the bytes sit*. If your Langfuse instance runs in your AWS account, every prompt, completion, tool arg, and retrieved chunk you send it has already left the customer's tenant. Traces are arguably the *worst* residency exposure you have — they're the only place where the full payload is stored in plaintext, indefinitely, and joined across sessions.

Same trap applies to your Postgres checkpointer: LangGraph checkpoints are not "state metadata," they're the serialized message history. That's the customer's data, verbatim.

So the honest inventory is bigger than it looks.

## Draw one line: payload plane vs. control plane

The rule that survives an auditor: **anything that has ever touched a customer payload must live in their tenant. Everything else can stay.**

| Component | Moves? | Why |
|---|---|---|
| Bedrock inference | **Must move** | Prompt + completion cross the boundary. Non-negotiable. |
| Postgres checkpointer | **Must move** | Checkpoints = full conversation state. |
| Langfuse (all of it: PG + ClickHouse + Redis + blob store) | **Must move** | Stores raw prompts/completions/attachments. |
| Vector store / embeddings | **Must move** | Embeddings are derived from their documents; treat as in scope. |
| Document/object store, raw uploads | **Must move** | Obvious. |
| Queues, caches, DLQs carrying payloads (SQS, Redis) | **Must move** | DLQs are the classic leak — failed messages sit there with full bodies. |
| App logs, if you log prompts or tool I/O | **Must move** | Audit your log statements. CloudWatch is not their tenant. |
| Any agent tool that calls a third party (Tavily, Serper, an external OCR, a hosted reranker) | **Must move or die** | A LangGraph tool node is an egress path. This is the sneakiest violation. |
| Guardrails / content safety (Bedrock Guardrails is in-path) | **Must move** | It sees the payload. |
| — | | |
| CI/CD, container registry, IaC + Terraform state | **Can stay** | No customer data — assuming state has no payload and no client secrets. |
| Prompt registry / prompt versions | **Can stay** | Your IP, not their data. |
| Aggregate telemetry: latency, token counts, error rates, cost | **Can stay** | Only if strictly non-payload. Metric *labels* leak — no `user_id`, no doc names, no error strings containing content. |
| Eval golden sets | **Depends** | Synthetic → stays. Built from real customer transcripts → that's their data. Most teams get this wrong. |
| Your LangGraph source, your Helm charts | **Can stay** | Code isn't data. |

## The gotchas nobody budgets for

**1. Azure OpenAI abuse monitoring.** By default Azure OpenAI retains prompts and completions for up to 30 days for abuse monitoring, with possible Microsoft human review. Under a strict "nothing leaves our tenant" reading, that is a violation and you've just rebuilt the same problem in a new cloud. You must apply for **Limited Access / modified abuse monitoring** (a Microsoft application form) to disable it. Budget weeks, not days. If you skip this, an auditor will find it.

**2. Claude might not follow you.** You're presumably prompt-tuned on Claude via Bedrock. Microsoft Foundry has added Anthropic models, but **verify where inference actually executes** — if Foundry proxies to Anthropic-managed infrastructure, it fails the exact same test Bedrock does, and you've done the migration for nothing. Confirm this in writing before you plan around it. Your fallbacks: Azure OpenAI (GPT family) with a private endpoint, or open weights (Llama/Mistral/Qwen) self-hosted on AKS with GPUs — full control, full ops burden.

Either way, **prompts do not transfer 1:1 across model families.** Tool-calling schemas, system prompt handling, streaming chunk shapes, and refusal behavior all differ. Assume a re-tuning cycle and a full eval re-run. Budget for it explicitly; this is usually the largest hidden cost of a cross-cloud move, larger than the infra work.

**3. Langfuse v3's storage dependencies.** It needs Postgres, ClickHouse, Redis/Valkey, and an S3-compatible blob store. On Azure: Azure Database for PostgreSQL Flexible Server, ClickHouse on AKS (not ClickHouse Cloud — that's a third-party tenant, same problem again), Azure Cache for Redis, and for blob storage verify current Azure Blob support; MinIO on AKS is the safe fallback. This is a real deployment, not a container swap.

**4. Postgres checkpointer + PgBouncer.** `langgraph-checkpoint-postgres` uses psycopg with prepared statements. Azure PG Flexible Server's built-in PgBouncer in transaction pooling mode will break them. Set `prepare_threshold=None` on the connection, or connect direct. You will hit this.

**5. Bedrock Guardrails → Azure AI Content Safety** is not a feature-for-feature port. Different detectors, different thresholds. Re-tune and re-baseline.

## Before you build any of this — one question for the customer

"No data leaves our tenant" is three different requirements wearing a trenchcoat, and they cost wildly different amounts:

1. **Data must stay in Azure** (any Azure) — then run it in *your* Azure subscription. You keep your ops model. Cheapest by far.
2. **Data must stay in *their* subscription** — you are now shipping a deployable product into someone else's cloud. No prod access, no live debugging, releases go through *their* change control, and every customer becomes a single-tenant deployment. This is a company-strategy change, not an infra ticket. Price it accordingly.
3. **Data must stay in a region/geo** — orthogonal, and honestly the easiest.

And the meta-question: **is this a contractual/policy line or a regulatory one?** A large share of "nothing leaves our tenant" demands come from a DPA template, not from a statute. It's worth putting on the table whether a signed DPA + Bedrock's no-training/no-retention terms + cross-region inference *disabled* + a PrivateLink path clears their actual policy. Sometimes it does, and you just saved a quarter. If it's a hard sovereignty clause (EU public sector, certain healthcare), it doesn't, and you go build it — but find out *which one it is* first, because you cannot afford to guess on a migration this expensive.

(Side note: if you're currently using Bedrock **cross-region inference profiles**, you're already moving payloads between AWS regions without an explicit region guarantee. Worth knowing before someone asks.)

## If you do move: sequence

1. **Abstract the model call first, on AWS.** Get everything behind one interface (`ChatBedrockConverse` → a provider-agnostic seam) and land your eval harness *before* you touch clouds. You need a baseline to migrate against, or you'll never know what the swap broke.
2. Stand up Azure PG Flexible Server, repoint the checkpointer, migrate state.
3. Stand up Langfuse in-tenant (the full v3 dependency stack). Cut traces over.
4. Swap the model provider. Re-run evals against the baseline from step 1. Expect regressions; fix prompts.
5. Audit every tool node for egress. Then enforce it: default-deny NetworkPolicy on AKS + Azure Firewall egress allowlist.
6. **Prove the boundary.** This is what actually gets you through the security review, and architecture diagrams won't do it:
   - `publicNetworkAccess: Disabled` on the Azure OpenAI account, private endpoint only
   - Default-deny egress with *flow logs* (the logs are the evidence)
   - Azure Policy denying resource creation outside the approved region/subscription
   - Diagnostic settings on the model endpoint → Log Analytics workspace in their tenant
   - Written confirmation of modified abuse monitoring

The customer's auditor doesn't want to hear "data stays in the tenant." They want a config export and a log that proves nothing *could* have left.
