# BTP Vault Structure

## Engine & Paths

- **Vault URL**: `http://vault.btp-utility.int/`
- **Engine**: KV v2 mounted at `kv/`
- **Path pattern**: `kv/BTP/{ENV}/{SERVICE}`
- Each service has exactly one KV v2 entry — a flat map of all its config keys

## Environments

| Environment | Purpose |
|-------------|---------|
| DEV | Development |
| QA | Quality Assurance |
| PROD | Production |
| UTILITY | Shared platform services (CI/CD runners, Grafana, registry) |
| DR | Disaster Recovery |

## Services by Environment

### DEV
BTP-CHAT, BTP-CONSUL-BACKUP, BTP-EMAIL-SERVICE, BTP-EXPOSURE-SERVICE, BTP-HELP-CENTER-API, BTP-IAM-API, BTP-PROPERTY-API, BTP-PROPERTY-UI, BTP-PUBLIC-UI, COPE-API, DEMO, DOC-PROCESSOR, EXTRACTION-AGENT, INSURDATA, TERRAFORM

### QA
BTP-EMAIL-SERVICE, BTP-EXPOSURE-SERVICE, BTP-HELP-CENTER-API, BTP-IAM-API, BTP-PROPERTY-API, BTP-PROPERTY-UI, COPE-API, DOC-PROCESSOR, EXTRACTION-AGENT, INSURDATA, TERRAFORM

### PROD
BTP-EMAIL-SERVICE, BTP-EXPOSURE-SERVICE, BTP-HELP-CENTER-API, BTP-IAM-API, BTP-PROPERTY-API, BTP-PROPERTY-UI, BTP-PUBLIC-UI, COPE-API, DOC-PROCESSOR, EXTRACTION-AGENT, INSURDATA, TERRAFORM

### UTILITY
BTP-GITHUB-RUNNER, GITHUB_RUNNER, GRAFANA, INSURDATA, POSTGIS, TERRAFORM

### DR
BTP-EMAIL-SERVICE, BTP-EXPOSURE-SERVICE, BTP-HELP-CENTER-API, BTP-IAM-API, BTP-PROPERTY-API, BTP-PROPERTY-UI, INSURDATA, TERRAFORM

## Service Categories

### Legacy BTP Platform Services
These have their own databases, Auth0 clients, and Consul configs:
- **BTP-IAM-API** — Identity and access management
- **BTP-PROPERTY-API** — Property management core API
- **BTP-EXPOSURE-SERVICE** — Exposure data management
- **BTP-EMAIL-SERVICE** — Email notifications via Postmark
- **BTP-HELP-CENTER-API** — Help center/knowledge base
- **BTP-PROPERTY-UI** — Property management frontend (Nuxt)
- **BTP-PUBLIC-UI** — Public-facing frontend

### COPE Extraction Monorepo Services
Three services sharing MSK, OpenSearch, S3, and SQS infrastructure:
- **COPE-API** — Orchestration layer (AppConfig, Auth0, DynamoDB, SQS field processing)
- **DOC-PROCESSOR** — Document ingestion (Bedrock embeddings, Kafka, Ray workers)
- **EXTRACTION-AGENT** — LLM-powered extraction (55+ keys — Bedrock models, Kafka topics, semantic mapping)

### Shared Paths
- **TERRAFORM** — Cross-cutting infrastructure values (DB endpoints, Auth0 issuer, service URLs, CDN). Every service policy grants read access to this.

## Authentication Model

### Scripts (vault_manager.py) — Token Auth
- Token resolved from `~/.vault-token-btp` file (first priority) or `VAULT_TOKEN` env var
- Used for human/Claude operational access
- Full read/write access to all `kv/BTP/` paths

### Applications (runtime) — Kubernetes Auth
- Each service has a dedicated auth mount: `kubernetes-{env}-{service}`
- Auth via pod service account JWT → Vault role → read-only policy
- Service accounts named `vault-auth-{env}-{service}` in service namespace
- Token TTL: 1 minute (apps must handle refresh or use vault-agent)
- **COPE services** run in namespace `cope`; legacy services in their own namespaces

### Vault Policies
Legacy services get 2 paths (own secrets + TERRAFORM). COPE services get 3 paths (own + TERRAFORM + BTP-COPE-EXTRACTION shared path). All read-only — no service can write to Vault.

## Sensitive Key Patterns

Keys containing these substrings (case-insensitive) are automatically masked in `read` output:
- `password`
- `secret`
- `key`
- `token`
- `salt`

Use `get` (single key) or `export` (full dump) to retrieve unmasked values.
