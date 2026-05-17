# Monorepo Architecture Reference

## Where Infrastructure Lives

Every application monorepo owns its own Terragrunt-managed Terraform stack at `applications/<app>/infrastructure/`. This stack creates all app-specific resources (K8s namespaces, IRSA roles, Vault auth, S3 buckets, event-bus wiring, scheduled jobs, file gateways) and reads outputs from a **base environment stack** (EKS cluster, VPC, hosted zones, ingress endpoints, runner IAM roles) via `data.terraform_remote_state`.

There is no hierarchy of stacks to remember beyond: *base environment stack → this app's stack*. The base environment stack is bootstrapped once per environment; the app stack is the responsibility of the app team.

---

## In-Repo Infrastructure Layout

```
applications/<app>/infrastructure/
├── <env>/                              # one folder per environment: dev/, qa/, prod/
│   ├── terragrunt.hcl                  # backend, source = ../environment
│   └── terraform.tfvars                # services = {} map and env-specific values
├── environment/                        # the root Terraform module — shared across envs
│   ├── backend.tf                      # remote_state inputs from the base env stack
│   ├── providers.tf                    # aws, aws.utility, kubernetes, vault, postgresql
│   ├── variables.tf                    # services var (typed), bucket names, domains
│   ├── locals.tf                       # derived locals: namespaces set, tags
│   ├── kubernetes.tf                   # namespaces + for_each over services map
│   ├── iam.tf                          # policy docs + aws_iam_policy resources
│   ├── storage.tf                      # S3 buckets, bucket policies
│   ├── <feature>.tf                    # stack-level features (one file per concern)
│   └── outputs.tf
└── modules/                            # repo-local TF modules (event-bus connectors, schedulers)
```

Each env folder is small (two files). All real Terraform lives once in `environment/` and is rendered per-env by Terragrunt with the env's tfvars.

---

## `terragrunt.hcl` Per Environment

```hcl
terraform {
  source = "${get_parent_terragrunt_dir()}/..//environment///"
}

locals {
  identifier     = "<app>-<env>"
  layer          = "<app>"
  aws_region     = "us-east-1"

  backend_bucket = "${local.identifier}-terraform-state-${local.aws_region}-${get_aws_account_id()}"
  dynamodb_table = "${local.identifier}-lock-table-${local.aws_region}-${get_aws_account_id()}"
}

remote_state {
  backend = "s3"
  config = {
    bucket         = local.backend_bucket
    dynamodb_table = local.dynamodb_table
    key            = "${local.layer}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
  }
}
```

The `layer` local becomes the state key prefix and identifies this app's stack in the environment's state bucket. Other stacks in the same environment (e.g., the base environment stack at `core/terraform.tfstate`) live under different keys in the same bucket.

Apply a specific environment:

```bash
cd applications/<app>/infrastructure/<env>
terragrunt apply
```

---

## `terraform.tfvars` Per Environment

This file is where the service registry lives. Each environment can have a different service set.

```hcl
environment    = "<env>"
domain_name    = "<env>.example.com"

# Bucket names — pinned to keep buckets stable across re-applies
exposure_bucket_name = "<app>-<env>-exposure-source-xxxx"

# Service registration
services = {
  <service-a> = { namespace = "<namespace>", public = false, internal = true, credentials = true,  rotation = false }
  <service-b> = { namespace = "<namespace>", public = false, internal = true, credentials = true,  rotation = true  }
  <service-c> = { namespace = "<other-ns>", public = true,  internal = true, credentials = false, rotation = false }
}
```

The corresponding TF variable declaration in `environment/variables.tf`:

```hcl
variable "services" {
  type = map(object({
    namespace   = string
    public      = bool
    internal    = bool
    credentials = bool
    rotation    = bool
  }))
}
```

Adding a service is a one-line change here per environment plus any IAM policy edits.

---

## Remote State Inputs

`environment/backend.tf` declares the app stack's own backend (config bag, the actual values come from Terragrunt) plus `data.terraform_remote_state` blocks for everything this stack consumes.

```hcl
terraform {
  backend "s3" {
    encrypt = true
  }
}

# Base environment stack — EKS, VPC, DNS, ingress endpoints, runner roles
data "terraform_remote_state" "environment" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "core/terraform.tfstate"
    region = local.region
  }
}

# Optional: a shared tools stack (e.g., for ingress gateway endpoints)
data "terraform_remote_state" "environment_tools" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "applications/terraform.tfstate"
    region = local.region
  }
}

# Optional: cross-account utility stack (ECR repos, monitoring)
data "terraform_remote_state" "utility" {
  backend = "s3"
  config = {
    assume_role = { role_arn = local.utility_role_arn }
    bucket      = local.utility_bucket
    key         = "terraform.tfstate"
    region      = local.utility_region
  }
}
```

### Typical Outputs Consumed From the Base Environment Stack

| Output | Used For |
|---|---|
| `eks_cluster_endpoint` | Kubernetes provider + service-wiring module |
| `eks_cluster_name` | kubeconfig + module input |
| `eks_cluster_oidc_issuer_url` | IRSA trust policy in the service-wiring module |
| `internal_domain_zone_id` | Internal Route53 zone for service DNS |
| `public_domain_hosted_zone_id` | Public Route53 zone for public services |
| `gateway_internal_nlb_endpoint` | Target for internal CNAMEs |
| `gateway_public_alb_endpoint` | Target for public CNAMEs |
| `kafka_bootstrap_brokers` | Kafka topic / event-bus connector inputs |
| `aurora_cluster_endpoint`, `aurora_master_user_name`, `aurora_root_password` | Postgres provider |
| `rotation_lambda_arn`, `rotation_lambda_role_arn` | Secret rotation wiring |
| `github_runner_role` | Trust policy for CI/CD assumed role |
| `static_assets_bucket_arn` | Bucket policy targets if reused by this app |

The exact output names are a contract between this stack and the base environment stack — they belong to the base environment's docs, not this skill.

---

## Provider Configuration

```hcl
terraform {
  required_providers {
    aws        = { source = "hashicorp/aws",          version = "~> 6.0" }
    kubernetes = { source = "hashicorp/kubernetes",   version = "~> 3.0" }
    vault      = { source = "hashicorp/vault",        version = "~> 5.0" }
    postgresql = { source = "cyrilgdn/postgresql",    version = "~> 1.0" }
    kafka      = { source = "Mongey/kafka",           version = "~> 0.13" }
    random     = { source = "hashicorp/random",       version = "~> 3.0" }
    null       = { source = "hashicorp/null",         version = "~> 3.0" }
  }
}

provider "aws" {
  region = var.region
}

# Cross-account access — for resources living in a separate account (e.g., ECR repos
# in a utility account). Always via assume_role with a role ARN, never with access keys.
provider "aws" {
  alias  = "utility"
  region = var.region
  assume_role {
    role_arn = var.utility_role_arn
  }
}

# Optional replica region for cross-region resources
provider "aws" {
  alias  = "replica"
  region = "us-east-1"
}

data "aws_eks_cluster" "cluster" {
  name = data.terraform_remote_state.environment.outputs.eks_cluster_name
}

data "aws_eks_cluster_auth" "cluster" {
  name = data.terraform_remote_state.environment.outputs.eks_cluster_name
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.cluster.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.cluster.token
}

provider "vault" {
  address = var.vault_address
}

provider "postgresql" {
  host      = data.terraform_remote_state.environment.outputs.aurora_cluster_endpoint
  username  = data.terraform_remote_state.environment.outputs.aurora_master_user_name
  password  = data.terraform_remote_state.environment.outputs.aurora_root_password
  superuser = false
  sslmode   = "require"
}

provider "kafka" {
  bootstrap_servers = split(",", local.kafka_bootstrap_brokers)
  tls_enabled       = false
}
```

The `aws.utility` provider alias exists so a resource block can write into a different AWS account by setting `provider = aws.utility` (or passing `aws.utility` into a module's `providers` block). This is the standard pattern for ECR repositories that live in a shared utility account while the app runs in per-environment accounts.

---

## The Service-Wiring Module

The map-key-to-K8s-and-Vault wiring is handled by a single cross-cutting Terraform module called once per service via `for_each`. This skill does not prescribe the specific module implementation — only the **contract** it must satisfy.

### What the Module Must Create per Service

Given a service entry (`<service-name>`, namespace, public/internal flags, credentials/rotation flags) and the base environment outputs, the module creates:

- `aws_iam_role` — IRSA role with OIDC federated trust scoped to the K8s service account
- `aws_iam_role_policy_attachment` — attaches all `policy_arns` passed in
- `kubernetes_service_account_v1` — named `vault-auth-<env>-<service>`, annotated with the IRSA role ARN
- `kubernetes_secret_v1` — service-account token (type `kubernetes.io/service-account-token`)
- `kubernetes_cluster_role_binding_v1` — grants `system:auth-delegator` to the SA (required for Vault token review)
- `vault_auth_backend` — Kubernetes auth backend at path `kubernetes-<env>-<service>`
- `vault_kubernetes_auth_backend_config` — wires Vault to the K8s cluster using the SA token
- `vault_policy` — grants read on `kv/data/<ORG>/<ENV>/<SERVICE-UPPER>` + a shared org path
- `vault_kubernetes_auth_backend_role` — binds the SA to the Vault policy
- `aws_route53_record.internal` — internal CNAME (if `internal = true`)
- `aws_route53_record.public` — public CNAME (if `public = true`)
- If `credentials = true`: `aws_secretsmanager_secret` + a Postgres role created via the `postgresql` provider
- If `rotation = true`: `aws_secretsmanager_secret_rotation` against the env's rotation Lambda

### Invocation Skeleton

```hcl
resource "kubernetes_namespace_v1" "this" {
  for_each = local.service_namespaces

  metadata {
    name = each.key
    labels = { app = each.key }
  }
}

module "services" {
  for_each = var.services

  source  = "<your-registry>/service-wiring/<your-cloud>"
  version = "<pinned>"

  providers = {
    aws         = aws
    aws.utility = aws.utility
    postgresql  = postgresql
  }

  service_name = each.key
  namespace    = each.value.namespace

  public   = each.value.public
  internal = each.value.internal

  internal_application_ingress_endpoint = data.terraform_remote_state.environment_tools.outputs.gateway_internal_nlb_endpoint
  application_ingress_endpoint          = data.terraform_remote_state.environment_tools.outputs.gateway_public_alb_endpoint
  private_domain_hosted_zone            = data.terraform_remote_state.environment.outputs.internal_domain_zone_id
  public_domain_hosted_zone             = data.terraform_remote_state.environment.outputs.public_domain_hosted_zone_id

  environment          = local.environment
  eks_cluster_endpoint = data.terraform_remote_state.environment.outputs.eks_cluster_endpoint
  eks_cluster_name     = data.terraform_remote_state.environment.outputs.eks_cluster_name
  oidc_provider_url    = data.terraform_remote_state.environment.outputs.eks_cluster_oidc_issuer_url

  policy_arns = [aws_iam_policy.service_policy[each.key].arn]

  credentials         = each.value.credentials
  rotation            = each.value.rotation
  rotation_lambda_arn = data.terraform_remote_state.environment.outputs.rotation_lambda_arn

  tags = local.tags

  depends_on = [kubernetes_namespace_v1.this]
}
```

---

## IAM Decentralization

IAM **roles** are never declared in `iam.tf`. Only **policy documents** and **`aws_iam_policy` resources** live there. Roles are created inside the service-wiring module from the OIDC provider URL.

```hcl
# iam.tf — define a per-service policy document and resource
data "aws_iam_policy_document" "<service-name>" {
  statement {
    actions = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
    resources = [
      module.<bucket>.s3_bucket_arn,
      "${module.<bucket>.s3_bucket_arn}/*",
    ]
  }

  statement {
    actions   = ["sqs:*"]
    resources = ["*"]
  }
}

locals {
  service_policy = {
    <service-a> = data.aws_iam_policy_document.<service-a>.json
    <service-b> = data.aws_iam_policy_document.<service-b>.json
  }
}

resource "aws_iam_policy" "service_policy" {
  for_each = var.services

  name   = "${each.value.namespace}-${each.key}-${random_string.this.id}"
  policy = local.service_policy[each.key]
}
```

The `random_string.this.id` suffix lets the policy be replaced without name collisions; it is generated once and persisted in state.

If two services genuinely need the same policy body, share the policy document but still produce one `aws_iam_policy` per service so that future divergence is a one-line change.

---

## Stack-Level Resources

Not everything lives inside `kubernetes.tf` + `iam.tf`. The app stack also typically owns:

- **S3 buckets** (`storage.tf`) — per-app buckets with explicit bucket policies that grant access to wiring-module-created role ARNs.
- **DynamoDB routing tables** — used by file gateways or feature flag systems.
- **Event-bus integrations** — connectors that route external events (Auth0, AWS service events, partner webhooks) into Kafka topics, typically via a Lambda. Use a local module under `infrastructure/modules/eventbridge-connector/`.
- **Kafka topics** (`kafka_topic` resources) — declared in the same file as the connector that produces to them.
- **Scheduled jobs** — EventBridge schedule expressions that fire into a Kafka topic to trigger batch jobs in services. Use a local module under `infrastructure/modules/scheduled-job/`.
- **File gateways** — CloudFront distributions with multiple S3 origins plus a DynamoDB routing table. Use a local module under `infrastructure/modules/s3_file_origin/`.

### Bucket Policy Referencing Wiring-Module Role ARNs

```hcl
data "aws_iam_policy_document" "<bucket>_policy" {
  statement {
    sid    = "AllowServiceRoleAccess"
    effect = "Allow"

    principals {
      type = "AWS"
      identifiers = compact([
        try(module.services["<service-a>"].iam_role_arn, ""),
        try(module.services["<service-b>"].iam_role_arn, ""),
      ])
    }

    actions   = ["s3:GetObject", "s3:GetObjectVersion", "s3:PutObject"]
    resources = ["${module.<bucket>.s3_bucket_arn}/*"]
  }
}
```

The `try(...)` wrapping makes the policy resilient when a service is added or removed from the `services` map — the bucket policy compiles either way.

---

## Safe Refactors

### `moved {}` Blocks for Hard-Coded → `for_each`

When the stack first lifts hard-coded resources into `for_each`, use `moved {}` blocks to preserve state and avoid recreation:

```hcl
moved {
  from = kubernetes_namespace_v1.<old-resource-name-a>
  to   = kubernetes_namespace_v1.this["<namespace-a>"]
}

moved {
  from = kubernetes_namespace_v1.<old-resource-name-b>
  to   = kubernetes_namespace_v1.this["<namespace-b>"]
}
```

Without these, `terragrunt apply` would destroy the old namespace (and every pod and service inside it) and re-create the new one.

### `try()` for Parallel-Name Cutover

When renaming a service, both the old and new keys may exist in `services = {}` simultaneously during the cutover window. Downstream resources referencing per-service module outputs should use `try()` to remain valid in any state:

```hcl
identifiers = compact([
  try(module.services["<old-name>"].iam_role_arn, ""),
  try(module.services["<new-name>"].iam_role_arn, ""),
])
```

Remove the unused branch once the cutover is final.

### Regex IAM Role Discovery

For downstream resources (e.g., DynamoDB resource policies) that need to grant access to any role matching a service stem during a rename:

```hcl
data "aws_iam_roles" "<service-stem>_clients" {
  name_regex = ".*<service-stem>.*"
}
```

This avoids hardcoding role ARNs and survives a rename without policy churn.

---

## Vault KV Path Convention

```
kv/data/<ORG>/<ENV>/<SERVICE-NAME-UPPER>
```

Examples (placeholders):
- `kv/data/<ORG>/DEV/<SERVICE-A-UPPER>`
- `kv/data/<ORG>/PROD/<SERVICE-B-UPPER>`
- `kv/data/<ORG>/<ENV>/TERRAFORM`   ← shared, readable by all services

The service-wiring module grants the per-service policy read access on both the service-specific path and the shared org-level path. Adding extra Vault paths to a service's policy is typically done via an `extra_vault_paths` module input.

### Migrating Secrets When a Service Is Renamed

```bash
vault kv get -format=json kv/<ORG>/<ENV>/<OLD-NAME-UPPER> \
  | jq -c '.data.data' \
  | vault kv put kv/<ORG>/<ENV>/<NEW-NAME-UPPER> -

vault kv get kv/<ORG>/<ENV>/<NEW-NAME-UPPER>
vault kv metadata delete kv/<ORG>/<ENV>/<OLD-NAME-UPPER>
```

---

## Local TF Modules in `infrastructure/modules/`

Repo-local modules belong here when they wrap a reusable wiring pattern that's specific to this app stack (and likely not worth publishing to a registry). Typical examples:

- `eventbridge-connector/` — wires one EventBridge pattern to one Lambda → Kafka topic delivery
- `kafka-connector/` — VPC-attached Lambda that produces to Kafka brokers
- `batch-eventbridge/` — generic dispatcher that posts to a known batch-trigger Kafka topic on a cron
- `scheduled-job/` — EventBridge schedule fires a payload at the batch-eventbridge dispatcher
- `s3_file_origin/` — wraps an S3 origin + origin-request Lambda for use as a CloudFront origin

Treat these as ordinary Terraform modules — give them clear inputs, no environment-specific hardcoding, and pin any internal provider requirements.
