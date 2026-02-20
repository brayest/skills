# Backend Configuration Reference

This document explains the two-tier backend pattern and provides templates for backend configuration at each layer.

## Two-Tier Backend Architecture

### Tier 1: Terragrunt (Actual Configuration)

Terragrunt manages the S3 backend configuration via the `remote_state` block in `terragrunt.hcl`.

**Responsibilities**:
- Define S3 bucket name
- Define state key path
- Define DynamoDB lock table
- Configure encryption
- Inject configuration into Terraform

### Tier 2: Terraform (Minimal Declaration)

Terraform only declares the backend type in `backend.tf` with minimal config.

**Responsibilities**:
- Declare backend type (`s3`)
- Enable encryption
- Define remote state data sources

## Minimal Terraform backend.tf

### Standard Pattern

```hcl
# environment/backend.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    encrypt = true
  }
}
```

**Key point**: No bucket, key, or region specified here. Terragrunt injects these values.

## Remote State Data Sources

### Pattern: Consuming Upstream Layers

```hcl
# environment/backend.tf (continued)

# Same-account access
data "terraform_remote_state" "environment" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "core/terraform.tfstate"
    region = local.region
  }
}

# Cross-account access with assume_role
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

### Variable Flow for Remote State

**Step 1: terraform.tfvars (hardcoded)**
```hcl
# dev/terraform.tfvars
utility_bucket   = "{org}-utility-terraform-state-us-east-1-{account}"
utility_role_arn = "arn:aws:iam::{account}:role/{org}-utility-assume"
utility_region   = "us-east-1"
```

**Step 2: variables.tf (declare)**
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

**Step 3: locals.tf (construct)**
```hcl
# environment/locals.tf
locals {
  utility_bucket   = var.utility_bucket
  utility_role_arn = var.utility_role_arn
  utility_region   = var.utility_region
}
```

**Step 4: backend.tf (use)**
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

## Complete backend.tf Templates by Layer

### DR Layer

```hcl
# infrastructure/btp-disaster-recovery/environment/backend.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    encrypt = true
  }
}

# No remote state dependencies - DR is the foundation
```

### Utility Layer

```hcl
# infrastructure/utility/{org}-utility/environment/backend.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    encrypt = true
  }
}

# Depends on DR (cross-account)
data "terraform_remote_state" "dr" {
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.dr_role_arn
    }
    bucket = local.dr_bucket
    key    = "disaster_recovery/terraform.tfstate"
    region = local.dr_region
  }
}
```

### Environment Layer

```hcl
# infrastructure/environment/{org}-environment/environment/backend.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    encrypt = true
  }
}

# Depends on Utility (cross-account)
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

# Depends on Utility Tools (cross-account)
data "terraform_remote_state" "utility_tools" {
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.utility_role_arn  # Same role
    }
    bucket = local.utility_bucket          # Same bucket
    key    = "tools/terraform.tfstate"    # Different key
    region = local.utility_region
  }
}

# Depends on DR (cross-account)
data "terraform_remote_state" "dr" {
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.dr_role_arn
    }
    bucket = local.dr_bucket
    key    = "disaster_recovery/terraform.tfstate"
    region = local.dr_region
  }
}
```

### Environment Tools Layer

```hcl
# infrastructure/environment/{org}-environment-tools/environment/backend.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    encrypt = true
  }
}

# Depends on Environment Core (same account)
data "terraform_remote_state" "environment" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "core/terraform.tfstate"
    region = local.region
  }
}

# Depends on Utility (cross-account)
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

### Application Layer

```hcl
# applications/{app}/environment/backend.tf

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    encrypt = true
  }
}

# Depends on Environment Core (same account)
data "terraform_remote_state" "environment" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "core/terraform.tfstate"
    region = local.region
  }
}

# Depends on Environment Tools (same account)
data "terraform_remote_state" "environment_tools" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "applications/terraform.tfstate"
    region = local.region
  }
}

# Depends on Utility (cross-account)
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

## Inline assume_role vs Provider Aliases

### Use Inline assume_role (Recommended)

**For remote state access**:
```hcl
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

**Benefits**:
- Self-contained
- No provider alias required
- Works independently of provider configuration

### Provider Aliases for Resources (Not State)

**Use provider aliases for cross-account resource creation**:
```hcl
# providers.tf
provider "aws" {
  region = var.region  # Primary account
}

provider "aws" {
  alias  = "utility"
  region = var.region
  assume_role {
    role_arn = local.utility_role_arn
  }
}

# Use in resources
resource "aws_s3_bucket" "utility_bucket" {
  provider = aws.utility
  bucket   = "my-bucket"
}
```

**Don't use for remote state** - provider aliases don't work with data source backend configs.

## State Locking with DynamoDB

### Automatic Lock Table Usage

Terragrunt automatically uses the DynamoDB table specified in `remote_state` config:

```hcl
# terragrunt.hcl
remote_state {
  backend = "s3"
  config = {
    bucket         = local.backend_bucket
    dynamodb_table = local.dynamodb_table  # Enables state locking
    # ...
  }
}
```

### Lock Table Schema

**Required attributes**:
- `LockID` (String, Primary Key)

**Example creation**:
```bash
aws dynamodb create-table \
  --table-name {org}-{env}-lock-table-{region}-{account} \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### Handling Lock Errors

**Force unlock** (use cautiously):
```bash
terragrunt force-unlock <lock-id>
```

**Check current locks**:
```bash
aws dynamodb scan \
  --table-name {org}-{env}-lock-table-{region}-{account} \
  --region us-east-1
```

## Common Patterns

### Multiple Remote States from Same Bucket

```hcl
# Different keys, same bucket
data "terraform_remote_state" "core" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "core/terraform.tfstate"
    region = local.region
  }
}

data "terraform_remote_state" "tools" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "applications/terraform.tfstate"
    region = local.region
  }
}
```

### Conditional Remote State

```hcl
# Only read DR state in certain environments
data "terraform_remote_state" "dr" {
  count   = var.enable_dr_integration ? 1 : 0
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.dr_role_arn
    }
    bucket = local.dr_bucket
    key    = "disaster_recovery/terraform.tfstate"
    region = local.dr_region
  }
}

# Usage with conditional
locals {
  dr_vpc_id = var.enable_dr_integration ? data.terraform_remote_state.dr[0].outputs.vpc_id : null
}
```

## Troubleshooting

### Error: Backend configuration changed

**Symptom**: `Error: Backend configuration changed`

**Cause**: Terragrunt injected different backend config than what Terraform was initialized with.

**Solution**:
```bash
terragrunt init -reconfigure
```

### Error: Failed to get existing workspaces

**Symptom**: `Error: Failed to get existing workspaces: S3 bucket does not exist`

**Cause**: Backend bucket doesn't exist yet.

**Solution**: Create bucket first:
```bash
aws s3 mb s3://{org}-{env}-terraform-state-{region}-{account} --region us-east-1
```

### Error: Access Denied to S3 bucket

**Symptom**: `Error: AccessDenied: Access Denied` when reading remote state

**Cause**: Cross-account role doesn't have permissions or doesn't exist.

**Solutions**:
1. Verify role ARN is correct in tfvars
2. Verify role exists in target account
3. Verify role trust policy allows source account
4. Verify role has S3 GetObject permission on state bucket

### Error: Error locking state

**Symptom**: `Error: Error locking state: ConditionalCheckFailedException`

**Cause**: State is already locked (possibly from interrupted run).

**Solution**:
```bash
# Check who has the lock
aws dynamodb get-item \
  --table-name {org}-{env}-lock-table-{region}-{account} \
  --key '{"LockID": {"S": "{bucket}/{key}-md5"}}'

# Force unlock if safe
terragrunt force-unlock <lock-id>
```
