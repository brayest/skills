#!/usr/bin/env bash
# migrate_k8s_resources_v1.sh
#
# Migrates deprecated kubernetes Terraform provider resource types to their
# _v1 equivalents using state rm + import (moved blocks are not supported
# for cross-type migrations by the kubernetes provider).
#
# Usage:
#   ./migrate_k8s_resources_v1.sh             # execute migration
#   ./migrate_k8s_resources_v1.sh --dry-run   # show plan without mutating state
#
# Run from the Terraform or Terragrunt working directory.
# For Terragrunt multi-env setups, run once per environment wrapper (dev/, qa/, prod/).
#
# Idempotent: resources already on _v1 types are skipped automatically.
# Requires: terraform or terragrunt in PATH, authenticated provider credentials.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
  echo "[DRY RUN] No state will be modified."
  echo ""
fi

# Auto-detect terraform vs terragrunt
if [ -f "terragrunt.hcl" ]; then
  TF_CMD="terragrunt"
  # Prevent terragrunt interactive prompts from blocking the script
  export TG_NON_INTERACTIVE=true
else
  TF_CMD="terraform"
fi
echo "==> Using: $TF_CMD"

# Deprecated resource types (non-_v1).
# The regex uses word-boundary-like anchors: starts at line beginning,
# ends at the first dot, ensuring kubernetes_role does not match
# kubernetes_role_binding entries (different suffix before the dot).
DEPRECATED_TYPES_REGEX="^(kubernetes_cluster_role_binding|kubernetes_cluster_role|kubernetes_role_binding|kubernetes_role|kubernetes_namespace|kubernetes_secret|kubernetes_service_account|kubernetes_service|kubernetes_config_map|kubernetes_deployment|kubernetes_daemonset|kubernetes_stateful_set|kubernetes_ingress|kubernetes_network_policy|kubernetes_persistent_volume_claim|kubernetes_persistent_volume|kubernetes_storage_class|kubernetes_pod_disruption_budget|kubernetes_pod|kubernetes_resource_quota|kubernetes_cron_job|kubernetes_horizontal_pod_autoscaler)\."

# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

echo "==> Discovering deprecated kubernetes resources in state..."

resources=$(
  $TF_CMD state list 2>/dev/null \
    | grep -E "$DEPRECATED_TYPES_REGEX" \
    | grep -v "_v1\." \
    || true
)

if [ -z "$resources" ]; then
  echo "Nothing to migrate — all kubernetes resources are already on _v1 types."
  exit 0
fi

count=$(echo "$resources" | wc -l | tr -d ' ')
echo "Found $count resource(s) to migrate:"
echo "$resources" | while IFS= read -r r; do echo "  - $r"; done
echo ""

# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------

# Cluster-scoped resources use just the resource name as import ID.
# Namespaced resources use namespace/name.
is_cluster_scoped() {
  local type="$1"
  case "$type" in
    kubernetes_namespace | \
    kubernetes_cluster_role | \
    kubernetes_cluster_role_binding | \
    kubernetes_persistent_volume | \
    kubernetes_storage_class)
      return 0 ;;
    *)
      return 1 ;;
  esac
}

# horizontal_pod_autoscaler maps to v2, not v1
target_suffix() {
  local type="$1"
  case "$type" in
    kubernetes_horizontal_pod_autoscaler) echo "_v2" ;;
    *) echo "_v1" ;;
  esac
}

# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

# FD3 carries the resource list so every command in the loop body
# gets a clean stdin and cannot accidentally drain the resource list.
# IMPORTANT: Using `echo "$resources" | while read` would share stdin
# with all commands inside the loop, causing terragrunt/terraform to
# consume resource lines when reading stdin for prompts/input.
while IFS= read -r from <&3; do
  type="${from%%.*}"
  rest="${from#*.}"
  suffix=$(target_suffix "$type")
  to="${type}${suffix}.${rest}"

  echo "── $from"
  echo "   → $to"

  # Read current state entry to extract name and namespace.
  # The `|| true` on grep pipelines prevents `set -euo pipefail` from
  # killing the script when grep finds no match (exit code 1).
  # This happens for cluster-scoped resources like kubernetes_namespace
  # which have no `namespace` attribute in their state.
  raw=$($TF_CMD state show "$from" 2>/dev/null)

  name=$(echo "$raw" | grep -E '^\s+name\s+=' | head -1 | awk -F'"' '{print $2}' || true)
  namespace=$(echo "$raw" | grep -E '^\s+namespace\s+=' | head -1 | awk -F'"' '{print $2}' || true)

  if is_cluster_scoped "$type"; then
    import_id="$name"
  else
    import_id="${namespace}/${name}"
  fi

  echo "   import_id: $import_id"

  if [ "$DRY_RUN" = "true" ]; then
    echo "   [DRY RUN] would run: $TF_CMD state rm '$from'"
    echo "   [DRY RUN] would run: $TF_CMD import '$to' '$import_id'"
  else
    $TF_CMD state rm "$from"
    $TF_CMD import "$to" "$import_id"
    echo "   ✓ done"
  fi

  echo ""
done 3<<< "$resources"

echo "==> Migration complete."
if [ "$DRY_RUN" = "false" ]; then
  echo "    Run: $TF_CMD plan"
  echo "    Expected: no changes for any migrated resource."
fi
