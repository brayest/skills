# Architecture & Flow

## System Architecture

```
┌─────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │  Pod (serviceAccountName: vault-auth-{env}-xx) │  │
│  │                                                │  │
│  │  /var/run/secrets/kubernetes.io/               │  │
│  │    serviceaccount/token  ← auto-mounted JWT    │  │
│  │                                                │  │
│  │  ┌──────────────────────────────────────────┐  │  │
│  │  │  Application Container                   │  │  │
│  │  │                                          │  │  │
│  │  │  1. Read SA token from filesystem        │  │  │
│  │  │  2. hvac.auth.kubernetes.login()         │  │  │
│  │  │  3. Fetch secrets from KV v2             │  │  │
│  │  │  4. Inject into os.environ               │  │  │
│  │  │  5. Application uses os.getenv()         │  │  │
│  │  └──────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────┘  │
│                         │                            │
└─────────────────────────┼────────────────────────────┘
                          │ hvac (HTTP)
                          ▼
                ┌───────────────────┐
                │   Vault Cluster   │
                │                   │
                │  K8s Auth Method  │
                │  KV v2 Engine     │
                └───────────────────┘
```

## Authentication Flow (Step by Step)

1. **Pod starts** — Kubernetes mounts the SA JWT at `/var/run/secrets/kubernetes.io/serviceaccount/token`
2. **Application reads the JWT** from the filesystem
3. **Application calls Vault's K8s login endpoint** — passing the JWT, the role name, and the auth mount point
4. **Vault validates the JWT** against the Kubernetes API server (token reviewer)
5. **Vault checks the role binding** — verifies the SA name and namespace match `bound_service_account_names` / `bound_service_account_namespaces`
6. **Vault issues a client token** with the role's attached policies and TTL
7. **Application uses the client token** to read secrets from KV v2
8. **Secrets are injected into `os.environ`** — the rest of the application uses `os.getenv()` normally

## Prerequisites

### Vault Side

1. **KV v2 secrets engine** mounted (e.g., at `kv`)
2. **Kubernetes auth method** enabled at a mount point (e.g., `kubernetes-{env}-{app}`)
3. **Vault role** configured to accept JWTs from the target K8s cluster, bound to specific SA names and namespaces, mapped to a read policy
4. **Vault policy** granting `read` on the KV v2 path

### Kubernetes Side

1. **ServiceAccount** created in the target namespace
2. **automountServiceAccountToken: true** (K8s default — no action needed unless explicitly disabled)
3. Vault K8s auth method configured with the cluster's API server CA and token reviewer JWT

## Naming Conventions

| Resource | Pattern | Example (dev) |
|----------|---------|---------------|
| ServiceAccount | `vault-auth-{env}-{app}` | `vault-auth-dev-myapp` |
| Vault K8s Auth Mount | `kubernetes-{env}-{app}` | `kubernetes-dev-myapp` |
| Vault Role | `{env}-{app}` | `dev-myapp` |
| KV v2 Path | `ORG/{ENV}/{APP}` | `ACME/DEV/MYAPP` |
| Vault Policy | `{app}-{env}-read` | `myapp-dev-read` |

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `VAULT_ADDR` | Yes (enables Vault) | Vault server URL | `http://vault.internal:8200` |
| `VAULT_ROLE` | Yes | Vault K8s auth role name | `dev-myapp` |
| `VAULT_PATH` | Yes | KV v2 secret path | `ORG/DEV/MYAPP` |
| `VAULT_MOUNT_POINT` | No (default: `kv`) | KV secrets engine mount | `kv` |
| `VAULT_K8S_AUTH_MOUNT_POINT` | Yes | K8s auth method mount point | `kubernetes-dev-myapp` |
| `VAULT_TIMEOUT` | No (default: `30`) | Connection timeout (seconds) | `30` |
| `VAULT_MAX_RETRIES` | No (default: `3`) | Max fetch retry attempts | `3` |
| `VAULT_RETRY_DELAY` | No (default: `5`) | Delay between retries (seconds) | `5` |
