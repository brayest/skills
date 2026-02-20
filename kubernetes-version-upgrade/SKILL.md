---
name: kubernetes-version-upgrade
description: This skill should be used when upgrading the Terraform kubernetes provider and resolving deprecation warnings about non-versioned resource types (kubernetes_role, kubernetes_secret, kubernetes_namespace, kubernetes_service_account, kubernetes_cluster_role_binding, etc.) that need to be renamed to their _v1 equivalents. Covers HCL transformation of resource declarations and all cross-references, explains why moved blocks fail for cross-type state moves, and provides an automated state rm + import migration script for both terraform and terragrunt workflows.
---

# Kubernetes Provider Version Upgrade

## Problem

When upgrading the Terraform `hashicorp/kubernetes` provider to 2.x+, every non-versioned resource and data source triggers deprecation warnings:

```
Warning: Deprecated Resource
  with kubernetes_role.tools_role, on applications.tf line 306:
  resource "kubernetes_role" "tools_role" {
  Deprecated; use kubernetes_role_v1.
(and N more similar warnings)
```

These are not errors — the plan applies — but they must be resolved before the provider removes the old types entirely.

## Why `moved` Blocks Don't Work

The obvious HCL approach fails:

```hcl
# DOES NOT WORK — provider rejects cross-type state moves
moved {
  from = kubernetes_role.tools_role
  to   = kubernetes_role_v1.tools_role
}
```

Error:
```
Error: Move Resource State Not Supported
The "kubernetes_role_v1" resource type does not support moving resource
state across resource types.
```

This is a provider-level restriction. `moved` blocks require the destination provider schema to explicitly declare support for cross-type migration. The kubernetes provider does not support this. The same restriction applies to most other providers.

**The correct approach is `state rm` + `import`**, which bypasses provider schema validation by directly manipulating the state file.

## 3-Step Workflow

### Step 1 — Audit (read-only)

Find all deprecated types in the codebase before touching anything:

```bash
grep -rn "resource \"kubernetes_[a-z_]*\"" . --include="*.tf" | grep -v "_v1"
grep -rn "data \"kubernetes_[a-z_]*\"" . --include="*.tf" | grep -v "_v1"
```

Load `references/k8s-deprecated-types.md` to identify which types need migration and their import ID formats.

### Step 2 — HCL Transformation

Rename every deprecated type in every `.tf` file. Two categories to update:

**A. Declarations** (resource and data source blocks):
```hcl
# Before
resource "kubernetes_role" "my_role" { ... }
data "kubernetes_secret" "my_secret" { ... }

# After
resource "kubernetes_role_v1" "my_role" { ... }
data "kubernetes_secret_v1" "my_secret" { ... }
```

**B. Cross-references** (attribute refs, depends_on, annotations, vault role configs):
```hcl
# Before
depends_on = [kubernetes_namespace.namespace]
name = kubernetes_role.my_role.metadata[0].name
bound_service_account_names = [kubernetes_service_account.foo.metadata[0].name]

# After
depends_on = [kubernetes_namespace_v1.namespace]
name = kubernetes_role_v1.my_role.metadata[0].name
bound_service_account_names = [kubernetes_service_account_v1.foo.metadata[0].name]
```

**Critical ordering rule**: Always rename longer/more-specific types first to avoid substring replacement bugs:
1. `kubernetes_cluster_role_binding` → `kubernetes_cluster_role_binding_v1`
2. `kubernetes_role_binding` → `kubernetes_role_binding_v1`
3. `kubernetes_cluster_role` → `kubernetes_cluster_role_v1`
4. `kubernetes_role` → `kubernetes_role_v1`
5. All other types (order doesn't matter between them)

`kubernetes_manifest` is NOT deprecated — leave it unchanged.

Load `references/hcl-transformation-guide.md` for full before/after examples covering all cross-reference patterns.

### Step 3 — State Migration

Run the bundled script from the Terraform/Terragrunt working directory:

```bash
# Dry-run first — shows what will be migrated without making changes
./scripts/migrate_k8s_resources_v1.sh --dry-run

# Execute migration
./scripts/migrate_k8s_resources_v1.sh
```

The script:
- Auto-detects `terraform` vs `terragrunt` based on presence of `terragrunt.hcl`
- Lists all deprecated resource entries in state (idempotent — skips already-migrated `_v1` resources)
- Reads `state show` to extract `name` + `namespace` dynamically (handles `for_each` resources correctly)
- Builds the correct import ID per resource scope (cluster-scoped = name only, namespaced = namespace/name)
- Runs `state rm` then `import` for each resource

**Run the script once per environment** (e.g., once for `development/`, once for `qa/`, once for `prod/`).

## Terragrunt-Specific Gotchas

The migration script has been battle-tested with terragrunt and addresses these known issues:

### 1. stdin Consumption (pipe vs fd3)

**Never** pipe the resource list into `while read`:
```bash
# BROKEN — terragrunt commands inside the loop consume lines from the pipe
echo "$resources" | while IFS= read -r from; do
  terragrunt state rm "$from"   # steals stdin from the resource list
done
```

The script uses **file descriptor 3** to isolate the loop's input:
```bash
while IFS= read -r from <&3; do
  terragrunt state rm "$from"   # stdin (fd0) is free for terragrunt
done 3<<< "$resources"
```

### 2. `set -euo pipefail` + grep No-Match = Silent Death

`grep` returns exit code 1 when no match is found. With `pipefail`, this propagates through the entire pipeline. With `set -e`, the script dies silently — no error message, just stops.

This hits **cluster-scoped resources** like `kubernetes_namespace` which have no `namespace` attribute in their state output:
```bash
# BROKEN — grep finds no "namespace =" line, returns 1, script dies
namespace=$(echo "$raw" | grep -E '^\s+namespace\s+=' | head -1 | awk -F'"' '{print $2}')

# FIXED — || true prevents grep's exit code from killing the script
namespace=$(echo "$raw" | grep -E '^\s+namespace\s+=' | head -1 | awk -F'"' '{print $2}' || true)
```

### 3. Non-Interactive Mode

Set `TG_NON_INTERACTIVE=true` to prevent terragrunt from prompting for confirmation during `state rm` / `import` operations:
```bash
export TG_NON_INTERACTIVE=true
```

Note: The older `TERRAGRUNT_NON_INTERACTIVE` env var is deprecated and will be removed in future terragrunt versions.

## Verification

After running the script, plan should show zero changes for migrated resources:

```bash
terragrunt plan   # or: terraform plan
```

Expected output: no creates, updates, or destroys for any `kubernetes_*` resource.

If a resource shows as a plan change after migration:
- The import ID was wrong — check `state show` on the new address to verify correct import
- A cross-reference in HCL still uses the old type name — re-run the audit grep

## Bundled Resources

- `scripts/migrate_k8s_resources_v1.sh` — automated state rm + import migration script
- `references/k8s-deprecated-types.md` — complete deprecation map with import ID formats for all resource types
- `references/hcl-transformation-guide.md` — ordered replacement patterns and before/after examples for all cross-reference scenarios
