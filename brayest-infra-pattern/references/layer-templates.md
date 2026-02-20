# Layer Templates Reference

This document provides complete Terraform code templates for each infrastructure layer.

## Template Structure Overview

Each layer template includes:
- `backend.tf` - Backend config and remote state dependencies
- `variables.tf` - Input variables
- `locals.tf` - Computed values and remote state extraction
- `outputs.tf` - Exported values for downstream layers
- `providers.tf` - AWS provider configuration

## Utility Layer Template

### backend.tf

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

### variables.tf

```hcl
# infrastructure/utility/{org}-utility/environment/variables.tf

variable "project" {
  type        = string
  description = "Project name"
}

variable "environment" {
  type        = string
  description = "Environment name (utility)"
}

variable "region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

# DR cross-account references
variable "dr_bucket" {
  type        = string
  description = "DR state bucket name"
}

variable "dr_role_arn" {
  type        = string
  description = "DR cross-account role ARN"
}

variable "dr_region" {
  type        = string
  description = "DR region"
  default     = "us-east-1"
}

# Infrastructure configuration
variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR block"
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  type        = list(string)
  description = "Availability zones"
}

variable "eks_version" {
  type        = string
  description = "EKS cluster version"
}
```

### locals.tf

```hcl
# infrastructure/utility/{org}-utility/environment/locals.tf

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {}

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

  # DR references
  dr_bucket   = var.dr_bucket
  dr_role_arn = var.dr_role_arn
  dr_region   = var.dr_region

  # Extract from DR remote state
  dr_vpc_config = {
    vpc_id             = data.terraform_remote_state.dr.outputs.vpc_id
    vpc_cidr           = data.terraform_remote_state.dr.outputs.vpc_cidr
    route_table_ids    = data.terraform_remote_state.dr.outputs.private_route_table_ids
  }

  tags = {
    Project     = local.project
    Environment = local.environment
    Terraform   = "managed"
    Layer       = "utility"
  }
}
```

### outputs.tf

```hcl
# infrastructure/utility/{org}-utility/environment/outputs.tf

# VPC outputs
output "vpc_id" {
  value = aws_vpc.main.id
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "vpc_config" {
  value = {
    vpc_id             = aws_vpc.main.id
    vpc_cidr           = aws_vpc.main.cidr_block
    private_subnet_ids = aws_subnet.private[*].id
    availability_zones = local.availability_zones
  }
}

# EKS outputs
output "eks_cluster_name" {
  value = aws_eks_cluster.main.name
}

output "eks_cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "eks_cluster_oidc_issuer_url" {
  value = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

output "cluster_config" {
  value = {
    eks_cluster_name            = aws_eks_cluster.main.name
    eks_cluster_endpoint        = aws_eks_cluster.main.endpoint
    eks_cluster_oidc_issuer_url = aws_eks_cluster.main.identity[0].oidc[0].issuer
    eks_admin_role_arn          = aws_iam_role.eks_admin.arn
  }
}

# Aurora outputs
output "aurora_cluster_endpoint" {
  value = aws_rds_cluster.main.endpoint
}

output "aurora_cluster_arn" {
  value = aws_rds_cluster.main.arn
}

# Cross-account role
output "cross_account_role_arn" {
  value = aws_iam_role.cross_account.arn
}

# Domain outputs
output "public_domain" {
  value = aws_route53_zone.public.name
}

output "internal_domain_name" {
  value = aws_route53_zone.private.name
}
```

### providers.tf

```hcl
# infrastructure/utility/{org}-utility/environment/providers.tf

provider "aws" {
  region = var.region
}

# DR provider (for cross-account resource creation if needed)
provider "aws" {
  alias  = "dr"
  region = var.dr_region
  assume_role {
    role_arn = local.dr_role_arn
  }
}
```

## Environment Layer Template

### backend.tf

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
      role_arn = local.utility_role_arn
    }
    bucket = local.utility_bucket
    key    = "tools/terraform.tfstate"
    region = local.utility_region
  }
}

# Depends on DR (cross-account, optional)
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

### variables.tf

```hcl
# infrastructure/environment/{org}-environment/environment/variables.tf

variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "region" {
  type    = string
  default = "us-east-1"
}

# Utility cross-account references
variable "utility_bucket" {
  type = string
}

variable "utility_role_arn" {
  type = string
}

variable "utility_region" {
  type    = string
  default = "us-east-1"
}

variable "utility_account" {
  type = string
}

# DR cross-account references
variable "dr_bucket" {
  type = string
}

variable "dr_role_arn" {
  type = string
}

variable "dr_region" {
  type    = string
  default = "us-east-1"
}

# Environment-specific config
variable "environment_bucket" {
  type = string
}

variable "vpc_cidr" {
  type = string
}

variable "availability_zones" {
  type = list(string)
}
```

### locals.tf

```hcl
# infrastructure/environment/{org}-environment/environment/locals.tf

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  region     = data.aws_region.current.id
  account_id = data.aws_caller_identity.current.account_id
  project    = var.project
  environment = var.environment

  # Utility references
  utility_bucket   = var.utility_bucket
  utility_role_arn = var.utility_role_arn
  utility_region   = var.utility_region
  utility_account  = var.utility_account

  # DR references
  dr_bucket   = var.dr_bucket
  dr_role_arn = var.dr_role_arn
  dr_region   = var.dr_region

  # Environment bucket (same account)
  environment_bucket = var.environment_bucket

  # Extract from Utility remote state
  utility_vpc_config = {
    vpc_id             = data.terraform_remote_state.utility.outputs.vpc_id
    private_subnet_ids = data.terraform_remote_state.utility.outputs.private_subnet_ids
  }

  cluster_config = {
    eks_cluster_name            = data.terraform_remote_state.utility.outputs.eks_cluster_name
    eks_cluster_endpoint        = data.terraform_remote_state.utility.outputs.eks_cluster_endpoint
    eks_cluster_oidc_issuer_url = data.terraform_remote_state.utility.outputs.eks_cluster_oidc_issuer_url
  }

  tags = {
    Project     = local.project
    Environment = local.environment
    Terraform   = "managed"
    Layer       = "environment"
  }
}
```

### outputs.tf

```hcl
# infrastructure/environment/{org}-environment/environment/outputs.tf

# VPC outputs
output "vpc_id" {
  value = aws_vpc.main.id
}

output "vpc_cidr" {
  value = aws_vpc.main.cidr_block
}

output "private_subnet_ids" {
  value = aws_subnet.private[*].id
}

output "vpc_config" {
  value = {
    vpc_id             = aws_vpc.main.id
    vpc_cidr           = aws_vpc.main.cidr_block
    private_subnet_ids = aws_subnet.private[*].id
  }
}

# EKS outputs (pass-through from utility with environment-specific additions)
output "eks_cluster_name" {
  value = local.cluster_config.eks_cluster_name
}

output "eks_cluster_endpoint" {
  value = local.cluster_config.eks_cluster_endpoint
}

output "eks_cluster_oidc_issuer_url" {
  value = local.cluster_config.eks_cluster_oidc_issuer_url
}

# RDS outputs
output "aurora_cluster_endpoint" {
  value = aws_rds_cluster.environment.endpoint
}

output "rds_record_set_writer" {
  value = aws_route53_record.rds_writer.fqdn
}

output "rds_record_set_reader" {
  value = aws_route53_record.rds_reader.fqdn
}

# Domain outputs
output "internal_domain_name" {
  value = aws_route53_zone.private.name
}

output "internal_domain_id" {
  value = aws_route53_zone.private.zone_id
}

output "public_domain" {
  value = data.terraform_remote_state.utility.outputs.public_domain
}

# Load balancer outputs
output "internal_loadbalancer_arn" {
  value = aws_lb.internal.arn
}

output "public_loadbalancer_endpoint" {
  value = aws_lb.public.dns_name
}

# Environment tags
output "environment_tags" {
  value = local.tags
}
```

## Application Layer Template

### backend.tf

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

### variables.tf

```hcl
# applications/{app}/environment/variables.tf

variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "region" {
  type    = string
  default = "us-east-1"
}

# Environment bucket (same account)
variable "environment_bucket" {
  type = string
}

# Utility cross-account references
variable "utility_bucket" {
  type = string
}

variable "utility_role_arn" {
  type = string
}

variable "utility_region" {
  type    = string
  default = "us-east-1"
}

# Application-specific config
variable "opensearch_instance_type" {
  type    = string
  default = "r5.large.search"
}

variable "opensearch_volume_size" {
  type    = number
  default = 100
}

variable "redis_node_type" {
  type    = string
  default = "cache.r5.large"
}
```

### locals.tf

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
    Terraform   = "managed"
    Component   = "{app-name}"
  }
}
```

### outputs.tf

```hcl
# applications/{app}/environment/outputs.tf

# Application IAM role ARNs (self-owned)
output "app_service_role_arns" {
  value = {
    for svc in local.app_services :
    svc => module.app_service_roles[svc].iam_role_arn
  }
}

# S3 buckets
output "app_bucket_id" {
  value = aws_s3_bucket.app_data.id
}

output "app_bucket_arn" {
  value = aws_s3_bucket.app_data.arn
}

# OpenSearch
output "opensearch_endpoint" {
  value = aws_opensearch_domain.main.endpoint
}

output "opensearch_arn" {
  value = aws_opensearch_domain.main.arn
}

# Redis
output "redis_primary_endpoint" {
  value = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "redis_port" {
  value = aws_elasticache_replication_group.main.port
}
```

### iam.tf (Application-Owned IAM)

```hcl
# applications/{app}/environment/iam.tf

# Define application services
locals {
  app_services = ["app-api", "app-worker", "app-ui"]
}

# IAM policy for application services
data "aws_iam_policy_document" "app_policy" {
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
}

# OIDC-assumable roles for EKS service accounts
module "app_service_roles" {
  for_each = toset(local.app_services)

  source = "terraform-aws-modules/iam/aws//modules/iam-assumable-role-with-oidc"

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

## Common Patterns

### Extracting Nested Remote State Outputs

```hcl
# When upstream outputs nested objects
locals {
  vpc_id = data.terraform_remote_state.environment.outputs.vpc_config.vpc_id
  
  # Or extract entire object
  vpc_config = data.terraform_remote_state.environment.outputs.vpc_config
}
```

### Conditional Remote State Access

```hcl
data "terraform_remote_state" "dr" {
  count = var.enable_dr ? 1 : 0
  # ...
}

locals {
  dr_vpc_id = var.enable_dr ? data.terraform_remote_state.dr[0].outputs.vpc_id : null
}
```

### Multiple Environments in Same File

```hcl
locals {
  environment_specific = {
    dev = {
      instance_type = "t3.medium"
      replica_count = 1
    }
    prod = {
      instance_type = "m5.xlarge"
      replica_count = 3
    }
  }
  
  config = local.environment_specific[var.environment]
}
```
