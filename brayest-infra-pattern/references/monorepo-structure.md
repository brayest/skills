# Monorepo Structure Reference

This document provides complete templates and guidance for setting up new monorepo infrastructure following the established pattern.

## Complete Monorepo Directory Structure

```
applications/{app-name}/
├── .git/                          ← Separate git repository
├── .gitignore
├── README.md
│
├── {app-code}/                    ← Application source code
│   ├── src/
│   ├── tests/
│   ├── package.json (or requirements.txt, etc.)
│   └── ...
│
├── environment/                   ← Terraform infrastructure code (reusable)
│   ├── backend.tf                (remote state dependencies)
│   ├── providers.tf              (AWS provider config)
│   ├── variables.tf              (input variables)
│   ├── locals.tf                 (computed values)
│   ├── outputs.tf                (exported values)
│   ├── iam.tf                    (application-owned IAM roles)
│   ├── storage.tf                (S3 buckets)
│   ├── queues.tf                 (SQS queues, optional)
│   ├── cache.tf                  (Redis/Elasticache, optional)
│   ├── opensearch.tf             (OpenSearch cluster, optional)
│   ├── dynamodb.tf               (DynamoDB tables, optional)
│   └── modules/                  (app-specific modules)
│
├── development/                   ← Terragrunt wrapper for dev
│   ├── terragrunt.hcl
│   └── terraform.tfvars
│
├── qa/                            ← Terragrunt wrapper for qa
│   ├── terragrunt.hcl
│   └── terraform.tfvars
│
├── prod/                          ← Terragrunt wrapper for prod
│   ├── terragrunt.hcl
│   └── terraform.tfvars
│
├── charts/                        ← Helm charts for Kubernetes deployment
│   └── {app-name}/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── templates/
│       │   ├── deployment.yaml
│       │   ├── service.yaml
│       │   └── serviceaccount.yaml
│       └── ...
│
└── .github/                       ← CI/CD workflows
    └── workflows/
        ├── terraform.yml
        └── deploy.yml
```

## Step-by-Step Setup Guide

### Step 1: Initialize Monorepo

```bash
# Create monorepo directory
mkdir -p applications/{app-name}
cd applications/{app-name}

# Initialize git
git init

# Create basic structure
mkdir -p environment/{app-code} charts development qa prod .github/workflows
```

### Step 2: Create Terraform Infrastructure

#### environment/backend.tf

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

# Depend on Environment Core (same account)
data "terraform_remote_state" "environment" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "core/terraform.tfstate"
    region = local.region
  }
}

# Depend on Environment Tools (same account, optional if using decentralized IAM)
data "terraform_remote_state" "environment_tools" {
  backend = "s3"
  config = {
    bucket = local.environment_bucket
    key    = "applications/terraform.tfstate"
    region = local.region
  }
}

# Depend on Utility (cross-account)
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

#### environment/providers.tf

```hcl
# applications/{app}/environment/providers.tf

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      Application = "{app-name}"
      Terraform   = "managed"
    }
  }
}
```

#### environment/variables.tf

```hcl
# applications/{app}/environment/variables.tf

variable "project" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment name (dev/qa/prod)"
}

variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

# Environment bucket (same account)
variable "environment_bucket" {
  type        = string
  description = "Environment state bucket"
}

# Utility cross-account references
variable "utility_bucket" {
  type        = string
  description = "Utility state bucket"
}

variable "utility_role_arn" {
  type        = string
  description = "Utility cross-account role ARN"
}

variable "utility_region" {
  type        = string
  description = "Utility region"
  default     = "us-east-1"
}

# Application-specific configuration
variable "app_instance_type" {
  type        = string
  description = "Instance type for application resources"
  default     = "t3.medium"
}

variable "app_replica_count" {
  type        = number
  description = "Number of application replicas"
  default     = 2
}
```

#### environment/locals.tf

```hcl
# applications/{app}/environment/locals.tf

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

resource "random_string" "this" {
  length  = 4
  special = false
  upper   = false
}

locals {
  region     = data.aws_region.current.id
  account_id = data.aws_caller_identity.current.account_id
  project    = var.project
  environment = var.environment

  # Environment bucket (same account)
  environment_bucket = var.environment_bucket

  # Utility references (cross-account)
  utility_bucket   = var.utility_bucket
  utility_role_arn = var.utility_role_arn
  utility_region   = var.utility_region

  # Extract from Environment remote state
  vpc_config = {
    vpc_id             = data.terraform_remote_state.environment.outputs.vpc_id
    private_subnet_ids = data.terraform_remote_state.environment.outputs.private_subnet_ids
    vpc_cidr           = data.terraform_remote_state.environment.outputs.vpc_cidr
  }

  cluster_config = {
    eks_cluster_name            = data.terraform_remote_state.environment.outputs.eks_cluster_name
    eks_cluster_oidc_issuer_url = data.terraform_remote_state.environment.outputs.eks_cluster_oidc_issuer_url
  }

  tags = {
    Project     = local.project
    Environment = local.environment
    Application = "{app-name}"
    Terraform   = "managed"
  }
}
```

#### environment/iam.tf (Application-Owned IAM)

```hcl
# applications/{app}/environment/iam.tf

locals {
  app_services = ["api", "worker", "ui"]
}

data "aws_iam_policy_document" "app_policy" {
  # S3 permissions
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
    resources = ["*"]
  }

  # Add other app-specific permissions
}

resource "aws_iam_policy" "app_policy" {
  name   = "{app}-policy-${var.environment}"
  policy = data.aws_iam_policy_document.app_policy.json
  tags   = local.tags
}

module "app_service_roles" {
  for_each = toset(local.app_services)

  source  = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"
  version = "~> 5.0"

  create_role = true
  role_name   = "{app}-${each.key}-${var.environment}"

  provider_url = local.cluster_config.eks_cluster_oidc_issuer_url

  role_policy_arns = [aws_iam_policy.app_policy.arn]

  oidc_fully_qualified_subjects = [
    "system:serviceaccount:{namespace}:${each.key}-sa"
  ]

  tags = local.tags
}
```

#### environment/storage.tf

```hcl
# applications/{app}/environment/storage.tf

resource "aws_s3_bucket" "app_data" {
  bucket = "${local.project}-{app}-data-${local.environment}-${local.account_id}-${local.region}-${random_string.this.id}"
  
  tags = merge(local.tags, {
    Purpose = "application-data"
  })
}

resource "aws_s3_bucket_versioning" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  versioning_configuration {
    status = var.environment == "prod" ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app_data" {
  bucket = aws_s3_bucket.app_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

#### environment/outputs.tf

```hcl
# applications/{app}/environment/outputs.tf

# IAM role ARNs
output "app_service_role_arns" {
  value = {
    for svc in local.app_services :
    svc => module.app_service_roles[svc].iam_role_arn
  }
}

# S3 outputs
output "app_data_bucket_id" {
  value = aws_s3_bucket.app_data.id
}

output "app_data_bucket_arn" {
  value = aws_s3_bucket.app_data.arn
}

# Add other resource outputs as needed
```

### Step 3: Create Terragrunt Wrappers

#### development/terragrunt.hcl

```hcl
# applications/{app}/development/terragrunt.hcl

locals {
  indentifier    = "{org}"
  environment    = "dev"
  layer          = "{app}"
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

#### development/terraform.tfvars

```hcl
# applications/{app}/development/terraform.tfvars

# Environment basics
project     = "{org}"
environment = "dev"
region      = "us-east-1"

# Environment bucket (same account)
environment_bucket = "{org}-dev-terraform-state-us-east-1-{dev-account-id}"

# Utility cross-account references
utility_bucket   = "{org}-utility-terraform-state-us-east-1-{utility-account-id}"
utility_role_arn = "arn:aws:iam::{utility-account-id}:role/{org}-utility-cross-account-access"
utility_region   = "us-east-1"

# Application-specific configuration (dev values)
app_instance_type  = "t3.medium"
app_replica_count  = 1
```

#### qa/terragrunt.hcl

Same as development, but with `environment = "qa"`.

#### prod/terragrunt.hcl

Same as development, but with `environment = "prod"` and possibly different `indentifier` (e.g., "{org}-active").

#### prod/terraform.tfvars

```hcl
# applications/{app}/prod/terraform.tfvars

project     = "{org}"
environment = "prod"
region      = "us-east-1"

environment_bucket = "{org}-prod-terraform-state-us-east-1-{prod-account-id}"

utility_bucket   = "{org}-utility-terraform-state-us-east-1-{utility-account-id}"
utility_role_arn = "arn:aws:iam::{utility-account-id}:role/{org}-utility-cross-account-access"
utility_region   = "us-east-1"

# Production values
app_instance_type  = "t3.large"
app_replica_count  = 3
```

### Step 4: Create Helm Charts

#### charts/{app}/Chart.yaml

```yaml
apiVersion: v2
name: {app}
description: {App description}
type: application
version: 1.0.0
appVersion: "1.0.0"
```

#### charts/{app}/values.yaml

```yaml
replicaCount: 2

image:
  repository: {ecr-registry}/{app}
  pullPolicy: IfNotPresent
  tag: "latest"

serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: ""  # Set via CI/CD from Terraform output
  name: ""

service:
  type: ClusterIP
  port: 8080

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: {app}.{domain}
      paths:
        - path: /
          pathType: Prefix

resources:
  limits:
    cpu: 1000m
    memory: 2Gi
  requests:
    cpu: 500m
    memory: 1Gi

env:
  - name: ENVIRONMENT
    value: "production"
  - name: AWS_REGION
    value: "us-east-1"
```

### Step 5: Create CI/CD Workflows

#### .github/workflows/terraform.yml

```yaml
name: Terraform

on:
  push:
    branches: [main, develop]
    paths:
      - 'environment/**'
      - 'development/**'
      - 'qa/**'
      - 'prod/**'
  pull_request:
    paths:
      - 'environment/**'
      - 'development/**'
      - 'qa/**'
      - 'prod/**'

jobs:
  terraform:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        environment: [development, qa, prod]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v2
        with:
          terraform_version: 1.5.0
      
      - name: Setup Terragrunt
        run: |
          wget https://github.com/gruntwork-io/terragrunt/releases/download/v0.50.0/terragrunt_linux_amd64
          chmod +x terragrunt_linux_amd64
          sudo mv terragrunt_linux_amd64 /usr/local/bin/terragrunt
      
      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Terragrunt Init
        working-directory: ./${{ matrix.environment }}
        run: terragrunt init
      
      - name: Terragrunt Plan
        working-directory: ./${{ matrix.environment }}
        run: terragrunt plan
      
      - name: Terragrunt Apply
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        working-directory: ./${{ matrix.environment }}
        run: terragrunt apply -auto-approve
```

### Step 6: Initialize and Deploy

```bash
# Initialize development environment
cd applications/{app}/development
terragrunt init

# Plan infrastructure
terragrunt plan

# Apply infrastructure
terragrunt apply

# Get outputs (role ARNs, bucket names, etc.)
terragrunt output
```

## Integration with Existing Infrastructure

### Referencing Platform Resources

```hcl
# In your application's Terraform code

# VPC for resources
resource "aws_security_group" "app" {
  vpc_id = local.vpc_config.vpc_id
  # ...
}

# Subnets for resources
resource "aws_opensearch_domain" "main" {
  vpc_options {
    subnet_ids = local.vpc_config.private_subnet_ids
  }
}

# OIDC for IAM roles
module "app_service_roles" {
  provider_url = local.cluster_config.eks_cluster_oidc_issuer_url
  # ...
}
```

### Kubernetes Service Account Integration

```yaml
# charts/{app}/templates/serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ .Values.serviceAccount.name }}
  annotations:
    eks.amazonaws.com/role-arn: {{ .Values.serviceAccount.annotations.eks.amazonaws.com/role-arn }}
```

Set the role ARN in Helm values:
```bash
# From Terraform output
APP_ROLE_ARN=$(terragrunt output -raw app_service_role_arns | jq -r '.api')

# Deploy with Helm
helm upgrade --install {app} ./charts/{app} \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$APP_ROLE_ARN
```

## Common Patterns

### Multi-Service Application

```
applications/{app}/
├── environment/
│   ├── iam.tf           (roles for api, worker, ui)
│   ├── storage.tf       (shared S3 buckets)
│   ├── cache.tf         (shared Redis)
│   └── opensearch.tf    (shared OpenSearch)
├── {app}-api/           (API service code)
├── {app}-worker/        (Worker service code)
├── {app}-ui/            (UI service code)
└── charts/
    ├── {app}-api/
    ├── {app}-worker/
    └── {app}-ui/
```

### Shared Module Pattern

```
applications/{app}/
├── environment/
│   ├── opensearch.tf
│   ├── dynamodb.tf
│   └── modules/
│       └── custom-component/
│           ├── main.tf
│           ├── variables.tf
│           └── outputs.tf
```

## Best Practices

1. **One Terraform root**: Keep all Terraform code in `environment/`
2. **Environment-agnostic code**: Use variables for environment-specific values
3. **Self-contained infrastructure**: Own all application-specific resources
4. **Clear outputs**: Export all values needed by Kubernetes/CI/CD
5. **Proper tagging**: Tag all resources with Application, Environment, Project
6. **State isolation**: Use unique state keys per application
7. **Documentation**: Keep README.md updated with setup instructions
