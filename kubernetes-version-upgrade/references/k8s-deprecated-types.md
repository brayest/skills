# Kubernetes Provider — Deprecated Types Reference

Complete mapping of deprecated kubernetes provider resource types (non-versioned) to their replacements, with import ID formats for the state rm + import migration approach.

## Import ID Scope Rules

**Cluster-scoped** (ID = just the resource `name`):
- `kubernetes_namespace`
- `kubernetes_cluster_role`
- `kubernetes_cluster_role_binding`
- `kubernetes_persistent_volume`
- `kubernetes_storage_class`

**Namespaced** (ID = `namespace/name`):
- All other resource types

## Resource Type Mapping

| Deprecated Type | Replacement | Import ID | Notes |
|---|---|---|---|
| `kubernetes_namespace` | `kubernetes_namespace_v1` | `name` | cluster-scoped |
| `kubernetes_cluster_role` | `kubernetes_cluster_role_v1` | `name` | cluster-scoped |
| `kubernetes_cluster_role_binding` | `kubernetes_cluster_role_binding_v1` | `name` | cluster-scoped |
| `kubernetes_persistent_volume` | `kubernetes_persistent_volume_v1` | `name` | cluster-scoped |
| `kubernetes_storage_class` | `kubernetes_storage_class_v1` | `name` | cluster-scoped |
| `kubernetes_role` | `kubernetes_role_v1` | `namespace/name` | |
| `kubernetes_role_binding` | `kubernetes_role_binding_v1` | `namespace/name` | |
| `kubernetes_secret` | `kubernetes_secret_v1` | `namespace/name` | |
| `kubernetes_service` | `kubernetes_service_v1` | `namespace/name` | |
| `kubernetes_service_account` | `kubernetes_service_account_v1` | `namespace/name` | |
| `kubernetes_config_map` | `kubernetes_config_map_v1` | `namespace/name` | |
| `kubernetes_deployment` | `kubernetes_deployment_v1` | `namespace/name` | |
| `kubernetes_daemonset` | `kubernetes_daemonset_v1` | `namespace/name` | |
| `kubernetes_stateful_set` | `kubernetes_stateful_set_v1` | `namespace/name` | |
| `kubernetes_ingress` | `kubernetes_ingress_v1` | `namespace/name` | |
| `kubernetes_network_policy` | `kubernetes_network_policy_v1` | `namespace/name` | |
| `kubernetes_persistent_volume_claim` | `kubernetes_persistent_volume_claim_v1` | `namespace/name` | |
| `kubernetes_pod` | `kubernetes_pod_v1` | `namespace/name` | |
| `kubernetes_pod_disruption_budget` | `kubernetes_pod_disruption_budget_v1` | `namespace/name` | |
| `kubernetes_resource_quota` | `kubernetes_resource_quota_v1` | `namespace/name` | |
| `kubernetes_cron_job` | `kubernetes_cron_job_v1` | `namespace/name` | |
| `kubernetes_horizontal_pod_autoscaler` | `kubernetes_horizontal_pod_autoscaler_v2` | `namespace/name` | maps to v2, not v1 |

## Data Source Mapping

| Deprecated | Replacement |
|---|---|
| `data "kubernetes_namespace"` | `data "kubernetes_namespace_v1"` |
| `data "kubernetes_cluster_role"` | `data "kubernetes_cluster_role_v1"` |
| `data "kubernetes_config_map"` | `data "kubernetes_config_map_v1"` |
| `data "kubernetes_secret"` | `data "kubernetes_secret_v1"` |
| `data "kubernetes_service"` | `data "kubernetes_service_v1"` |
| `data "kubernetes_service_account"` | `data "kubernetes_service_account_v1"` |
| `data "kubernetes_storage_class"` | `data "kubernetes_storage_class_v1"` |
| `data "kubernetes_persistent_volume_claim"` | `data "kubernetes_persistent_volume_claim_v1"` |

## NOT Deprecated

These types do NOT have `_v1` replacements and must NOT be renamed:

- `kubernetes_manifest` — stays as-is, used for CRDs and custom resources
- `kubernetes_labels` — stays as-is
- `kubernetes_annotations` — stays as-is
- `kubernetes_certificate_signing_request` — has `_v1` but different semantics (check provider version)

## Grep Commands for Audit

```bash
# Find all deprecated resource declarations
grep -rn "resource \"kubernetes_[a-z_]*\"" . --include="*.tf" | grep -v "_v1"

# Find all deprecated data source declarations
grep -rn "data \"kubernetes_[a-z_]*\"" . --include="*.tf" | grep -v "_v1"

# Find all deprecated attribute references (cross-references)
grep -rn "\bkubernetes_[a-z]*\." . --include="*.tf" | grep -v "_v1\."

# List deprecated types currently in Terraform state
terraform state list | grep -E "^kubernetes_" | grep -v "_v1\."
# or with terragrunt:
terragrunt state list | grep -E "^kubernetes_" | grep -v "_v1\."

# Count how many warnings to expect (each deprecated declaration = 1 warning)
grep -rc "resource \"kubernetes_" . --include="*.tf" | grep -v "_v1" | awk -F: '{sum+=$2} END{print sum}'
```

## Manual Import Examples

For cases where the automated script cannot be used, manual import commands:

```bash
# Cluster-scoped resource (just the name)
terraform import kubernetes_namespace_v1.my_ns production

# Namespaced resource (namespace/name)
terraform import kubernetes_role_v1.my_role btp-tools/developers-tools-role
terraform import kubernetes_secret_v1.my_secret default/vault-auth-dev-secret

# for_each resource (use quoted instance key)
terraform import 'kubernetes_namespace_v1.namespace["cope"]' cope
terraform import 'kubernetes_role_v1.role["btp-tools"]' btp-tools/my-role

# With terragrunt wrapper
terragrunt import 'kubernetes_role_binding_v1.binding' btp-tools/developer-tools-role-binding
```
