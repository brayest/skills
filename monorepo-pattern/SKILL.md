---
name: monorepo-pattern
description: "Use this skill for application monorepos that consolidate code, Helm chart, Terragrunt-managed Terraform, and CI/CD under a single tree, with a `services = {}` map in tfvars as the source of truth for all services. Trigger on: adding a new service, bootstrapping a new monorepo, renaming a service, debugging IRSA / Vault auth / K8s ServiceAccount wiring, authoring per-service Helm values, wiring change-detection + build-matrix + deploy-matrix in GitHub Actions, structuring `infrastructure/<env>` + `infrastructure/environment` + `infrastructure/modules`, cross-account ECR via provider alias, or local dev with `compose.yaml` profiles. Also trigger on phrases like 'add a service to the monorepo', 'register a service', 'per-service values', 'service map', 'service-wiring module', 'IRSA role for service', 'paths-filter matrix' — even if the user does not say 'monorepo' explicitly."
---

# Monorepo Pattern

## What This Skill Covers

Application monorepos following this pattern co-locate four concerns under one tree:

1. **Infrastructure** — a Terragrunt-managed Terraform stack lives at `applications/<app>/infrastructure/`. It owns everything app-specific (K8s namespaces, IRSA roles, Vault auth, S3 buckets, event bus integrations) and reads outputs from a base environment stack (EKS, VPC, DNS, hosted zones, runner IAM roles) via `terraform_remote_state`.
2. **Deployment** — a single parameterized Helm chart at `charts/<chart>/` is reused for every service. Per-service overrides live as separate values files in `charts/values/<service>.yaml`.
3. **CI/CD** — `.github/workflows/ci-cd.yml` uses `dorny/paths-filter` for change detection, then a Bash matrix builder fans out build and deploy jobs per changed service.
4. **Local dev** — `compose.yaml` with named profiles brings up dependencies (DB, message broker, secret-store mock, etc.). `scripts/*.sh` handle bootstrap (migrations, seed data).

A single `services = {}` map in `infrastructure/<env>/terraform.tfvars` is the **source of truth**. Every service in the monorepo is registered there, and a `for_each` over that map drives the per-service wiring module that creates K8s ServiceAccount, IRSA role, Vault auth backend, and DNS records.

---

## Reference Files

Load these as needed:

- `references/architecture.md` — Infrastructure tree layout, `terragrunt.hcl` / `terraform.tfvars` shape, remote state inputs, provider configuration (including cross-account aliases), the service-wiring module contract, IAM decentralization, stack-level resources, safe-refactor patterns (`moved {}`, `try()`), Vault KV path convention.
- `references/helm-patterns.md` — One parameterized chart serving many services, `_helpers.tpl` Vault wiring helpers, `values.yaml` defaults, per-service values templates (HTTP, queue worker, GPU worker, frontend), immutable-selector gotcha, `helm upgrade --install` command shape.
- `references/cicd-patterns.md` — Branch → env mapping, paths-filter change detection, matrix builder, build job (BuildKit S3 cache, ECR), deploy job (AWS CLI non-root install gotcha, helm upgrade), integration test, multi-arch runners.
- `references/local-dev.md` — `compose.yaml` profiles, health checks, bootstrap scripts, AWS profile mounting.

---

## Repository Layout

```
applications/<app>/
├── .github/workflows/ci-cd.yml      # detect → build matrix → deploy matrix
├── infrastructure/
│   ├── <env>/                       # one folder per env: dev/, qa/, prod/
│   │   ├── terragrunt.hcl           # state key, backend, source = ../environment
│   │   └── terraform.tfvars         # services = {} map lives here, per env
│   ├── environment/                 # the root TF module — shared across envs
│   │   ├── backend.tf               # remote_state from base environment stack
│   │   ├── providers.tf             # aws, aws.utility, kubernetes, vault, ...
│   │   ├── variables.tf             # services var, bucket names, domains
│   │   ├── locals.tf                # derived locals (namespaces, tags)
│   │   ├── kubernetes.tf            # for_each over services map → wiring module
│   │   ├── iam.tf                   # policy docs + aws_iam_policy resources
│   │   ├── storage.tf               # S3 buckets, bucket policies
│   │   ├── <feature>.tf             # stack-level features (event bus, gateways)
│   │   └── outputs.tf
│   └── modules/                     # local TF modules (event-bus connectors, etc.)
├── charts/
│   ├── <chart>/                     # ONE parameterized chart, reused for all services
│   │   ├── Chart.yaml
│   │   ├── values.yaml              # safe defaults
│   │   └── templates/
│   └── values/
│       └── <service>.yaml           # per-service overrides
├── services/                        # service source code (one subdir each)
│   ├── <service-a>/Dockerfile
│   └── <service-b>/Dockerfile
├── compose.yaml                     # Docker Compose with named profiles
└── scripts/                         # bootstrap scripts (db migrate, seed, ...)
```

---

## Adding a New Service to an Existing Monorepo

### Step 1 — Register in `terraform.tfvars`

Add the service to the `services` map in `infrastructure/<env>/terraform.tfvars`:

```hcl
services = {
  # existing entries...
  <service-name> = {
    namespace   = "<namespace>"
    public      = false   # true → creates public Route53 DNS record
    internal    = true    # true → creates internal Route53 DNS record
    credentials = false   # true → DB user + Secrets Manager secret
    rotation    = false   # true → wires Secrets Manager rotation
  }
}
```

The map key becomes the Kubernetes ServiceAccount name suffix, the Vault auth mount path suffix, the Vault KV path leaf, the Helm release name, and the CI/CD matrix entry name. **Choose carefully — renaming requires migrating Vault secrets and reapplying TF.**

Repeat in each environment's tfvars where the service should exist. Environments can have different service sets.

### Step 2 — Add IAM Policy (if needed)

In `infrastructure/environment/iam.tf`, add `aws_iam_policy_document` + `aws_iam_policy` for any new AWS service access. Do not create IAM roles here — the wiring module creates them.

Wire the policy ARN into the wiring-module call via a map in `kubernetes.tf` (e.g., `local.service_policy[each.key]` → `policy_arns`).

### Step 3 — Apply Terraform

```bash
cd applications/<app>/infrastructure/<env>
terragrunt apply
```

This creates the K8s ServiceAccount, IRSA role, Vault auth backend + role + policy, and DNS records for the new service.

### Step 4 — Write Vault Secrets

```bash
vault kv put kv/<ORG>/<ENV>/<SERVICE-NAME-UPPER> \
  KEY1=value1 \
  KEY2=value2
```

The Vault policy created by the wiring module grants read on this exact path plus a shared org-level path.

### Step 5 — Create Helm Values File

Create `charts/values/<service-name>.yaml`. The file name **must match the tfvars map key**. See `references/helm-patterns.md` for templates by service type (HTTP, queue worker, GPU worker, frontend).

### Step 6 — Wire CI/CD

In `.github/workflows/ci-cd.yml`:

1. Add filters in `detect-changes`:
   ```yaml
   <service-name>: ['services/<service-name>/**']
   <service-name>-values: ['charts/values/<service-name>.yaml']
   ```
2. Add the corresponding env vars in the `set-matrix` step.
3. Add a matrix entry in the Bash matrix builder (see `references/cicd-patterns.md`).
4. If the service has an ingress, add a domain-injection branch in the deploy step.

---

## Bootstrapping a New Monorepo

1. **Repo scaffold** — copy the layout above. Pick a `<chart>` name; one chart can serve all backend services. A second chart is justified only for fundamentally different runtime profiles (e.g., a frontend nginx chart).

2. **Terragrunt files per env** — set `layer` (becomes the state key prefix), `identifier`, region, and backend bucket/lock-table names in each `infrastructure/<env>/terragrunt.hcl`.

3. **`providers.tf`** — declare `aws`, `kubernetes` (wired to EKS via remote-state outputs), `vault`, `postgresql` if used. Declare an `aws.utility` alias with `assume_role` for any resource that lives in a separate account (e.g., ECR repositories in a utility account).

4. **`backend.tf`** — add `data "terraform_remote_state"` blocks for the base environment stack (and any other stacks whose outputs you consume — e.g., a tools stack with the cluster's ingress endpoints).

5. **`variables.tf` + tfvars** — declare a `services` variable typed as `map(object({...}))`. Each env's tfvars declares its own service set.

6. **`locals.tf`** — derive a `service_namespaces` set, tags, and any other helpers off `var.services`. Pull cluster/VPC/runner config from remote-state outputs.

7. **`kubernetes.tf`** — create `kubernetes_namespace_v1` per unique namespace; declare `module "services"` with `for_each = var.services` pointed at the service-wiring module.

8. **`iam.tf`** — define scoped policy documents for each AWS service the app uses.

9. **CI/CD** — copy `.github/workflows/ci-cd.yml` from the reference and wire matrix entries for the initial services.

10. **Local dev** — write `compose.yaml` with at least a `common` profile bringing up the standard dependencies. See `references/local-dev.md`.

---

## Renaming a Service

A rename touches four systems. Coordinate them to avoid downtime:

1. **Terraform key** (`terraform.tfvars`) — add the new key alongside the old (do not delete the old yet). Run `terragrunt apply` to provision the new K8s SA + Vault infra. Use `moved {}` blocks in TF to preserve any hard-coded resources (e.g., `kubernetes_namespace_v1`) that should not be recreated.
2. **Vault secrets** — copy from old path to new path, verify, then delete old:
   ```bash
   vault kv get -format=json kv/<ORG>/<ENV>/<OLD-NAME> | \
     jq -c '.data.data' | \
     vault kv put kv/<ORG>/<ENV>/<NEW-NAME> -
   vault kv get kv/<ORG>/<ENV>/<NEW-NAME>
   vault kv metadata delete kv/<ORG>/<ENV>/<OLD-NAME>
   ```
3. **Helm values** — rename `charts/values/<old>.yaml` → `charts/values/<new>.yaml`. If the Deployment already exists, set `settings.selectorService: <old-name>` in the new values file to preserve the immutable pod selector label. See `references/helm-patterns.md`.
4. **CI/CD** — update filter keys, env vars, and matrix entries. If both names need to deploy in parallel during cutover, add both matrix entries temporarily.

**Parallel-name cutover idioms** for downstream TF resources that reference per-service module outputs:

```hcl
# Bucket policy referencing both old and new module keys
identifiers = compact([
  try(module.services["<old-name>"].iam_role_arn, ""),
  try(module.services["<new-name>"].iam_role_arn, ""),
])

# Regex-based IAM role discovery when a downstream resource (e.g., DynamoDB policy)
# must grant access under either name
data "aws_iam_roles" "service_clients" {
  name_regex = ".*<service-stem>.*"
}
```

Remove the parallel entries once cutover is complete.

---

## Key Invariants

- **Map key is the canonical name.** The key in `services = {}` is the K8s SA name suffix (`vault-auth-<env>-<key>`), the Vault auth mount (`kubernetes-<env>-<key>`), the Vault KV path leaf, the Helm release name, the values file basename, and the CI/CD matrix entry name. Drift breaks pod startup.
- **IAM roles are never declared in `iam.tf`.** Only policy documents + `aws_iam_policy`. Roles are created inside the service-wiring module from the OIDC provider URL.
- **Policy attachment is per-service.** Use a `local.service_policy[each.key]` mapping in `kubernetes.tf` so each service receives only the policies it needs.
- **Cross-account access uses provider aliases with `assume_role`.** Never use access keys.
- **`domains[0]` is injected at deploy time** — the domain suffix changes per environment, so it should not be hardcoded in values files.
- **BuildKit S3 cache key is per-service.** A shared cache key collides on layer hashes.
- **Self-hosted K8s runners run as non-root.** Install CLI tools to `$HOME`, never `/usr/local`.
- **Environments can have different service sets.** The `services = {}` map is per-env tfvars, not global.

---

## Debugging Vault Auth Failures

When pods are in `CrashLoopBackOff` with a Vault auth error:

```bash
# Which SA is the pod requesting?
kubectl get pod <pod> -n <namespace> -o yaml | grep serviceAccountName

# Does that SA exist?
kubectl get sa vault-auth-<env>-<service> -n <namespace>

# Does the Vault auth backend exist?
vault auth list | grep kubernetes-<env>-<service>

# Is the role bound correctly?
vault read auth/kubernetes-<env>-<service>/role/<env>-<service>

# Does the KV path exist?
vault kv get kv/<ORG>/<ENV>/<SERVICE-UPPER>
```

If the SA or Vault auth backend is missing → `terragrunt apply` in `infrastructure/<env>/`. If the KV path is missing → write it with `vault kv put`. If the SA exists but the pod still fails → check that the values file's `settings.vaultService` matches the tfvars map key (only relevant during a rename).
