# "Data can't leave our Azure tenant" — what actually has to move

## First: make them define the boundary

"Won't leave our tenant" is three different requirements, and the answer changes by ~6 months of work depending on which one they mean:

1. **Residency** — "must stay in Azure West Europe." Easy. Region pinning + contractual terms.
2. **Subscription/tenant boundary** — "the resources must be ours, in our subscription, private-linked, no vendor-side persistence, no training on our data." This is what ~90% of enterprises actually mean. Azure OpenAI / AI Foundry satisfies it: the resource lives in *their* subscription, private endpoint, CMK, no training on inputs.
3. **Literal "no Microsoft-operated multi-tenant service touches the payload"** — then even Azure OpenAI is out and you're self-hosting open weights on their AKS with GPU node pools. Rare, but banks and some health systems say it.

Get this answer in writing before you scope anything. Also spend one email probing whether Bedrock in *their own AWS account* with PrivateLink + CMK + model invocation logging to their S3 is acceptable — it usually isn't (the policy is org-wide "Azure only"), but it costs you nothing to ask and it's by far the cheapest outcome.

Assume answer #2 for the rest of this.

## The split: data plane moves, control plane stays

The clean mental model is **BYOC / in-tenant data plane**. Anything that touches customer content runs in their Azure subscription. Anything that only touches *your* code, config, and non-content telemetry stays where it is.

### Has to move (touches customer content)

| Today (AWS) | Azure equivalent | Notes |
|---|---|---|
| Bedrock inference | Azure AI Foundry / Azure OpenAI | Anthropic models are available in Microsoft Foundry — **verify current model + region availability yourself**, don't take my word for it. If Claude isn't available in their region, it's GPT-family or self-hosted. |
| Titan/Cohere embeddings | `text-embedding-3-large`, or self-hosted BGE/E5 on AKS | See "the hidden cost" below. |
| S3 document store | ADLS Gen2 / Blob, private endpoint, CMK in Key Vault | Immutability policy = your Object Lock equivalent. |
| OpenSearch (vector + BM25) | Azure AI Search (hybrid built in), or pgvector on Postgres Flexible Server | AI Search is the closest hybrid-retrieval match. |
| DynamoDB / RDS metadata | Cosmos DB / Azure Postgres | Chunk metadata is derived customer data. It moves. |
| SQS / MSK carrying doc payloads | Service Bus / Event Hubs | If the payload is a pointer, not a blob, this is less painful. |
| Docling/Ray parsing workers | AKS + GPU node pool | Raw docs pass through here. Non-negotiable. |
| API + orchestration services | AKS (or Container Apps) | They see prompts and completions. |
| Bedrock Guardrails | Azure AI Content Safety | Not feature-equivalent. Re-tune your thresholds. |
| Bedrock model invocation logging | Foundry diagnostic settings → their Log Analytics / Blob | This log *contains prompts and completions*. It's customer data. |

### Can stay on AWS (no customer content)

- Source code, prompt templates, model config, Helm charts, Terraform modules.
- CI/CD (GitHub Actions or whatever) — it builds and deploys *into* their tenant, it doesn't process their data.
- Terraform state — **audit it first**. State files leak secrets and sometimes sample data. If it's clean, it stays; if not, move it to their storage account.
- Container registry — but mirror images into their ACR, because their egress policy will block a pull from your ECR anyway. Sign the images, verify at admission.
- Your own control plane: tenant registry, billing, feature flags, license checks.
- **Aggregate, content-free telemetry**: latency, token counts, error rates, retrieval hit-rate. This needs an explicit carve-out in the DPA. Get it — without it you are operating blind in someone else's cloud.

### The fights you'll have

- **Traces.** Datadog LLM Observability / Langfuse / whatever you're using captures prompt and completion bodies. That is a straight-line exfil path out of their tenant and their security team will find it. Either self-host the trace backend in their subscription, or redact payloads at the SDK boundary and ship only spans + metrics. Don't promise "we'll scrub it" and rely on a regex.
- **Eval golden sets.** If they were built from customer documents, they *are* customer data. Your evals now have to run inside their tenant against a shadow environment. Budget for this — it's the thing everyone forgets and it's what stops you from ever shipping a model upgrade again.
- **Your engineers' debug access.** Reading their logs is data access. You need break-glass into their tenant with their approval — Entra guest + PIM with time-bound elevation, or Azure Lighthouse — not standing credentials in a shared vault.

## The hidden cost nobody scopes

The embedding model changes. That means **you reindex the entire corpus, and retrieval quality changes**. Your chunking, your rerankers, your top-k, your prompt — all tuned against Titan/whatever — are now tuned against nothing. You will need to re-run your eval suite and probably re-tune. This is bigger than the infra port and it's the reason "just swap the endpoint" estimates are always wrong by 3x.

Same story for guardrails: Content Safety categories and severity levels don't map 1:1 to Bedrock Guardrails, so your safety behavior shifts and you have to re-baseline.

## How to do it without maintaining two products

Don't fork. Cut abstraction seams at exactly three places and keep one codebase:

1. **Model provider** — one interface for chat + embeddings. LiteLLM if you want it for free, or your own thin adapter (worth it if you're on LlamaIndex — you're mostly just swapping `LLM` and `EmbeddingModel` implementations).
2. **Object store** — one blob interface. S3 vs. Blob is a 200-line adapter.
3. **Vector/search store** — one retriever interface. This one is genuinely leaky (hybrid query syntax differs); expect to write it twice and test it twice.

Everything else stays portable *if it's already on Kubernetes*. Your EKS workloads move to AKS with real but bounded pain: IRSA → AKS Workload Identity (both are OIDC federation, the shape is the same), IAM roles → Entra managed identities + RBAC, SGs/NACLs → NSGs + NetworkPolicy, default-deny egress via Azure Firewall with an FQDN allowlist. If anything is on Lambda/Step Functions/DynamoDB Streams, that part is a rewrite, not a port.

## What I'd actually do this week

1. Get the boundary definition in writing (1, 2, or 3 above) and the telemetry carve-out.
2. Inventory every place a prompt, completion, or document body is written to disk or crosses a network boundary. That list *is* your migration scope — everything else is noise.
3. Check Foundry model availability in their required region **before** promising Claude-class quality.
4. Build the three adapter seams, and stand up one thin end-to-end path in their tenant (blob → parse → embed → AI Search → Foundry → response) as a spike. You'll learn more from that in a week than from a month of architecture docs.

The honest bottom line: your **inference, retrieval, storage, ingestion, and any log that carries a payload** all move. Your **build, deploy, code, and content-free metrics** stay. The migration is mostly mechanical — the part that will actually hurt is re-earning your retrieval and safety quality on a different model family.
