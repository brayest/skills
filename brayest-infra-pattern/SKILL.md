---
name: brayest-infra-pattern
description: This skill should be used when working with multi-account, multi-environment Terraform infrastructure managed by Terragrunt in a 4-layer architecture (DR → Utility → Environment → Applications). Use when creating new infrastructure components, adding resources to existing layers, setting up new monorepo infrastructure, understanding remote state dependencies, cross-account access patterns, or working with the Terragrunt wrapper system.
---

# Infrastructure Pattern: Multi-Layer Terragrunt Architecture

## Overview

This skill documents a production-grade, multi-account Terraform infrastructure pattern managed by Terragrunt. Use this pattern for enterprise-scale infrastructure with:
- Multiple AWS accounts (utility, dev, qa, prod, DR)
- Cross-account state access
- Environment multiplication (one codebase, many environments)
- Clear separation of concerns across infrastructure layers

## Architecture Overview

### Four-Layer Dependency Hierarchy

```
┌────────────────────────────────────────────────────────┐
│  Layer 0: DISASTER RECOVERY                             │
│  Purpose: DR VPC, peering, failover infrastructure     │
│  Dependencies: None (foundation layer)                  │
└────────────────────────────────────────────────────────┘
                      ↑ (cross-account)
┌────────────────────────────────────────────────────────┐
│  Layer 1: UTILITY (Shared Platform)                    │
│  Purpose: EKS cluster, VPC, Aurora, Vault, CI/CD       │
│  Account: Separate utility account                     │
│  Dependencies: DR                                       │
└────────────────────────────────────────────────────────┘
                      ↑ (cross-account)
┌────────────────────────────────────────────────────────┐
│  Layer 2: ENVIRONMENT (Per-Environment Core)           │
│  Purpose: Environment VPC, RDS, Route53, IAM base      │
│  Account: Per-environment accounts (dev/qa/prod)       │
│  Dependencies: Utility, DR                             │
└────────────────────────────────────────────────────────┘
                      ↑ (same-account)
┌────────────────────────────────────────────────────────┐
│  Layer 3: APPLICATIONS (Monorepo-Owned)                │
│  Purpose: App-specific S3, IAM, queues, caching        │
│  Account: Same as environment                          │
│  Dependencies: Environment, Utility                    │
└────────────────────────────────────────────────────────┘
```

### Layer Decision Tree

When adding new infrastructure, determine the appropriate layer:

**Is it disaster recovery or VPC peering?** → DR Layer
**Is it shared across ALL environments (dev/qa/prod)?** → Utility Layer
**Is it per-environment but shared across applications?** → Environment Layer
**Is it specific to one application/monorepo?** → Application Layer

### Multi-Account Design

- **Utility Account**: Hosts shared EKS cluster, VPC, Aurora, Vault (single account)
- **Environment Accounts**: Separate accounts for dev, qa, prod (multiple accounts)
- **DR Account**: Separate disaster recovery account
- **Cross-account access**: Via IAM role assumption (hardcoded role ARNs)

## Directory Structure Pattern

### Component Directory Structure

Each infrastructure component follows this pattern:

```
{component-name}/
├── environment/              ← Terraform code (reusable, environment-agnostic)
│   ├── backend.tf           (minimal: encrypt=true + remote state data sources)
│   ├── providers.tf         (AWS provider config, optional cross-account aliases)
│   ├── variables.tf         (input variables)
│   ├── locals.tf            (computed values, remote state extraction)
│   ├── outputs.tf           (exported values for downstream layers)
│   ├── *.tf files           (actual infrastructure resources)
│   └── modules/             (component-specific sub-modules)
├── dev/                      ← Terragrunt wrapper for dev environment
│   ├── terragrunt.hcl       (sources ../environment, configures backend)
│   └── terraform.tfvars     (dev-specific values: account IDs, role ARNs)
├── qa/                       ← Terragrunt wrapper for qa environment
│   ├── terragrunt.hcl
│   └── terraform.tfvars
├── prod/                     ← Terragrunt wrapper for prod environment
│   ├── terragrunt.hcl
│   └── terraform.tfvars
└── utility/                  ← Terragrunt wrapper for utility environment (if applicable)
    ├── terragrunt.hcl
    └── terraform.tfvars
```

### Key Principles

1. **One Terraform root per component**: `environment/` directory contains all `.tf` files
2. **Multiple Terragrunt wrappers**: `dev/`, `qa/`, `prod/` directories wrap the same Terraform code
3. **Terragrunt sources Terraform**: `terraform { source = "../environment" }` in terragrunt.hcl
4. **Git-committed tfvars**: Environment-specific values hardcoded in terraform.tfvars files

## Two-Tier Backend Configuration

### Tier 1: Terragrunt (Actual Backend Configuration)

Terragrunt manages the S3 backend via `remote_state` block in `terragrunt.hcl`:

```hcl
# dev/terragrunt.hcl
locals {
  indentifier    = "{org}"
  environment    = "dev"
  layer          = "{layer-name}"  # e.g., "core", "applications", "cope"
  aws_region     = "us-east-1"
  backend_bucket = "${local.indentifier}-${local.environment}-terraform-state-${local.aws_region}-${get_aws_account_id()}"
  dynamodb_table = "${local.indentifier}-${local.environment}-lock-table-${local.aws_region}-${get_aws_account_id()}"
}

terraform {
  source = "${get_parent_terragrunt_dir()}/..//environment///"
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

### Tier 2: Terraform (Minimal Backend Declaration)

Terraform only declares backend type in `environment/backend.tf`:

```hcl
terraform {
  backend "s3" {
    encrypt = true
  }
}
```

### How It Works

1. Terragrunt reads `remote_state` block → configures S3 backend with bucket/key/lock-table
2. Terraform sees minimal `backend "s3"` block → uses Terragrunt's configuration
3. State is stored: `{org}-{env}-terraform-state-{region}-{account}/{layer}/terraform.tfstate`

**Critical**: Terragrunt handles ALL backend configuration. Terraform backend.tf is intentionally minimal.

## State Organization Pattern

### Shared Buckets with Isolated Keys

- **One S3 bucket per environment** (not per component)
- **Unique keys per component/layer** within the bucket
- **DynamoDB lock table per environment**

**Example bucket structure**:
```
{org}-dev-terraform-state-us-east-1-{account}/
├── core/terraform.tfstate                ← Environment core layer
├── applications/terraform.tfstate        ← Environment tools layer
├── public-gateway/terraform.tfstate      ← Gateway component
└── {app-name}/terraform.tfstate          ← Application-specific infrastructure
```

### Naming Conventions

**Backend bucket pattern**: `{org}-{env}-terraform-state-{region}-{account}`
**Lock table pattern**: `{org}-{env}-lock-table-{region}-{account}`
**State key pattern**: `{layer}/terraform.tfstate`

**Examples**:
- Utility: `{org}-utility-terraform-state-us-east-1-{account}/terraform.tfstate`
- Environment core: `{org}-dev-terraform-state-us-east-1-{account}/core/terraform.tfstate`
- Application: `{org}-dev-terraform-state-us-east-1-{account}/{app}/terraform.tfstate`

### Benefits

- **Cost-effective**: One bucket per environment (not hundreds)
- **Access control**: Single IAM policy per environment
- **Clear namespace**: Keys provide logical separation
- **Avoid bucket proliferation**: Scales to 100+ components without 100+ buckets

## Remote State Dependencies

### Pattern: Data Sources in backend.tf

Consume upstream layer outputs via `data "terraform_remote_state"` blocks:

```hcl
# environment/backend.tf

# Same-account access (no assume_role)
data "terraform_remote_state" "environment" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "core/terraform.tfstate"
    region = local.region
  }
}

# Cross-account access (with assume_role)
data "terraform_remote_state" "utility" {
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.utility_role_arn
    }
    bucket = local.utility_bucket
    key    = "terraform.tfstate"
    region = local.utility_region
  }
}
```

### Dependency Chain Examples

**Application depends on Environment and Utility**:
```hcl
# applications/{app}/environment/backend.tf
data "terraform_remote_state" "environment" { ... }           # Environment core
data "terraform_remote_state" "environment_tools" { ... }     # Environment tools
data "terraform_remote_state" "utility" { ... }               # Utility (cross-account)
```

**Environment depends on Utility and DR**:
```hcl
# infrastructure/environment/{component}/environment/backend.tf
data "terraform_remote_state" "utility" { ... }               # Utility (cross-account)
data "terraform_remote_state" "utility_tools" { ... }         # Utility tools (cross-account)
data "terraform_remote_state" "dr" { ... }                    # DR (cross-account)
```

**Utility depends on DR**:
```hcl
# infrastructure/utility/{component}/environment/backend.tf
data "terraform_remote_state" "dr" { ... }                    # DR (cross-account)
```

### Inline assume_role vs Provider Aliases

**Use inline `assume_role` in data source config** (recommended):
```hcl
data "terraform_remote_state" "utility" {
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.utility_role_arn
    }
    # ...
  }
}
```

**Not provider aliases** (provider aliases are for resources, not state access).

## Variable Flow Pattern

### Critical: Variables Come from Hardcoded tfvars

Variables do NOT flow through Terragrunt. They come from git-committed `terraform.tfvars` files:

**Flow**: `terraform.tfvars` → `variables.tf` → `locals.tf` → usage in resources/data sources

### Example: Cross-Account Reference Flow

**Step 1: terraform.tfvars** (hardcoded values per environment)
```hcl
# dev/terraform.tfvars
utility_bucket          = "{org}-utility-terraform-state-us-east-1-{utility-account-id}"
utility_role_arn        = "arn:aws:iam::{utility-account-id}:role/{org}-utility-assume-role"
utility_region          = "us-east-1"
utility_account         = "{utility-account-id}"

environment_bucket      = "{org}-dev-terraform-state-us-east-1-{dev-account-id}"
```

**Step 2: variables.tf** (declare inputs)
```hcl
# environment/variables.tf
variable "utility_bucket" {
  type    = string
  default = null
}

variable "utility_role_arn" {
  type    = string
  default = null
}

variable "utility_region" {
  type    = string
  default = null
}
```

**Step 3: locals.tf** (construct references)
```hcl
# environment/locals.tf
locals {
  utility_bucket   = var.utility_bucket
  utility_region   = var.utility_region
  utility_role_arn = var.utility_role_arn

  # Extract values from remote state
  cluster_config = {
    eks_cluster_oidc_issuer_url = data.terraform_remote_state.utility.outputs.eks_cluster_oidc_issuer_url
    eks_cluster_name            = data.terraform_remote_state.utility.outputs.eks_cluster_name
  }
}
```

**Step 4: backend.tf** (use in remote state config)
```hcl
# environment/backend.tf
data "terraform_remote_state" "utility" {
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.utility_role_arn  # From locals!
    }
    bucket = local.utility_bucket
    key    = "terraform.tfstate"
    region = local.utility_region
  }
}
```

### Manual Configuration Management

**Critical insight**: Account IDs, role ARNs, and bucket names are **manually managed**:
- Set once when accounts/roles are created
- Hardcoded in git-committed tfvars files
- Must be updated manually if roles or accounts change
- This is NOT dynamic discovery—it's explicit configuration

## Decentralized Permissions Pattern

### NEW Pattern: Applications Own Their IAM

**Problem with centralized approach**:
```hcl
# ❌ Anti-pattern: infrastructure/environment/{org}-environment-tools/environment/services.tf
locals {
  service_policy = {
    app-one     = data.aws_iam_policy_document.app_one.json
    app-two     = data.aws_iam_policy_document.app_two.json
    app-three   = data.aws_iam_policy_document.app_three.json
    # Must add every app here before deploying! (chicken-and-egg)
  }
}

resource "aws_iam_policy" "service_policy" {
  for_each = local.service_policy
  policy   = local.service_policy[each.key]  # Lookup fails if app not in map
}
```

**Solution with decentralized approach**:
```hcl
# ✅ Correct: applications/{app}/environment/iam.tf
data "aws_iam_policy_document" "app_policy" {
  statement {
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.app_bucket.arn}/*"]
  }
  # ... app-specific permissions
}

resource "aws_iam_policy" "app_policy" {
  name   = "{app}-policy-${var.environment}"
  policy = data.aws_iam_policy_document.app_policy.json
}

module "app_service_role" {
  source = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"

  create_role = true
  role_name   = "{app}-${var.environment}"

  # Get OIDC issuer from environment layer (platform provides primitives)
  provider_url = data.terraform_remote_state.environment.outputs.eks_cluster_oidc_issuer_url

  role_policy_arns = [aws_iam_policy.app_policy.arn]

  oidc_fully_qualified_subjects = [
    "system:serviceaccount:{namespace}:{app}-sa"
  ]
}

output "app_role_arn" {
  value = module.app_service_role.iam_role_arn
}
```

### Platform Provides Primitives, Not Per-App Roles

**Platform layer exports**:
- `eks_cluster_oidc_issuer_url` (required for IRSA)
- `vpc_id`, `subnet_ids` (networking primitives)
- `aurora_cluster_endpoint` (if shared database)
- `region`, `account_id` (account primitives)

**Platform layer does NOT export**:
- ~~`service_account_roles_arns["app-name"]`~~ (no per-app knowledge)

**Applications create their own**:
- IAM policies (app-specific permissions)
- IAM roles (OIDC-assumable for EKS service accounts)
- S3 buckets, SQS queues, DynamoDB tables
- OpenSearch clusters, Redis clusters

For detailed examples, see `references/iam-decentralization.md`.

## Cross-Account Access Mechanics

### Multi-Account Design

**Typical account structure**:
- **Utility account** ({utility-account-id}): Hosts shared EKS, VPC, Aurora
- **Dev account** ({dev-account-id}): Dev environment infrastructure
- **QA account** ({qa-account-id}): QA environment infrastructure
- **Prod account** ({prod-account-id}): Prod environment infrastructure
- **DR account** ({dr-account-id}): Disaster recovery infrastructure

### IAM Role Creation for Cross-Account Access

**In Utility account** (create assumable role):
```hcl
# infrastructure/utility/{org}-utility/environment/cross_account.tf
data "aws_iam_policy_document" "utility_state_access" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      "arn:aws:s3:::{org}-utility-terraform-state-*",
      "arn:aws:s3:::{org}-utility-terraform-state-*/*"
    ]
  }
  statement {
    actions = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:DeleteItem"]
    resources = ["arn:aws:dynamodb:*:*:table/{org}-utility-lock-table-*"]
  }
}

resource "aws_iam_policy" "utility_state_access" {
  name   = "{org}-utility-state-access"
  policy = data.aws_iam_policy_document.utility_state_access.json
}

data "aws_iam_policy_document" "utility_assume_policy" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::{dev-account-id}:root",
        "arn:aws:iam::{qa-account-id}:root",
        "arn:aws:iam::{prod-account-id}:root"
      ]
    }
  }
}

resource "aws_iam_role" "utility_cross_account" {
  name               = "{org}-utility-cross-account-access"
  assume_role_policy = data.aws_iam_policy_document.utility_assume_policy.json
}

resource "aws_iam_role_policy_attachment" "utility_cross_account" {
  role       = aws_iam_role.utility_cross_account.name
  policy_arn = aws_iam_policy.utility_state_access.arn
}

output "cross_account_role_arn" {
  value = aws_iam_role.utility_cross_account.arn
}
```

### Referencing Cross-Account Role ARNs

**In Environment account tfvars** (hardcode role ARN):
```hcl
# infrastructure/environment/{org}-environment/dev/terraform.tfvars
utility_role_arn = "arn:aws:iam::{utility-account-id}:role/{org}-utility-cross-account-access"
utility_bucket   = "{org}-utility-terraform-state-us-east-1-{utility-account-id}"
```

**In Environment locals** (pass through):
```hcl
# infrastructure/environment/{org}-environment/environment/locals.tf
locals {
  utility_role_arn = var.utility_role_arn
  utility_bucket   = var.utility_bucket
}
```

**In Environment backend** (use for state access):
```hcl
# infrastructure/environment/{org}-environment/environment/backend.tf
data "terraform_remote_state" "utility" {
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.utility_role_arn
    }
    bucket = local.utility_bucket
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}
```

## Outputs Chain

### What Each Layer Exports

**DR Layer**:
```hcl
output "vpc_id" { ... }
output "vpc_cidr" { ... }
output "private_route_table_ids" { ... }
output "dr_role_arn" { ... }
```

**Utility Layer**:
```hcl
output "eks_cluster_oidc_issuer_url" { ... }  # For OIDC-assumable roles
output "vpc_id" { ... }
output "vpc_cidr" { ... }
output "private_subnet_ids" { ... }
output "aurora_cluster_endpoint" { ... }
output "vault_kms_key_id" { ... }
output "public_domain" { ... }
```

**Environment Layer**:
```hcl
output "vpc_id" { ... }
output "vpc_cidr" { ... }
output "eks_cluster_endpoint" { ... }
output "eks_cluster_oidc_issuer_url" { ... }
output "aurora_cluster_endpoint" { ... }
output "rds_record_set_writer" { ... }
output "internal_domain_name" { ... }
```

**Application Layer**:
```hcl
output "app_role_arn" { ... }
output "app_bucket_id" { ... }
output "opensearch_endpoint" { ... }
output "redis_endpoint" { ... }
```

### Structuring Outputs for Consumption

**Pattern**: Group related outputs into nested objects:

```hcl
# environment/outputs.tf
output "vpc_config" {
  value = {
    vpc_id              = aws_vpc.main.id
    vpc_cidr            = aws_vpc.main.cidr_block
    private_subnet_ids  = aws_subnet.private[*].id
    availability_zones  = data.aws_availability_zones.available.names
  }
}

output "cluster_config" {
  value = {
    eks_cluster_name            = aws_eks_cluster.main.name
    eks_cluster_endpoint        = aws_eks_cluster.main.endpoint
    eks_cluster_oidc_issuer_url = aws_eks_cluster.main.identity[0].oidc[0].issuer
    eks_admin_role_arn          = aws_iam_role.eks_admin.arn
  }
}
```

**Consumption in downstream layer**:
```hcl
# environment/locals.tf
locals {
  vpc_config = {
    vpc_id             = data.terraform_remote_state.environment.outputs.vpc_config.vpc_id
    private_subnet_ids = data.terraform_remote_state.environment.outputs.vpc_config.private_subnet_ids
  }

  cluster_oidc_issuer = data.terraform_remote_state.environment.outputs.cluster_config.eks_cluster_oidc_issuer_url
}
```

## Common Patterns

### Locals Extract and Restructure Remote State

**Pattern**: Use locals to extract remote state outputs and restructure for component usage:

```hcl
# environment/locals.tf
locals {
  # Basic values
  region     = data.aws_region.current.id
  account_id = data.aws_caller_identity.current.account_id

  # From remote state - utility layer
  utility_vpc_config = {
    vpc_id             = data.terraform_remote_state.utility.outputs.vpc_id
    private_subnet_ids = data.terraform_remote_state.utility.outputs.private_subnet_ids
  }

  # From remote state - environment layer
  eks_cluster_config = {
    cluster_name        = data.terraform_remote_state.environment.outputs.eks_cluster_name
    oidc_issuer_url     = data.terraform_remote_state.environment.outputs.eks_cluster_oidc_issuer_url
  }

  # Computed values
  tags = {
    Project     = "{org}"
    Environment = var.environment
    Terraform   = "managed"
    Component   = "{component-name}"
  }
}
```

### Naming Conventions Across Layers

**Resources**: `{org}-{component}-{environment}-{random-suffix}`
**S3 buckets**: `{org}-{component}-{environment}-{account}-{region}-{random}`
**IAM roles**: `{component}-{service}-{environment}`
**State buckets**: `{org}-{env}-terraform-state-{region}-{account}`
**State keys**: `{layer}/terraform.tfstate`

### Module Structure Within Components

```
{component}/
├── environment/
│   ├── main.tf           (primary resources)
│   ├── backend.tf        (minimal backend + remote state)
│   ├── providers.tf
│   ├── variables.tf
│   ├── locals.tf
│   ├── outputs.tf
│   ├── vpc.tf            (resource grouping by domain)
│   ├── eks.tf
│   ├── rds.tf
│   └── modules/          (component-specific modules)
│       ├── custom-module-one/
│       └── custom-module-two/
└── {env}/
    └── terragrunt.hcl
```

### Tracking Resource Dependencies When Making Changes

**Critical**: When modifying Terraform resources (renaming, changing types, or refactoring), you MUST track and update ALL references to those resources across the codebase.

#### What to Track

When changing a resource, search for and update:

1. **Direct resource references** in other resources:
   ```hcl
   # If changing: resource "kubernetes_secret" "this"
   # Find and update all: kubernetes_secret.this
   kubernetes_ca_cert = data.kubernetes_secret.this.data["ca.crt"]  # ← Update this
   ```

2. **Data source references** to the same resource type:
   ```hcl
   # If changing: resource "kubernetes_secret" "this"
   # Update corresponding: data "kubernetes_secret" "this"
   data "kubernetes_secret" "this" {
     metadata {
       name = kubernetes_secret.this.metadata.0.name  # ← Update both
     }
   }
   ```

3. **Outputs** that expose the resource:
   ```hcl
   # If resource name/type changed, update output references
   output "secret_name" {
     value = kubernetes_secret.this.metadata[0].name  # ← Update this
   }
   ```

4. **Module references** if the resource is passed to modules:
   ```hcl
   module "app" {
     secret_arn = aws_secretsmanager_secret.this.arn  # ← Update this
   }
   ```

5. **Remote state consumers** in downstream layers:
   ```hcl
   # If output name changed, downstream layers break
   # Check what outputs are consumed via remote state
   data.terraform_remote_state.environment.outputs.secret_arn
   ```

#### Search Strategy

Use systematic search to find all references:

```bash
# Find all references to a resource name
grep -r "kubernetes_secret\.this" .

# Find all references to a specific resource type
grep -r "kubernetes_secret\"" .

# Check outputs that might be consumed downstream
grep -r "output.*secret" .
```

#### Example: Renaming a Resource

**Scenario**: Migrating `resource "kubernetes_secret"` to `resource "kubernetes_secret_v1"`

**Steps**:
1. Update resource declaration: `resource "kubernetes_secret_v1" "this"`
2. Update data source declaration: `data "kubernetes_secret_v1" "this"`
3. Update data source references: `kubernetes_secret.this` → `kubernetes_secret_v1.this`
4. Update all resource attribute references: `data.kubernetes_secret.this.data["token"]` → `data.kubernetes_secret_v1.this.data["token"]`
5. Verify outputs don't expose old resource references
6. Check downstream layers consuming outputs

#### Common Failure Pattern

**Symptom**: `Error: Reference to undeclared resource`
```
Error: Reference to undeclared resource
on .terraform/modules/app/main.tf line 84:
  kubernetes_ca_cert = data.kubernetes_secret.this.data["ca.crt"]

A data resource "kubernetes_secret" "this" has not been declared
```

**Cause**: Resource was renamed but not all references were updated.

**Fix**: Search for all occurrences of the old resource name and update systematically.

#### Prevention

- **Before making changes**: Search for all current references
- **After making changes**: Re-search to verify all references updated
- **Use IDE refactoring**: If available, use IDE's rename/refactor feature for better coverage
- **Test incrementally**: Run `terraform plan` after each logical change to catch reference errors early

## Decision Trees

### Where Does New Infrastructure Go?

```
START: New infrastructure needed
│
├─ Is this for disaster recovery or VPC peering?
│  └─ YES → DR Layer (infrastructure/btp-disaster-recovery)
│
├─ Is this shared across ALL environments (dev/qa/prod)?
│  └─ YES → Utility Layer (infrastructure/utility/{component})
│
├─ Is this per-environment but shared across applications?
│  └─ YES → Environment Layer (infrastructure/environment/{component})
│
└─ Is this specific to one application/monorepo?
   └─ YES → Application Layer (applications/{app}/environment)
```

### When to Create a New Component vs Add to Existing?

```
START: Need to add infrastructure
│
├─ Does this logically belong with existing resources?
│  ├─ YES → Add to existing component (new .tf file)
│  └─ NO → Continue
│
├─ Will this have a different deployment lifecycle?
│  ├─ YES → Create new component
│  └─ NO → Continue
│
├─ Will this have different RBAC/ownership?
│  ├─ YES → Create new component
│  └─ NO → Continue
│
└─ Will the state file become too large (>100 resources)?
   ├─ YES → Create new component
   └─ NO → Add to existing component
```

### When to Create a New Monorepo?

```
START: Considering new monorepo for application
│
├─ Is this a distinct system with independent lifecycle?
│  └─ YES → Create new monorepo
│
├─ Does this have different team ownership?
│  └─ YES → Create new monorepo
│
├─ Does this have significantly different tech stack?
│  └─ YES → Create new monorepo
│
└─ Is this a new microservice in existing system?
   └─ NO → Add to existing monorepo (new service directory)
```

### How to Add a New Environment?

```
START: Need to deploy to new environment (e.g., staging)
│
1. Create new AWS account (if needed)
│
2. Create Terragrunt wrapper: {component}/staging/
│  ├─ terragrunt.hcl (copy from dev, update identifiers)
│  └─ terraform.tfvars (set account-specific values)
│
3. Update utility role trust policy (if cross-account)
│
4. Set up cross-account role ARN in staging/terraform.tfvars
│
5. Run terragrunt init && terragrunt apply
```

## Anti-Patterns to Avoid

### ❌ Centralized Per-App Configuration

**Problem**: Platform layer has hardcoded map of all applications:
```hcl
# infrastructure/environment/{org}-environment-tools/environment/services.tf
locals {
  service_policy = {
    app-one   = data.aws_iam_policy_document.app_one.json
    app-two   = data.aws_iam_policy_document.app_two.json
    app-three = data.aws_iam_policy_document.app_three.json
  }
}
```
**Why bad**: Chicken-and-egg problem. Must add app to central map before deploying app.
**Solution**: Applications own their IAM in `{app}/environment/iam.tf`.

### ❌ Tight Coupling Between Layers

**Problem**: Environment layer creates app-specific resources:
```hcl
# infrastructure/environment/{org}-environment/environment/app_resources.tf
resource "aws_s3_bucket" "app_one_uploads" { ... }
resource "aws_s3_bucket" "app_two_uploads" { ... }
```
**Why bad**: Platform must know about every application. Breaks separation of concerns.
**Solution**: Applications create their own buckets in `{app}/environment/storage.tf`.

### ❌ Platform Knowing About Specific Applications

**Problem**: Platform exports per-app resources:
```hcl
output "app_buckets" {
  value = {
    app-one = aws_s3_bucket.app_one.id
    app-two = aws_s3_bucket.app_two.id
  }
}
```
**Why bad**: Platform coupled to application names. Can't add apps without platform changes.
**Solution**: Platform exports primitives (vpc_id, oidc_issuer), not app-specific resources.

### ❌ Hardcoding Values That Should Come From Remote State

**Problem**: Hardcoding values that exist in upstream layers:
```hcl
locals {
  vpc_id = "vpc-0abc123def456"  # ❌ Hardcoded
}
```
**Why bad**: Brittle. Breaks if upstream VPC changes.
**Solution**: Pull from remote state:
```hcl
locals {
  vpc_id = data.terraform_remote_state.environment.outputs.vpc_id
}
```

### ❌ Creating New State Buckets Instead of Using Keys

**Problem**: Creating new S3 bucket for each component:
```hcl
backend "s3" {
  bucket = "{org}-{component}-terraform-state-{account}"  # ❌ New bucket per component
}
```
**Why bad**: Bucket proliferation. Management overhead. Cost.
**Solution**: Use shared bucket with unique keys:
```hcl
bucket = "{org}-{env}-terraform-state-{account}"
key    = "{component}/terraform.tfstate"  # ✅ Unique key, shared bucket
```

### ❌ Putting Backend Config in Terraform Instead of Terragrunt

**Problem**: Hardcoding backend config in Terraform backend.tf:
```hcl
terraform {
  backend "s3" {
    bucket = "{org}-dev-terraform-state-us-east-1-{account}"  # ❌ Hardcoded
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}
```
**Why bad**: Not environment-agnostic. Must change Terraform code for each environment.
**Solution**: Minimal Terraform backend, Terragrunt configures:
```hcl
# environment/backend.tf
terraform {
  backend "s3" {
    encrypt = true  # ✅ Minimal config
  }
}

# dev/terragrunt.hcl
remote_state {
  backend = "s3"
  config = {
    bucket = "{org}-dev-terraform-state-us-east-1-${get_aws_account_id()}"
    key    = "core/terraform.tfstate"
    # ...
  }
}
```

## Additional Resources

For detailed code examples and templates, see:
- `references/terragrunt-pattern.md` - Terragrunt configuration templates
- `references/backend-configuration.md` - Backend setup patterns
- `references/layer-templates.md` - Complete templates for each layer
- `references/iam-decentralization.md` - Application-owned IAM patterns
- `references/cross-account-pattern.md` - Cross-account access mechanics
- `references/monorepo-structure.md` - Setting up new monorepo infrastructure
