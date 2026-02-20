# Terragrunt Pattern Reference

This document provides complete examples and templates for the Terragrunt wrapper pattern used in multi-environment infrastructure.

## Complete Directory Structure Example

```
infrastructure/environment/{org}-cloud-environment/
├── environment/                    ← Terraform code (reusable)
│   ├── backend.tf
│   ├── providers.tf
│   ├── variables.tf
│   ├── locals.tf
│   ├── outputs.tf
│   ├── vpc.tf
│   ├── eks.tf
│   └── rds.tf
├── dev/                            ← Terragrunt wrapper for dev
│   ├── terragrunt.hcl
│   └── terraform.tfvars
├── qa/                             ← Terragrunt wrapper for qa
│   ├── terragrunt.hcl
│   └── terraform.tfvars
├── prod/                           ← Terragrunt wrapper for prod
│   ├── terragrunt.hcl
│   └── terraform.tfvars
└── README.md
```

## terragrunt.hcl Template

### Standard Pattern

```hcl
# dev/terragrunt.hcl

locals {
  # Organization identifier
  indentifier = "{org}"

  # Environment name
  environment = "dev"

  # Layer name for state key
  layer = "core"  # or "applications", "{app-name}", etc.

  # AWS region
  aws_region = "us-east-1"

  # Backend bucket naming
  backend_bucket = "${local.indentifier}-${local.environment}-terraform-state-${local.aws_region}-${get_aws_account_id()}"

  # DynamoDB lock table naming
  dynamodb_table = "${local.indentifier}-${local.environment}-lock-table-${local.aws_region}-${get_aws_account_id()}"
}

# Point to the Terraform code
terraform {
  source = "${get_parent_terragrunt_dir()}/..//environment///"
}

# Configure the S3 backend
remote_state {
  backend = "s3"

  config = {
    bucket         = local.backend_bucket
    dynamodb_table = local.dynamodb_table
    key            = "${local.layer}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
  }

  # Create backend resources if they don't exist
  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

# Generate provider configuration (optional, if you want Terragrunt to manage it)
generate "provider" {
  path      = "provider_override.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region = "${local.aws_region}"
}
EOF
}
```

### Utility Layer Pattern

```hcl
# utility/terragrunt.hcl

locals {
  indentifier    = "{org}-utility"
  environment    = "utility"
  aws_region     = "us-east-1"
  backend_bucket = "${local.indentifier}-terraform-state-${local.aws_region}-${get_aws_account_id()}"
  dynamodb_table = "${local.indentifier}-lock-table-${local.aws_region}-${get_aws_account_id()}"
}

terraform {
  source = "${get_parent_terragrunt_dir()}/..//environment///"
}

remote_state {
  backend = "s3"
  config = {
    bucket         = local.backend_bucket
    dynamodb_table = local.dynamodb_table
    key            = "terraform.tfstate"  # Simple key for utility
    region         = local.aws_region
    encrypt        = true
  }
}
```

### Application Layer Pattern

```hcl
# applications/{app}/development/terragrunt.hcl

locals {
  indentifier    = "{org}"
  environment    = "dev"
  layer          = "{app-name}"  # e.g., "cope", "services"
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
    key            = "${local.layer}/terraform.tfstate"  # App-specific key
    region         = local.aws_region
    encrypt        = true
  }
}
```

## terraform.tfvars Template

### Environment Layer tfvars

```hcl
# dev/terraform.tfvars

# Environment basics
project     = "{org}"
environment = "dev"
region      = "us-east-1"

# Cross-account references
utility_bucket          = "{org}-utility-terraform-state-us-east-1-{utility-account-id}"
utility_role_arn        = "arn:aws:iam::{utility-account-id}:role/{org}-utility-cross-account-access"
utility_env             = "utility"
utility_region          = "us-east-1"
utility_account         = "{utility-account-id}"

# DR references (if needed)
dr_bucket               = "{org}-dr-terraform-state-us-east-1-{dr-account-id}"
dr_role_arn             = "arn:aws:iam::{dr-account-id}:role/{org}-dr-cross-account-access"
dr_region               = "us-east-1"

# Environment-specific configuration
environment_bucket      = "{org}-dev-terraform-state-us-east-1-{dev-account-id}"

# Infrastructure configuration
vpc_cidr                = "10.0.0.0/16"
availability_zones      = ["us-east-1a", "us-east-1b", "us-east-1c"]

# Database configuration
db_instance_class       = "db.r5.large"
db_engine_version       = "14.7"

# EKS configuration
eks_version             = "1.27"
eks_node_instance_types = ["t3.large"]
```

### Application Layer tfvars

```hcl
# applications/{app}/development/terraform.tfvars

# Environment basics
project     = "{org}"
environment = "dev"
region      = "us-east-1"

# Environment bucket (same account)
environment_bucket      = "{org}-dev-terraform-state-us-east-1-{dev-account-id}"

# Utility references (cross-account)
utility_bucket          = "{org}-utility-terraform-state-us-east-1-{utility-account-id}"
utility_role_arn        = "arn:aws:iam::{utility-account-id}:role/{org}-utility-cross-account-access"
utility_region          = "us-east-1"

# Application-specific configuration
opensearch_instance_type = "r5.large.search"
opensearch_volume_size   = 100
opensearch_version       = "2.7"

redis_node_type          = "cache.r5.large"
redis_num_nodes          = 2
```

## Backend Bucket and Key Naming

### Bucket Naming Patterns

**Utility layer**:
```
{org}-utility-terraform-state-{region}-{account}
```

**Environment layer**:
```
{org}-{env}-terraform-state-{region}-{account}
```

**Examples**:
- `{org}-utility-terraform-state-us-east-1-123456789012`
- `{org}-dev-terraform-state-us-east-1-987654321098`
- `{org}-prod-terraform-state-us-east-1-567890123456`

### State Key Patterns

**Utility components**:
```
terraform.tfstate                    # Main utility infrastructure
tools/terraform.tfstate              # Utility tools
```

**Environment components**:
```
core/terraform.tfstate               # Core environment infrastructure
applications/terraform.tfstate       # Application tooling layer
public-gateway/terraform.tfstate     # Gateway component
```

**Application components**:
```
{app-name}/terraform.tfstate         # e.g., cope/terraform.tfstate
```

## DynamoDB Lock Table Naming

Pattern: `{org}-{env}-lock-table-{region}-{account}`

**Examples**:
- `{org}-utility-lock-table-us-east-1-123456789012`
- `{org}-dev-lock-table-us-east-1-987654321098`
- `{org}-prod-lock-table-us-east-1-567890123456`

## How Terragrunt Sources Terraform

```hcl
terraform {
  source = "${get_parent_terragrunt_dir()}/..//environment///"
}
```

**Breakdown**:
- `get_parent_terragrunt_dir()`: Returns the directory containing terragrunt.hcl
- `/../`: Go up one directory (from `dev/` to component root)
- `//environment///`: Terragrunt-specific syntax for Terraform module source
  - `//`: Signals start of Terraform module path
  - `///`: Signals end of Terraform module path (allows for query params)

**Example path resolution**:
```
Current: /repo/infrastructure/environment/{org}-environment/dev/terragrunt.hcl
Parent:  /repo/infrastructure/environment/{org}-environment/dev
Up one:  /repo/infrastructure/environment/{org}-environment
Source:  /repo/infrastructure/environment/{org}-environment/environment
```

## Environment-Specific Variations

### Development Environment

```hcl
# dev/terragrunt.hcl
locals {
  environment = "dev"
  # ... smaller instances, fewer replicas
}
```

```hcl
# dev/terraform.tfvars
db_instance_class = "db.t3.medium"
eks_node_instance_types = ["t3.medium"]
```

### Production Environment

```hcl
# prod/terragrunt.hcl
locals {
  indentifier = "{org}-active"  # Different identifier for prod
  environment = "prod"
}
```

```hcl
# prod/terraform.tfvars
db_instance_class = "db.r5.2xlarge"
eks_node_instance_types = ["m5.xlarge", "m5.2xlarge"]
multi_az = true
```

## Common Terragrunt Commands

```bash
# Navigate to environment directory
cd infrastructure/environment/{org}-environment/dev

# Initialize Terraform with Terragrunt
terragrunt init

# Plan changes
terragrunt plan

# Apply changes
terragrunt apply

# Destroy infrastructure
terragrunt destroy

# Validate Terraform code
terragrunt validate

# Show current state
terragrunt show

# Output values
terragrunt output

# Force unlock state (if locked)
terragrunt force-unlock <lock-id>
```

## Troubleshooting

### Backend Bucket Doesn't Exist

**Error**: `Error: Failed to get existing workspaces: S3 bucket does not exist.`

**Solution**: Create the backend bucket manually or use Terragrunt's auto-creation:
```bash
aws s3 mb s3://{org}-{env}-terraform-state-{region}-{account} --region us-east-1
```

### DynamoDB Table Doesn't Exist

**Error**: `Error: Error acquiring the state lock: dynamodb table not found`

**Solution**: Create the lock table:
```bash
aws dynamodb create-table \
  --table-name {org}-{env}-lock-table-us-east-1-{account} \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### Terragrunt Can't Find Terraform Code

**Error**: `Error: Terraform files not found`

**Solution**: Check the `source` path in terragrunt.hcl:
```bash
# From dev/ directory, should resolve to ../environment
ls ../environment/*.tf  # Should show Terraform files
```

### State File Key Conflicts

**Error**: `Error: state file already exists`

**Solution**: Each component/layer needs a unique key. Check:
```hcl
key = "${local.layer}/terraform.tfstate"  # Ensure layer is unique
```
