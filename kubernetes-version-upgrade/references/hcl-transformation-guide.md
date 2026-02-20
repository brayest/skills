# HCL Transformation Guide

Step-by-step instructions for renaming deprecated kubernetes resource types in Terraform `.tf` files, with patterns covering every type of cross-reference that must be updated.

## Replacement Ordering (Critical)

Always process types in this order to prevent substring replacement bugs. Types listed earlier are substrings of types listed later — processing the specific ones first avoids partial replacements.

```
1. kubernetes_cluster_role_binding  →  kubernetes_cluster_role_binding_v1
2. kubernetes_role_binding          →  kubernetes_role_binding_v1
3. kubernetes_cluster_role          →  kubernetes_cluster_role_v1
4. kubernetes_role                  →  kubernetes_role_v1
5. kubernetes_persistent_volume_claim → kubernetes_persistent_volume_claim_v1
6. kubernetes_persistent_volume     →  kubernetes_persistent_volume_v1
7. kubernetes_pod_disruption_budget →  kubernetes_pod_disruption_budget_v1
8. kubernetes_horizontal_pod_autoscaler → kubernetes_horizontal_pod_autoscaler_v2
   (all remaining types in any order)
9. kubernetes_namespace             →  kubernetes_namespace_v1
10. kubernetes_secret               →  kubernetes_secret_v1
11. kubernetes_service_account      →  kubernetes_service_account_v1
12. kubernetes_service              →  kubernetes_service_v1
13. kubernetes_config_map           →  kubernetes_config_map_v1
14. kubernetes_deployment           →  kubernetes_deployment_v1
15. kubernetes_daemonset            →  kubernetes_daemonset_v1
16. kubernetes_stateful_set         →  kubernetes_stateful_set_v1
17. kubernetes_ingress              →  kubernetes_ingress_v1
18. kubernetes_network_policy       →  kubernetes_network_policy_v1
19. kubernetes_storage_class        →  kubernetes_storage_class_v1
20. kubernetes_pod                  →  kubernetes_pod_v1
21. kubernetes_resource_quota       →  kubernetes_resource_quota_v1
22. kubernetes_cron_job             →  kubernetes_cron_job_v1
```

When using an editor with replace-all or `sed`, run each substitution in this order.

---

## What Needs to Change

There are four distinct contexts where a resource type name appears in HCL.

### 1. Resource Declarations

```hcl
# Before
resource "kubernetes_role" "tools_role" {
  metadata { ... }
}

resource "kubernetes_role_binding" "tools_role_binding" {
  metadata { ... }
}

resource "kubernetes_namespace" "namespace" {
  for_each = toset(local.namespaces)
  metadata { name = each.key }
}

# After
resource "kubernetes_role_v1" "tools_role" {
  metadata { ... }
}

resource "kubernetes_role_binding_v1" "tools_role_binding" {
  metadata { ... }
}

resource "kubernetes_namespace_v1" "namespace" {
  for_each = toset(local.namespaces)
  metadata { name = each.key }
}
```

### 2. Data Source Declarations

```hcl
# Before
data "kubernetes_secret" "vault_default" {
  metadata {
    name      = kubernetes_secret.vault_default.metadata.0.name
    namespace = kubernetes_service_account.vault_default.metadata[0].namespace
  }
}

# After
data "kubernetes_secret_v1" "vault_default" {
  metadata {
    name      = kubernetes_secret_v1.vault_default.metadata.0.name
    namespace = kubernetes_service_account_v1.vault_default.metadata[0].namespace
  }
}
```

### 3. Attribute References (cross-resource)

All uses of `<resource_type>.<resource_name>.<attribute>` must be updated.

```hcl
# Before
role_ref {
  name = kubernetes_role.tools_role.metadata[0].name
}

subject {
  name      = kubernetes_service_account.cert_manager.metadata.0.name
  namespace = kubernetes_service_account.cert_manager.metadata.0.namespace
}

kubernetes_ca_cert = data.kubernetes_secret.vault_default.data["ca.crt"]
token_reviewer_jwt = data.kubernetes_secret.vault_default.data["token"]

annotations = {
  "kubernetes.io/service-account.name" = kubernetes_service_account.vault_default.metadata[0].name
}

# After
role_ref {
  name = kubernetes_role_v1.tools_role.metadata[0].name
}

subject {
  name      = kubernetes_service_account_v1.cert_manager.metadata.0.name
  namespace = kubernetes_service_account_v1.cert_manager.metadata.0.namespace
}

kubernetes_ca_cert = data.kubernetes_secret_v1.vault_default.data["ca.crt"]
token_reviewer_jwt = data.kubernetes_secret_v1.vault_default.data["token"]

annotations = {
  "kubernetes.io/service-account.name" = kubernetes_service_account_v1.vault_default.metadata[0].name
}
```

### 4. `depends_on` Arrays

```hcl
# Before
depends_on = [kubernetes_namespace.namespace]
depends_on = [kubernetes_secret.vault_secret, kubernetes_service_account.vault_default]

# After
depends_on = [kubernetes_namespace_v1.namespace]
depends_on = [kubernetes_secret_v1.vault_secret, kubernetes_service_account_v1.vault_default]
```

### 5. Third-party Resource Arguments (e.g., Vault auth backend roles)

These appear when other providers (like `vault`, `helm`) accept Kubernetes identifiers as strings derived from k8s resource attributes:

```hcl
# Before — vault_kubernetes_auth_backend_role
bound_service_account_names      = [kubernetes_service_account.vault_default.metadata[0].name]
bound_service_account_namespaces = [kubernetes_service_account.vault_default.metadata[0].namespace]

# After
bound_service_account_names      = [kubernetes_service_account_v1.vault_default.metadata[0].name]
bound_service_account_namespaces = [kubernetes_service_account_v1.vault_default.metadata[0].namespace]
```

### 6. Inside `kubernetes_manifest` blocks (do NOT rename these)

`kubernetes_manifest` uses raw Kubernetes API objects. The Kubernetes `kind` and `apiGroup` values inside these blocks are Kubernetes API fields, NOT Terraform resource type names. Leave them unchanged:

```hcl
# This stays exactly as-is — these are K8s API kinds, not Terraform types
resource "kubernetes_manifest" "vault_issuer_role" {
  manifest = {
    apiVersion = "rbac.authorization.k8s.io/v1"
    kind       = "Role"        # NOT a Terraform resource type
    metadata = {
      name      = "vault-issuer"
      namespace = "cert-manager"
    }
    rules = [...]
  }
}
```

However, any references TO Kubernetes resources FROM inside a manifest block DO need updating:

```hcl
resource "kubernetes_manifest" "vault_issuer_sa" {
  manifest = {
    ...
    serviceAccountRef = {
      # Before
      name = kubernetes_service_account.cert_manager.metadata.0.name
      # After
      name = kubernetes_service_account_v1.cert_manager.metadata.0.name
    }
  }
}
```

---

## sed Commands for Bulk Replacement

Run these in order from the directory containing your `.tf` files. Use `-i ''` on macOS, `-i` on Linux.

```bash
# macOS
SED="sed -i ''"
# Linux
SED="sed -i"

# Run in this exact order (longest/most-specific first)
$SED 's/kubernetes_cluster_role_binding\b/kubernetes_cluster_role_binding_v1/g' **/*.tf
$SED 's/kubernetes_role_binding\b/kubernetes_role_binding_v1/g' **/*.tf
$SED 's/kubernetes_cluster_role\b/kubernetes_cluster_role_v1/g' **/*.tf
$SED 's/kubernetes_role\b/kubernetes_role_v1/g' **/*.tf
$SED 's/kubernetes_persistent_volume_claim\b/kubernetes_persistent_volume_claim_v1/g' **/*.tf
$SED 's/kubernetes_persistent_volume\b/kubernetes_persistent_volume_v1/g' **/*.tf
$SED 's/kubernetes_pod_disruption_budget\b/kubernetes_pod_disruption_budget_v1/g' **/*.tf
$SED 's/kubernetes_horizontal_pod_autoscaler\b/kubernetes_horizontal_pod_autoscaler_v2/g' **/*.tf
$SED 's/kubernetes_namespace\b/kubernetes_namespace_v1/g' **/*.tf
$SED 's/kubernetes_secret\b/kubernetes_secret_v1/g' **/*.tf
$SED 's/kubernetes_service_account\b/kubernetes_service_account_v1/g' **/*.tf
$SED 's/kubernetes_service\b/kubernetes_service_v1/g' **/*.tf
$SED 's/kubernetes_config_map\b/kubernetes_config_map_v1/g' **/*.tf
$SED 's/kubernetes_deployment\b/kubernetes_deployment_v1/g' **/*.tf
$SED 's/kubernetes_daemonset\b/kubernetes_daemonset_v1/g' **/*.tf
$SED 's/kubernetes_stateful_set\b/kubernetes_stateful_set_v1/g' **/*.tf
$SED 's/kubernetes_ingress\b/kubernetes_ingress_v1/g' **/*.tf
$SED 's/kubernetes_network_policy\b/kubernetes_network_policy_v1/g' **/*.tf
$SED 's/kubernetes_storage_class\b/kubernetes_storage_class_v1/g' **/*.tf
$SED 's/kubernetes_pod\b/kubernetes_pod_v1/g' **/*.tf
$SED 's/kubernetes_resource_quota\b/kubernetes_resource_quota_v1/g' **/*.tf
$SED 's/kubernetes_cron_job\b/kubernetes_cron_job_v1/g' **/*.tf
```

> The `\b` word boundary prevents double-suffixing already-migrated `_v1` strings. Some systems may need `[[:<:]]` and `[[:>:]]` instead of `\b` — test with `grep` first.

---

## Verification After HCL Changes

Run this before touching state to confirm no deprecated references remain:

```bash
# Should return empty
grep -rn "resource \"kubernetes_[a-z_]*\"" . --include="*.tf" | grep -v "_v1\|_v2\|_manifest"
grep -rn "data \"kubernetes_[a-z_]*\"" . --include="*.tf" | grep -v "_v1\|_v2"
grep -rn "\bkubernetes_[a-z]*\." . --include="*.tf" | grep -v "_v1\.\|_v2\.\|_manifest\."
```

All three greps returning empty means the HCL transformation is complete.

---

## Common Pitfalls

**Double-renaming**: If a file already has some `_v1` types and some deprecated ones, ensure your substitution doesn't rename `_v1` → `_v1_v1`. The `\b` word boundary in sed prevents this (won't match `kubernetes_role_v1` with the `kubernetes_role` pattern because `_` is a word character).

**Partial cross-reference update**: Updating only the `resource "..."` declaration but missing attribute references elsewhere (e.g., in a different `.tf` file that imports an annotation or a Vault role config) causes Terraform errors after the HCL change. Always scan all `.tf` files, not just files with resource declarations.

**`kubernetes_manifest` internals**: The kind/apiGroup strings inside `manifest = {}` blocks are Kubernetes API values, not Terraform types. They must NOT be renamed.

**`kubernetes_horizontal_pod_autoscaler` maps to `_v2`**, not `_v1`. Using `_v1` will fail at plan time.
