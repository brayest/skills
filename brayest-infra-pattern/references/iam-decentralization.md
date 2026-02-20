# IAM Decentralization Pattern Reference

This document provides detailed examples of the decentralized permissions pattern where applications own their IAM roles instead of relying on a centralized platform layer.

## Problem: Centralized Service Policy Map

### Anti-Pattern (Old Approach)

```hcl
# ❌ infrastructure/environment/{org}-environment-tools/environment/services.tf

# Centralized policy definitions
data "aws_iam_policy_document" "app_one" {
  statement {
    actions   = ["s3:*"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "app_two" {
  statement {
    actions   = ["sqs:*"]
    resources = ["*"]
  }
}

# Centralized map (chicken-and-egg problem!)
locals {
  service_policy = {
    app-one   = data.aws_iam_policy_document.app_one.json
    app-two   = data.aws_iam_policy_document.app_two.json
    app-three = data.aws_iam_policy_document.app_three.json
    # Must add every app here BEFORE deploying!
  }
}

# Platform creates roles for all apps
resource "aws_iam_policy" "service_policy" {
  for_each = local.service_policy
  
  name   = "${each.key}-policy"
  policy = local.service_policy[each.key]  # Fails if app not in map
}

module "service_account_role" {
  for_each = local.service_policy
  
  source = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"
  
  role_name        = "${each.key}-role"
  provider_url     = local.eks_cluster_oidc_issuer_url
  role_policy_arns = [aws_iam_policy.service_policy[each.key].arn]
  
  oidc_fully_qualified_subjects = [
    "system:serviceaccount:${each.value.namespace}:${each.key}-sa"
  ]
}

# Platform exports per-app roles
output "service_account_roles_arns" {
  value = {
    for app_key, _ in local.service_policy :
    app_key => module.service_account_role[app_key].iam_role_arn
  }
}
```

### Problems with Centralized Approach

1. **Chicken-and-egg**: Must add app to central map before deploying app
2. **Tight coupling**: Platform knows about every application
3. **No autonomy**: Teams can't deploy new services independently
4. **Merge conflicts**: Everyone modifies the same central file
5. **Blocks AI development**: Can't create monorepos with self-contained infrastructure

## Solution: Decentralized Application-Owned IAM

### Pattern (New Approach)

```hcl
# ✅ applications/{app}/environment/iam.tf

# Define application services
locals {
  app_services = ["app-api", "app-worker", "app-ui"]
}

# Application-specific IAM policy
data "aws_iam_policy_document" "app_policy" {
  # S3 permissions for app-specific buckets
  statement {
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.app_data.arn,
      "${aws_s3_bucket.app_data.arn}/*"
    ]
  }

  # SQS permissions
  statement {
    actions = [
      "sqs:SendMessage",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = ["arn:aws:sqs:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:${local.project}-*"]
  }

  # Bedrock permissions (for AI workloads)
  statement {
    actions   = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
      "arn:aws:bedrock:*::foundation-model/amazon.titan-*"
    ]
  }

  # OpenSearch permissions
  statement {
    actions = [
      "es:ESHttpPost",
      "es:ESHttpPut",
      "es:ESHttpGet",
      "es:ESHttpDelete"
    ]
    resources = ["${aws_opensearch_domain.main.arn}/*"]
  }

  # DynamoDB permissions
  statement {
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ]
    resources = ["arn:aws:dynamodb:${data.aws_region.current.id}:${data.aws_caller_identity.current.account_id}:table/${local.project}-*"]
  }
}

resource "aws_iam_policy" "app_policy" {
  name        = "{app}-policy-${var.environment}"
  description = "IAM policy for {app} application services"
  policy      = data.aws_iam_policy_document.app_policy.json
}

# Create OIDC-assumable roles for each service
module "app_service_roles" {
  for_each = toset(local.app_services)

  source  = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"
  version = "~> 5.0"

  create_role = true
  role_name   = "{app}-${each.key}-${var.environment}"

  # Get OIDC issuer from environment layer (platform provides primitives)
  provider_url = data.terraform_remote_state.environment.outputs.eks_cluster_oidc_issuer_url

  role_policy_arns = [aws_iam_policy.app_policy.arn]

  oidc_fully_qualified_subjects = [
    "system:serviceaccount:{namespace}:${each.key}-sa"
  ]

  tags = merge(local.tags, {
    Service = each.key
  })
}

# Export role ARNs for use in Kubernetes manifests
output "app_service_role_arns" {
  value = {
    for svc in local.app_services :
    svc => module.app_service_roles[svc].iam_role_arn
  }
}
```

### Benefits of Decentralized Approach

1. **No chicken-and-egg**: Application creates its own roles, no central dependencies
2. **Loose coupling**: Platform only provides OIDC issuer URL (primitive)
3. **Team autonomy**: Teams deploy independently
4. **No merge conflicts**: Each app owns its own IAM file
5. **AI-friendly**: Monorepos are self-contained with infrastructure

## Platform Layer Changes

### What Platform DOES Provide

```hcl
# infrastructure/environment/{org}-environment/environment/outputs.tf

# ✅ Provide primitives (shared infrastructure)
output "eks_cluster_oidc_issuer_url" {
  value = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "aurora_cluster_endpoint" {
  value = aws_rds_cluster.main.endpoint
}
```

### What Platform Does NOT Provide

```hcl
# ❌ Remove per-app role exports
# output "service_account_roles_arns" {
#   value = {
#     for app_key, _ in local.btp_services :
#     app_key => module.service_account_role[app_key].iam_role_arn
#   }
# }

# ❌ Remove per-app knowledge
# locals {
#   service_policy = {
#     app-one = ...
#     app-two = ...
#   }
# }
```

## Complete Application IAM Example

### Directory Structure

```
applications/{app}/
├── environment/
│   ├── backend.tf           (remote state dependencies)
│   ├── locals.tf            (extract OIDC issuer from environment)
│   ├── iam.tf               (create app-owned IAM roles)
│   ├── storage.tf           (S3 buckets)
│   ├── opensearch.tf        (OpenSearch cluster)
│   └── outputs.tf           (export role ARNs)
└── dev/
    ├── terragrunt.hcl
    └── terraform.tfvars
```

### locals.tf (Extract OIDC Issuer)

```hcl
# applications/{app}/environment/locals.tf

locals {
  # Extract EKS OIDC issuer from environment layer
  eks_cluster_oidc_issuer_url = data.terraform_remote_state.environment.outputs.eks_cluster_oidc_issuer_url
  
  # VPC config for OpenSearch/Redis
  vpc_config = {
    vpc_id             = data.terraform_remote_state.environment.outputs.vpc_id
    private_subnet_ids = data.terraform_remote_state.environment.outputs.private_subnet_ids
  }
}
```

### iam.tf (Complete IAM Setup)

```hcl
# applications/{app}/environment/iam.tf

locals {
  app_services = ["app-api", "app-worker", "app-ui"]
}

# Comprehensive IAM policy for application
data "aws_iam_policy_document" "app_policy" {
  # S3 - Application buckets
  statement {
    sid = "S3Access"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetObjectVersion"
    ]
    resources = [
      aws_s3_bucket.app_data.arn,
      "${aws_s3_bucket.app_data.arn}/*",
      aws_s3_bucket.app_uploads.arn,
      "${aws_s3_bucket.app_uploads.arn}/*"
    ]
  }

  # SQS - Queue management
  statement {
    sid = "SQSAccess"
    actions = [
      "sqs:SendMessage",
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ChangeMessageVisibility"
    ]
    resources = ["arn:aws:sqs:*:*:{app}-*"]
  }

  # Bedrock - AI model invocation
  statement {
    sid = "BedrockAccess"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-*",
      "arn:aws:bedrock:*::foundation-model/anthropic.claude-3-haiku-*",
      "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-*"
    ]
  }

  # Textract - Document OCR (if needed)
  statement {
    sid = "TextractAccess"
    actions = [
      "textract:DetectDocumentText",
      "textract:StartDocumentTextDetection",
      "textract:GetDocumentTextDetection"
    ]
    resources = ["*"]
  }

  # OpenSearch - Full access to app cluster
  statement {
    sid = "OpenSearchAccess"
    actions = [
      "es:ESHttpPost",
      "es:ESHttpPut",
      "es:ESHttpGet",
      "es:ESHttpDelete"
    ]
    resources = [
      aws_opensearch_domain.main.arn,
      "${aws_opensearch_domain.main.arn}/*"
    ]
  }

  # DynamoDB - Table access
  statement {
    sid = "DynamoDBAccess"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "dynamodb:DescribeTable"
    ]
    resources = [
      aws_dynamodb_table.app_jobs.arn,
      "${aws_dynamodb_table.app_jobs.arn}/index/*"
    ]
  }

  # STS - Assume OpenSearch master role (if needed)
  statement {
    sid = "STSAssumeRole"
    actions = ["sts:AssumeRole"]
    resources = [
      "arn:aws:iam::*:role/{org}-opensearch-master-*"
    ]
  }

  # Secrets Manager - Read app secrets
  statement {
    sid = "SecretsManagerAccess"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret"
    ]
    resources = [
      "arn:aws:secretsmanager:*:*:secret:{app}-*"
    ]
  }
}

resource "aws_iam_policy" "app_policy" {
  name        = "{app}-policy-${var.environment}"
  description = "Comprehensive IAM policy for {app} services"
  policy      = data.aws_iam_policy_document.app_policy.json
  
  tags = local.tags
}

# Create OIDC-assumable IAM roles
module "app_service_roles" {
  for_each = toset(local.app_services)

  source  = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"
  version = "~> 5.0"

  create_role = true
  role_name   = "{app}-${each.key}-${var.environment}"

  provider_url = local.eks_cluster_oidc_issuer_url

  role_policy_arns = [aws_iam_policy.app_policy.arn]

  oidc_fully_qualified_subjects = [
    "system:serviceaccount:{namespace}:${each.key}-sa"
  ]

  tags = merge(local.tags, {
    Service     = each.key
    Application = "{app}"
  })
}
```

### outputs.tf (Export Role ARNs)

```hcl
# applications/{app}/environment/outputs.tf

output "app_service_role_arns" {
  description = "IAM role ARNs for application services"
  value = {
    for svc in local.app_services :
    svc => module.app_service_roles[svc].iam_role_arn
  }
}

# Example output:
# {
#   "app-api"    = "arn:aws:iam::123456789012:role/{app}-app-api-dev"
#   "app-worker" = "arn:aws:iam::123456789012:role/{app}-app-worker-dev"
#   "app-ui"     = "arn:aws:iam::123456789012:role/{app}-app-ui-dev"
# }
```

## Integration with Kubernetes

### Service Account Annotation

```yaml
# kubernetes/app-api-serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-api-sa
  namespace: {namespace}
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/{app}-app-api-dev
```

### Helm Chart Integration

```yaml
# helm/templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.service.name }}-sa
  namespace: {{ .Values.namespace }}
  annotations:
    eks.amazonaws.com/role-arn: {{ .Values.iam.roleArn }}
```

```yaml
# helm/values.yaml
service:
  name: app-api

iam:
  roleArn: ""  # Set via terraform output or CI/CD

namespace: {namespace}
```

## Migration Path

### Step 1: Create Application IAM in App Repo

1. Add `iam.tf` to `applications/{app}/environment/`
2. Define `local.app_services`
3. Create `aws_iam_policy_document` with app permissions
4. Create `module.app_service_roles` for OIDC roles
5. Export `app_service_role_arns` output

### Step 2: Update Application to Use New Roles

1. Update Kubernetes service accounts with new role ARNs
2. Deploy application
3. Verify IRSA is working (pods can assume roles)

### Step 3: Remove from Platform Layer

1. Remove app from `local.service_policy` map
2. Remove centralized IAM policy/role creation
3. Remove app-specific outputs from platform

### Step 4: Clean Up

1. Delete old IAM roles/policies from platform layer
2. Update platform outputs documentation
3. Remove centralized service map entirely

## Common IAM Policy Patterns

### S3 Bucket Access

```hcl
statement {
  actions = [
    "s3:GetObject",
    "s3:PutObject",
    "s3:DeleteObject",
    "s3:ListBucket"
  ]
  resources = [
    aws_s3_bucket.my_bucket.arn,
    "${aws_s3_bucket.my_bucket.arn}/*"
  ]
}
```

### SQS Queue Access

```hcl
statement {
  actions = [
    "sqs:SendMessage",
    "sqs:ReceiveMessage",
    "sqs:DeleteMessage",
    "sqs:GetQueueAttributes"
  ]
  resources = ["arn:aws:sqs:*:*:my-queue-*"]
}
```

### Bedrock Model Invocation

```hcl
statement {
  actions   = ["bedrock:InvokeModel"]
  resources = [
    "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
    "arn:aws:bedrock:*:${local.account_id}:inference-profile/*"
  ]
}
```

### OpenSearch Access

```hcl
statement {
  actions = [
    "es:ESHttpPost",
    "es:ESHttpPut",
    "es:ESHttpGet"
  ]
  resources = ["${aws_opensearch_domain.main.arn}/*"]
}
```

### DynamoDB Table Access

```hcl
statement {
  actions = [
    "dynamodb:PutItem",
    "dynamodb:GetItem",
    "dynamodb:UpdateItem",
    "dynamodb:Query"
  ]
  resources = [
    aws_dynamodb_table.my_table.arn,
    "${aws_dynamodb_table.my_table.arn}/index/*"
  ]
}
```
