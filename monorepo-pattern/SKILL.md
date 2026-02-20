---
name: monorepo-pattern
description: "This skill should be used when creating, extending, or managing application monorepos in the BigTicket infrastructure system. Covers the full pattern: service registration in Terraform locals, IAM policy authoring, Vault/IRSA wiring via the btp_service_cross module, Helm chart structure (backend and frontend), per-service values files, and the GitHub Actions CI/CD pipeline (paths-filter change detection, ECR build matrix, helm deploy matrix). Use when adding a new service to an existing monorepo, bootstrapping a new monorepo, renaming services, or debugging any of the Vault/K8s/IAM integration layers."
---

# Monorepo Pattern

## What This Skill Covers

Application monorepos in this system follow a consistent pattern across three concerns:

1. **Infrastructure** — Terraform managed by Terragrunt, consuming outputs from lower layers (environment, utility)
2. **Deployment** — Helm charts (one generic backend chart, one frontend chart) with per-service values files
3. **CI/CD** — GitHub Actions with per-service change detection, ECR builds, and Helm deploys

The canonical reference implementation is `applications/btp-cope-extractor`.

---

## Reference Files

Load these references as needed:

- `references/architecture.md` — 4-layer Terragrunt hierarchy, remote state dependencies, btp_service_cross module, IAM decentralization, Vault path conventions
- `references/helm-patterns.md` — Chart structure, _helpers.tpl, values.yaml defaults, per-service values patterns, deploy command
- `references/cicd-patterns.md` — Change detection matrix, build job, deploy job, AWS CLI caching, multi-arch runners

---

## Adding a New Service to an Existing Monorepo

### Step 1 — Register in locals.tf

Add the service to the `{app}_services` map in `environment/locals.tf`:

```hcl
{service-name} = {
  public      = false          # true = creates public Route53 DNS record
  internal    = true           # true = creates internal Route53 DNS record
  credentials = false
  namespace   = "{namespace}"
  rotation    = false
}
```

The map key becomes the Kubernetes ServiceAccount name (`vault-auth-{env}-{key}`), the Vault auth mount (`kubernetes-{env}-{key}`), and the Vault KV path (`BTP/{ENV}/{KEY-UPPERCASED}`). Choose carefully — renaming requires migrating Vault secrets.

### Step 2 — Add IAM Policies (if needed)

In `environment/iam.tf`, add `aws_iam_policy_document` + `aws_iam_policy` for any new AWS service access. Do not create IAM roles here — those are created by the module.

Pass new policy ARNs to the module via `policy_arns` in `environment/kubernetes.tf`.

### Step 3 — Apply Terraform

```bash
cd applications/{app-name}/development
terragrunt apply
```

This creates the K8s ServiceAccount, Vault auth backend, IRSA role, and DNS records for the new service.

### Step 4 — Write Vault Secrets

```bash
vault kv put kv/BTP/{ENV}/{SERVICE-NAME-UPPER} \
  KEY=value \
  KEY2=value2
```

The Vault policy created by the module grants read on this exact path.

### Step 5 — Create Helm Values File

Create `charts/values/{service-name}.yaml`. The service name here **must match** the Terraform map key. See `references/helm-patterns.md` for per-service type patterns (HTTP service, worker, GPU worker, frontend).

### Step 6 — Update CI/CD

In `.github/workflows/ci-cd.yml`:

1. Add a filter in `detect-changes`:
   ```yaml
   {service-name}: ['{service-name}/**']
   {service-name}-values: ['charts/values/{service-name}.yaml']
   ```

2. Add env vars for the new filter outputs in the `set-matrix` step:
   ```yaml
   SERVICE_NAME: ${{ steps.changes.outputs.service-name }}
   SERVICE_NAME_VALUES: ${{ steps.changes.outputs.service-name-values }}
   ```

3. Add matrix entry logic in the bash matrix builder:
   ```bash
   if [[ "$SERVICE_NAME" == "true" || "$BACKEND_CHART" == "true" || "$SERVICE_NAME_VALUES" == "true" ]]; then
     entry=$(service_matrix "{service-name}" "{service-name}" "{tag-prefix}" "btp-runners" "backend" "false")
     BUILD_SERVICES+=("$entry")
     DEPLOY_SERVICES+=("$entry")
   fi
   ```

4. Add domain injection in the deploy step (if the service has an ingress).

---

## Bootstrapping a New Monorepo

When creating a new application monorepo from scratch, the structure mirrors `applications/btp-cope-extractor`:

1. **Repository structure**
   ```
   applications/{app-name}/
   ├── environment/           # Copy from existing app, adapt
   ├── development/terragrunt.hcl
   ├── qa/terragrunt.hcl
   ├── prod/terragrunt.hcl
   ├── charts/
   │   ├── backend/           # Copy chart from existing app
   │   ├── frontend/          # If UI service needed
   │   └── values/
   └── {service-dirs}/
   ```

2. **Terragrunt files** — Update `layer` name (becomes the S3 state key prefix), `identifier`, and bucket names

3. **providers.tf** — Wire Kubernetes provider to EKS via remote state; wire Vault to utility account

4. **backend.tf** — Add `data.terraform_remote_state` blocks for environment and utility layers

5. **locals.tf** — Define `{app}_services` map; assemble cluster_config and vpc_config from remote state outputs

6. **kubernetes.tf** — Create namespace + module loop over the services map

7. **iam.tf** — Define scoped policy documents for each AWS service the app uses

---

## Renaming a Service

Service rename requires coordinated changes across four systems:

1. **Terraform key** (`locals.tf`) — Change map key, run `terragrunt apply` to create new K8s SA + Vault infra
2. **Vault secrets** — Copy from old path to new path, then delete old (see `references/architecture.md` → "Migrating Vault Secrets")
3. **Helm values** — Rename `charts/values/{old-name}.yaml` → `charts/values/{new-name}.yaml`
4. **CI/CD** — Update filter keys, matrix entries, domain references, release name

**Avoid downtime**: Use `settings.vaultService: {old-name}` in the values file to keep pods authenticating against old Vault infra while new infra is being provisioned. Remove once Terraform is applied and secrets migrated.

**Immutable selectors**: If the Deployment already exists with the old name, use `settings.selectorService: {old-name}` to preserve the immutable pod selector label.

---

## Key Invariants

- Service name in `locals.tf` = Helm release name = Vault auth mount suffix = K8s SA name suffix
- `vault-auth-{env}-{service}` is the SA name that deployment.yaml requests; this must exist before pods start
- IAM roles are never defined in `iam.tf` — only policy documents and `aws_iam_policy` resources
- All services in the `for_each` module loop share the same `policy_arns` list
- `domains[0]` is injected at deploy time by CI/CD, not hardcoded in values files, because the suffix changes per environment
- AWS CLI must be installed to `$HOME/.aws-cli` on K8s runners (not `/usr/local/`) — tar cannot write to system paths as non-root
- BuildKit S3 cache key is per-service-name in the utility account cache bucket

---

## Debugging Vault Auth Failures

When pods are in `CrashLoopBackOff` due to Vault auth:

```bash
# Check which SA the pod is requesting
kubectl get pod {pod} -n {namespace} -o yaml | grep serviceAccountName

# Check if that SA exists
kubectl get sa vault-auth-{env}-{service} -n {namespace}

# Check if Vault auth backend exists
vault auth list | grep kubernetes-{env}-{service}

# Check Vault role
vault read auth/kubernetes-{env}-{service}/role/{env}-{service}

# Check KV path
vault kv get kv/BTP/{ENV}/{SERVICE-UPPER}
```

If SA or auth backend is missing → `terragrunt apply` in the environment layer.
If KV path is missing → `vault kv put kv/BTP/{ENV}/{SERVICE-UPPER} ...`.
