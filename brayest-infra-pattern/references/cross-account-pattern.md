# Cross-Account Pattern Reference

This document explains the multi-account architecture and cross-account IAM role patterns for state access.

## Multi-Account Architecture

### Account Structure

```
┌─────────────────────────────────────────────────────────────┐
│  Utility Account (e.g., 638362541257)                      │
│  - EKS cluster (shared across all environments)            │
│  - VPC                                                      │
│  - Aurora (shared database)                                │
│  - Vault                                                    │
│  - CI/CD runners                                           │
│  - State bucket: {org}-utility-terraform-state-*           │
└─────────────────────────────────────────────────────────────┘
                         ↑
                         | (cross-account assume_role)
                         |
         ┌───────────────┼───────────────┬────────────────┐
         │               │               │                │
┌────────▼────┐ ┌────────▼────┐ ┌────────▼────┐ ┌────────▼────┐
│  Dev        │ │  QA         │ │  Prod       │ │  DR         │
│  Account    │ │  Account    │ │  Account    │ │  Account    │
│  (551...)   │ │  (159...)   │ │  (691...)   │ │  (891...)   │
│             │ │             │ │             │ │             │
│  State:     │ │  State:     │ │  State:     │ │  State:     │
│  {org}-dev  │ │  {org}-qa   │ │  {org}-prod │ │  {org}-dr   │
│  -terraform │ │  -terraform │ │  -terraform │ │  -terraform │
│  -state-*   │ │  -state-*   │ │  -state-*   │ │  -state-*   │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

### Why Multi-Account?

**Benefits**:
1. **Security isolation**: Dev mistakes can't affect prod
2. **Blast radius**: Security breach contained to one account
3. **Cost allocation**: Clear cost attribution per environment
4. **Compliance**: Separate audit trails per environment
5. **RBAC**: Different IAM policies per environment

**Shared utility account**:
- EKS cluster shared across environments (cost efficiency)
- One Vault instance for secrets management
- CI/CD infrastructure centralized

## Cross-Account IAM Role Creation

### In Utility Account: Create Assumable Role

```hcl
# infrastructure/utility/{org}-utility/environment/cross_account_roles.tf

# IAM policy for state bucket access
data "aws_iam_policy_document" "utility_state_access" {
  statement {
    sid = "S3StateAccess"
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
    sid = "DynamoDBLockAccess"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:DeleteItem"
    ]
    resources = [
      "arn:aws:dynamodb:*:*:table/{org}-utility-lock-table-*"
    ]
  }
}

resource "aws_iam_policy" "utility_state_access" {
  name        = "{org}-utility-state-access"
  description = "Allow cross-account access to utility Terraform state"
  policy      = data.aws_iam_policy_document.utility_state_access.json
}

# Trust policy - who can assume this role
data "aws_iam_policy_document" "utility_cross_account_assume" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRole"]
    
    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::{dev-account-id}:root",      # Dev account
        "arn:aws:iam::{qa-account-id}:root",       # QA account
        "arn:aws:iam::{prod-account-id}:root",     # Prod account
        "arn:aws:iam::{utility-account-id}:root"   # Self (utility can assume itself)
      ]
    }
  }
}

resource "aws_iam_role" "utility_cross_account" {
  name               = "{org}-utility-cross-account-access"
  description        = "Role for environment accounts to read utility Terraform state"
  assume_role_policy = data.aws_iam_policy_document.utility_cross_account_assume.json
  
  tags = {
    Purpose = "cross-account-terraform-state-access"
  }
}

resource "aws_iam_role_policy_attachment" "utility_cross_account" {
  role       = aws_iam_role.utility_cross_account.name
  policy_arn = aws_iam_policy.utility_state_access.arn
}

# Export the role ARN
output "cross_account_role_arn" {
  value       = aws_iam_role.utility_cross_account.arn
  description = "ARN of role for cross-account state access"
}
```

### In Environment Account: Reference Role ARN

```hcl
# infrastructure/environment/{org}-environment/dev/terraform.tfvars

# Hardcode the role ARN after utility stack is created
utility_role_arn = "arn:aws:iam::{utility-account-id}:role/{org}-utility-cross-account-access"
utility_bucket   = "{org}-utility-terraform-state-us-east-1-{utility-account-id}"
utility_region   = "us-east-1"
utility_account  = "{utility-account-id}"
```

## Using Cross-Account Roles for Remote State

### In backend.tf (Environment Layer)

```hcl
# infrastructure/environment/{org}-environment/environment/backend.tf

data "terraform_remote_state" "utility" {
  backend = "s3"
  config = {
    # Inline assume_role configuration
    assume_role = {
      role_arn = local.utility_role_arn
    }
    bucket = local.utility_bucket
    key    = "terraform.tfstate"
    region = local.utility_region
  }
}
```

### Variable Flow

**Step 1: tfvars** (hardcoded per environment)
```hcl
# dev/terraform.tfvars
utility_role_arn = "arn:aws:iam::638362541257:role/{org}-utility-assume"
```

**Step 2: variables.tf**
```hcl
# environment/variables.tf
variable "utility_role_arn" {
  type = string
}
```

**Step 3: locals.tf**
```hcl
# environment/locals.tf
locals {
  utility_role_arn = var.utility_role_arn
}
```

**Step 4: backend.tf** (use in remote state)
```hcl
# environment/backend.tf
data "terraform_remote_state" "utility" {
  backend = "s3"
  config = {
    assume_role = {
      role_arn = local.utility_role_arn  # From locals
    }
    # ...
  }
}
```

## DR Account Cross-Account Pattern

### In DR Account: Create Assumable Role

```hcl
# infrastructure/btp-disaster-recovery/environment/dr_account.tf

data "aws_iam_policy_document" "dr_state_access" {
  statement {
    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      "arn:aws:s3:::*-dr-terraform-state-*",
      "arn:aws:s3:::*-dr-terraform-state-*/*"
    ]
  }

  statement {
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:DeleteItem"
    ]
    resources = ["arn:aws:dynamodb:*:*:table/*-dr-lock-table-*"]
  }
}

resource "aws_iam_policy" "dr_state_access" {
  name   = "{org}-dr-state-access"
  policy = data.aws_iam_policy_document.dr_state_access.json
}

data "aws_iam_policy_document" "dr_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type = "AWS"
      identifiers = [
        "arn:aws:iam::{utility-account-id}:root",
        "arn:aws:iam::{dev-account-id}:root",
        "arn:aws:iam::{qa-account-id}:root",
        "arn:aws:iam::{prod-account-id}:root"
      ]
    }
  }
}

resource "aws_iam_role" "dr_role" {
  name               = "{org}-dr-role-dr"
  assume_role_policy = data.aws_iam_policy_document.dr_assume.json
}

resource "aws_iam_role_policy_attachment" "dr_role" {
  role       = aws_iam_role.dr_role.name
  policy_arn = aws_iam_policy.dr_state_access.arn
}

output "dr_role" {
  value = aws_iam_role.dr_role.arn
}
```

### In Utility/Environment: Reference DR Role

```hcl
# infrastructure/utility/{org}-utility/utility/terraform.tfvars

dr_role_arn = "arn:aws:iam::{dr-account-id}:role/{org}-dr-role-dr"
dr_bucket   = "{org}-dr-terraform-state-us-east-1-{dr-account-id}"
dr_region   = "us-east-1"
```

## Provider Aliases for Cross-Account Resources

### When to Use Provider Aliases

**Use inline `assume_role` in data sources** for remote state (recommended):
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

**Use provider aliases for resource creation** in other accounts:
```hcl
# providers.tf
provider "aws" {
  region = var.region  # Primary account
}

provider "aws" {
  alias  = "utility"
  region = var.utility_region
  assume_role {
    role_arn = local.utility_role_arn
  }
}

# Use in resources
resource "aws_s3_bucket" "cross_account_bucket" {
  provider = aws.utility  # Create in utility account
  bucket   = "my-cross-account-bucket"
}
```

## Account ID Management

### Hardcoded in tfvars

```hcl
# dev/terraform.tfvars
utility_account = "638362541257"
dr_account      = "891612552075"

# prod/terraform.tfvars
utility_account = "638362541257"  # Same utility account
dr_account      = "891612552075"  # Same DR account
```

### Dynamic Account ID Retrieval

```hcl
# environment/locals.tf
data "aws_caller_identity" "current" {}

locals {
  current_account_id = data.aws_caller_identity.current.account_id
  
  # Utility account is hardcoded from variables
  utility_account = var.utility_account
}
```

## Security Best Practices

### 1. Principle of Least Privilege

**Read-only state access**:
```hcl
actions = [
  "s3:GetObject",      # Read state files
  "s3:ListBucket"      # List state files
  # NOT "s3:PutObject" - no write access
]
```

### 2. Restrict Role Assumption

**Specific principals only**:
```hcl
principals {
  type = "AWS"
  identifiers = [
    "arn:aws:iam::{dev-account-id}:root",
    # NOT "*" - never allow any account
  ]
}
```

### 3. Add External ID (Optional)

```hcl
data "aws_iam_policy_document" "assume_role_with_external_id" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::{account-id}:root"]
    }
    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = ["unique-external-id-12345"]
    }
  }
}
```

### 4. Session Duration Limits

```hcl
resource "aws_iam_role" "cross_account" {
  name               = "{org}-cross-account"
  max_session_duration = 3600  # 1 hour max
  assume_role_policy = data.aws_iam_policy_document.assume.json
}
```

## Troubleshooting

### Error: AccessDenied when assuming role

**Check 1: Role exists in target account**
```bash
aws iam get-role --role-name {org}-utility-cross-account-access --profile utility
```

**Check 2: Trust policy allows source account**
```bash
aws iam get-role --role-name {org}-utility-cross-account-access --profile utility \
  | jq '.Role.AssumeRolePolicyDocument.Statement[].Principal.AWS'
```

**Check 3: Source account has permission to assume**
```bash
# In source account, check if you can assume the role
aws sts assume-role \
  --role-arn arn:aws:iam::{utility-account}:role/{org}-utility-cross-account-access \
  --role-session-name test-session
```

### Error: Role ARN is incorrect in tfvars

**Symptom**: `Error: InvalidParameter: 1 validation error(s) found. - role_arn`

**Fix**: Verify role ARN format in tfvars:
```hcl
# Correct format
utility_role_arn = "arn:aws:iam::123456789012:role/role-name"

# Wrong formats
utility_role_arn = "arn:aws:sts::123456789012:role/role-name"  # ❌ sts, not iam
utility_role_arn = "arn:aws:iam::123456789012:policy/role-name"  # ❌ policy, not role
```

### Error: State bucket in different account

**Symptom**: `Error: Failed to save state: AccessDenied`

**Cause**: Trying to write state to cross-account bucket without permission.

**Fix**: Each account has its own state bucket. Use assume_role only for reading remote state, not for backend configuration.

## Complete Multi-Account Setup Example

### 1. Create Utility Account Infrastructure

```bash
cd infrastructure/utility/{org}-utility/utility
terragrunt apply
# Note the cross_account_role_arn output
```

### 2. Update Environment tfvars with Role ARN

```hcl
# infrastructure/environment/{org}-environment/dev/terraform.tfvars
utility_role_arn = "arn:aws:iam::638362541257:role/{org}-utility-cross-account-access"
utility_bucket   = "{org}-utility-terraform-state-us-east-1-638362541257"
```

### 3. Deploy Environment Infrastructure

```bash
cd infrastructure/environment/{org}-environment/dev
terragrunt apply
# Environment can now read utility state via cross-account role
```

### 4. Verify Cross-Account Access

```bash
# Test role assumption from dev account
aws sts assume-role \
  --role-arn arn:aws:iam::638362541257:role/{org}-utility-cross-account-access \
  --role-session-name test-from-dev \
  --profile dev

# Verify state access
export AWS_ACCESS_KEY_ID=<temp-key>
export AWS_SECRET_ACCESS_KEY=<temp-secret>
export AWS_SESSION_TOKEN=<temp-token>

aws s3 ls s3://{org}-utility-terraform-state-us-east-1-638362541257/
```
