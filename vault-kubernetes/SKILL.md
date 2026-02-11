---
name: vault-kubernetes
description: "This skill should be used when integrating HashiCorp Vault with Kubernetes-deployed services using the Kubernetes auth method. Provides the standard pattern for service account authentication, KV v2 secret retrieval, Helm chart configuration, and Python VaultSecretManager implementation. Covers Vault CLI setup, K8s manifests, hvac client code, and failure mode debugging."
---

# Vault + Kubernetes Authentication

## Overview

Standard pattern for integrating HashiCorp Vault with Kubernetes-deployed Python services. Secrets are fetched once at application startup via Kubernetes service account authentication, injected into environment variables, and consumed via `os.getenv()`. No Vault Agent sidecar — direct client integration using the `hvac` library.

## When to Use This Skill

- Adding Vault secret management to a new Kubernetes-deployed service
- Implementing `VaultSecretManager` in a Python application
- Configuring Helm charts with Vault environment variables and service accounts
- Setting up Vault Kubernetes auth method (roles, policies, auth mounts)
- Debugging Vault authentication failures in K8s pods (403, 404, token errors)
- Establishing naming conventions for Vault resources across environments

## Key Principles

1. **Startup-only fetch** — Secrets are loaded once at application startup, then accessed via `os.environ`. No polling, no persistent Vault connection.
2. **Kubernetes SA auth** — Authentication uses the pod's auto-mounted service account JWT. No API keys, no long-lived tokens.
3. **Fail-fast, fail-loud** — If Vault is enabled and any step fails (auth, fetch, validation), the application crashes immediately. No fallbacks, no defaults.
4. **Environment variable injection** — After fetching, secrets are injected into `os.environ` so the rest of the application is Vault-unaware.
5. **Conditional enable** — Vault is only active when `VAULT_ADDR` is set. Local development works without Vault by setting env vars directly.

## How to Use This Skill

### Architecture & Flow
To understand the overall system design, authentication flow, naming conventions, or environment variables, consult `references/architecture.md`.
- "How does K8s service account auth work with Vault?"
- "What naming convention to use for Vault roles and service accounts?"
- "What environment variables does the Vault client need?"

### Infrastructure Setup
To configure Vault (CLI), create K8s manifests, or set up Helm charts, consult `references/infrastructure-setup.md`.
- "How to enable Kubernetes auth method in Vault?"
- "What does the Vault policy HCL look like?"
- "How to template Vault env vars in a Helm deployment?"
- "How to set up local development without Vault?"

### Python Implementation
To implement the `VaultSecretManager` class, wire up the application entry point, or debug failure modes, consult `references/python-implementation.md`.
- "Give me the VaultSecretManager implementation"
- "How to initialize Vault at application startup?"
- "What exceptions does the Vault client raise?"
- "App crashes with VaultAuthenticationError — what to check?"

## Quick Reference — Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VAULT_ADDR` | Yes | — | Vault server URL (also acts as enable flag) |
| `VAULT_ROLE` | Yes | — | K8s auth role name |
| `VAULT_PATH` | Yes | — | KV v2 secret path |
| `VAULT_K8S_AUTH_MOUNT_POINT` | Yes | — | K8s auth method mount |
| `VAULT_MOUNT_POINT` | No | `kv` | KV engine mount |
| `VAULT_TIMEOUT` | No | `30` | Connection timeout (s) |
| `VAULT_MAX_RETRIES` | No | `3` | Fetch retry attempts |
| `VAULT_RETRY_DELAY` | No | `5` | Retry delay (s) |
