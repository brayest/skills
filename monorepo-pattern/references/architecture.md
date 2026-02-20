# Monorepo Architecture Reference

## 4-Layer Terragrunt Hierarchy

Every application in this system sits inside a 4-layer infrastructure hierarchy managed by Terragrunt. Understanding which layer owns what is mandatory before making any infrastructure change.

```
DR Layer           → btp-disaster-recovery/
Utility Layer      → infrastructure/utility/         (shared: Vault, monitoring, networking)
Environment Layer  → infrastructure/environment/     (EKS, VPC, DNS, load balancers, IAM roles)
Application Layer  → applications/{app-name}/        (app-specific AWS resources + K8s wiring)
```

Each layer reads outputs from layers below it via `data.terraform_remote_state`.

---

## Application Monorepo Structure

```
applications/{app-name}/
├── .github/workflows/ci-cd.yml          # Full pipeline: detect → build → deploy → test
├── environment/                          # Shared Terraform for all services in this app
│   ├── backend.tf                        # Remote state config + data sources from lower layers
│   ├── providers.tf                      # AWS, K8s, Vault provider configs
│   ├── locals.tf                         # services map + cluster/VPC config assembled from remote states
│   ├── variables.tf                      # Inputs (region, project, buckets, environment)
│   ├── outputs.tf                        # Exports (IAM ARNs, queue URLs, table names, etc.)
│   ├── iam.tf                            # IAM policy documents + aws_iam_policy resources (no roles)
│   ├── kubernetes.tf                     # K8s namespace + btp_service_cross module loop
│   └── {feature}.tf                      # One file per AWS feature: sqs.tf, dynamodb.tf, storage.tf, etc.
├── development/
│   └── terragrunt.hcl                    # Source points to ../environment, sets layer name + S3 backend
├── qa/
│   └── terragrunt.hcl
├── prod/
│   └── terragrunt.hcl
├── charts/
│   ├── backend/                          # Generic Python/worker Helm chart (reused by all backend services)
│   ├── frontend/                         # Generic UI Helm chart
│   └── values/
│       └── {service}.yaml               # Per-service Helm value overrides
├── {service-a}/                          # Service source code
│   └── Dockerfile
├── {service-b}/
│   └── Dockerfile
└── config/                               # Shared config files mounted to /usr/share/env in K8s
```

---

## Remote State Dependencies

### backend.tf Pattern

Every application environment/ reads from three remote state sources:

```hcl
# 1. Environment layer (EKS, DNS, load balancers, IAM roles)
data "terraform_remote_state" "environment" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket   # "btp-{env}-terraform-state-us-east-1-{account_id}"
    key    = "core/terraform.tfstate"
    region = local.region
  }
}

# 2. Utility layer (Vault, monitoring — cross-account via assume role)
data "terraform_remote_state" "btp_utility" {
  backend = "s3"
  config = {
    assume_role = { role_arn = local.utility_role_arn }
    bucket      = local.utility_bucket    # utility account state bucket
    key         = "terraform.tfstate"
    region      = local.utility_region
  }
}

# 3. Other application layers (when consuming shared app infrastructure)
data "terraform_remote_state" "environment_tools" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "applications/terraform.tfstate"
    region = local.region
  }
}
```

### Key Outputs Consumed From Environment Layer

| Output | Used For |
|--------|----------|
| `eks_cluster_endpoint` | Kubernetes provider + btp_service_cross module |
| `eks_cluster_name` | kubeconfig, module input |
| `eks_cluster_oidc_issuer_url` | IRSA trust policy in btp_service_cross |
| `internal_load_balancer_endpoint` | Internal Route53 CNAME target |
| `public_load_balancer_endpoint` | Public Route53 CNAME target |
| `internal_domain_zone_id` | Route53 hosted zone for `*.btp-{env}.int` |
| `public_domain_hosted_zone_id` | Route53 hosted zone for public domain |
| `eks_admin_role` | K8s RBAC |
| `github_runner_role` | CI/CD IRSA role |
| `private_subnet_ids` | VPC subnet placements |
| `vpc_id`, `vpc_cidr` | Security group rules |

---

## Terragrunt Per-Environment Files

Each environment (development/, qa/, prod/) has a `terragrunt.hcl` that:
1. Points `source` to `../environment` (shared Terraform)
2. Declares S3 backend with environment-specific bucket and lock table
3. Sets the state key as `{layer-name}/terraform.tfstate`

```hcl
terraform {
  source = "${get_parent_terragrunt_dir()}/..//environment///"
}

locals {
  identifier    = "btp-dev"
  layer         = "cope"                                      # Becomes state key prefix
  aws_region    = "us-east-1"
  backend_bucket = "btp-dev-terraform-state-us-east-1-{account}"
  dynamodb_table = "btp-dev-lock-table-us-east-1-{account}"
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

Apply a specific environment:
```bash
cd applications/{app-name}/development
terragrunt apply
```

---

## btp_service_cross Module

This module is the core wiring unit. It creates everything needed for one Kubernetes service to run securely:

**Source**: `app.terraform.io/bigticket/btp_service_cross/aws` (private Terraform registry)
**Current version**: 1.5.2

**What it creates per service**:
- `aws_iam_role` — IRSA role with OIDC federated trust scoped to the K8s service account
- `aws_iam_role_policy_attachment` — Attaches all `policy_arns` to the IRSA role
- `kubernetes_service_account_v1` — Named `vault-auth-{env}-{service}`, annotated with IRSA role ARN
- `kubernetes_secret_v1` — Service account token (type: `kubernetes.io/service-account-token`)
- `kubernetes_cluster_role_binding_v1` — Grants `system:auth-delegator` to the service account (required for Vault token review)
- `vault_auth_backend` — Kubernetes auth backend at path `kubernetes-{env}-{service}`
- `vault_kubernetes_auth_backend_config` — Wires Vault to the K8s cluster using the SA token
- `vault_policy` — Grants read on `kv/data/BTP/{ENV}/{SERVICE}` + `kv/data/BTP/{ENV}/TERRAFORM` + any `extra_vault_paths`
- `vault_kubernetes_auth_backend_role` — Binds the service account to the Vault policy
- `aws_route53_record.internal` — Internal CNAME (if `internal = true`)
- `aws_route53_record.public` — Public CNAME (if `public = true`)

**Usage pattern in kubernetes.tf**:

```hcl
resource "kubernetes_namespace_v1" "app" {
  metadata {
    name = "{app-namespace}"
    labels = { app = "{app-namespace}" }
  }
}

module "app_services" {
  for_each = local.app_services        # Defined in locals.tf

  source  = "app.terraform.io/bigticket/btp_service_cross/aws"
  version = "1.5.2"

  service_name = each.key
  namespace    = each.value.namespace

  public   = each.value.public
  internal = each.value.internal

  internal_application_ingress_endpoint = data.terraform_remote_state.environment.outputs.internal_load_balancer_endpoint
  private_domain_hosted_zone            = data.terraform_remote_state.environment.outputs.internal_domain_zone_id
  public_domain_hosted_zone             = data.terraform_remote_state.environment.outputs.public_domain_hosted_zone_id
  application_ingress_endpoint          = data.terraform_remote_state.environment.outputs.public_load_balancer_endpoint

  environment          = local.environment
  eks_cluster_endpoint = data.terraform_remote_state.environment.outputs.eks_cluster_endpoint
  eks_cluster_name     = data.terraform_remote_state.environment.outputs.eks_cluster_name
  oidc_provider_url    = local.cluster_config.cluster_oidc_issuer_url

  policy_arns = [
    aws_iam_policy.{app}_sqs.arn,
    aws_iam_policy.{app}_s3.arn,
    # ... all service-level policies
  ]

  extra_vault_paths        = ["{EXTRA-KV-PATH}"]    # Optional additional Vault paths
  extra_vault_policy_names = []                      # Optional additional Vault policies

  tags = local.tags

  depends_on = [kubernetes_namespace_v1.app]
}
```

---

## IAM Decentralization Pattern

IAM roles are **not** created in `iam.tf`. Only policy documents and `aws_iam_policy` resources live there. Roles are created inside the `btp_service_cross` module.

```hcl
# iam.tf — define scoped policy documents
data "aws_iam_policy_document" "app_sqs" {
  statement {
    actions = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", ...]
    resources = [aws_sqs_queue.main.arn, aws_sqs_queue.dlq.arn]
  }
}

resource "aws_iam_policy" "app_sqs" {
  name   = "${local.project}-{app}-sqs-${local.environment}"
  policy = data.aws_iam_policy_document.app_sqs.json
}

# kubernetes.tf — attach policies to module
module "app_services" {
  policy_arns = [
    aws_iam_policy.app_sqs.arn,
    # more policies...
  ]
}
```

All services in the `for_each` loop receive the same set of `policy_arns`. If service-specific IAM is needed, create separate module calls (not a `for_each`).

---

## services Map in locals.tf

The `locals.tf` file defines a map of all services in the monorepo. This map drives both the Terraform module loop and provides metadata for CI/CD:

```hcl
locals {
  app_services = {
    service-a = {
      public      = false
      internal    = true
      credentials = false
      namespace   = "{app-namespace}"
      rotation    = false
    }
    service-b = {
      public      = true         # Creates public DNS record
      internal    = true
      credentials = false
      namespace   = "{app-namespace}"
      rotation    = false
    }
  }
}
```

**Naming constraint**: The map key becomes the Kubernetes ServiceAccount name suffix (`vault-auth-{env}-{key}`), the Vault auth mount path (`kubernetes-{env}-{key}`), and the Vault KV path (`BTP/{ENV}/{KEY-UPPERCASED}`). Renaming a key requires migrating Vault secrets and recreating K8s infrastructure.

---

## Vault Secret Path Convention

```
kv/data/BTP/{ENVIRONMENT}/{SERVICE-NAME-UPPERCASED}
```

Examples:
- `kv/data/BTP/DEV/COPE-API`
- `kv/data/BTP/PROD/EXTRACTION-AGENT`
- `kv/data/BTP/DEV/TERRAFORM`  ← shared secrets, readable by all services

The module automatically grants read access to both the service-specific path and the shared `TERRAFORM` path. Add more shared paths via `extra_vault_paths`.

### Migrating Vault Secrets (when renaming a service)

```bash
# Copy all secret data to new path
vault kv get -format=json kv/BTP/{ENV}/{OLD-NAME} \
  | jq -c '.data.data' \
  | vault kv put kv/BTP/{ENV}/{NEW-NAME} -

# Verify new path has data, then delete old
vault kv get kv/BTP/{ENV}/{NEW-NAME}
vault kv metadata delete kv/BTP/{ENV}/{OLD-NAME}
```

---

## Provider Configuration Pattern

```hcl
# providers.tf
provider "aws" {
  region = local.region
}

provider "kubernetes" {
  host                   = data.terraform_remote_state.environment.outputs.eks_cluster_endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.cluster.token
}

provider "vault" {
  address = var.vault_address    # e.g., "http://vault.btp-utility.int/"
}
```
