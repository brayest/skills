# Infrastructure Setup

## Vault Configuration (CLI)

### Enable Kubernetes Auth Method

```bash
vault auth enable -path="kubernetes-dev-myapp" kubernetes

vault write auth/kubernetes-dev-myapp/config \
  kubernetes_host="https://kubernetes.default.svc" \
  kubernetes_ca_cert=@/path/to/ca.crt \
  token_reviewer_jwt="<reviewer-jwt>"
```

### Create Policy

```hcl
# policy: myapp-dev-read
path "kv/data/ORG/DEV/MYAPP" {
  capabilities = ["read"]
}

path "kv/metadata/ORG/DEV/MYAPP" {
  capabilities = ["read", "list"]
}
```

```bash
vault policy write myapp-dev-read myapp-dev-read.hcl
```

### Create Role

```bash
vault write auth/kubernetes-dev-myapp/role/dev-myapp \
  bound_service_account_names="vault-auth-dev-myapp" \
  bound_service_account_namespaces="myapp" \
  policies="myapp-dev-read" \
  ttl=1h
```

## Kubernetes Manifests

### ServiceAccount

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: vault-auth-dev-myapp
  namespace: myapp
automountServiceAccountToken: true
```

### Deployment (relevant spec)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: myapp
spec:
  template:
    spec:
      serviceAccountName: vault-auth-dev-myapp
      containers:
        - name: myapp
          env:
            - name: VAULT_ADDR
              value: "http://vault.internal:8200"
            - name: VAULT_ROLE
              value: "dev-myapp"
            - name: VAULT_PATH
              value: "ORG/DEV/MYAPP"
            - name: VAULT_MOUNT_POINT
              value: "kv"
            - name: VAULT_K8S_AUTH_MOUNT_POINT
              value: "kubernetes-dev-myapp"
            - name: VAULT_TIMEOUT
              value: "30"
            - name: VAULT_MAX_RETRIES
              value: "3"
            - name: VAULT_RETRY_DELAY
              value: "5"
```

### Helm Templating (multi-environment)

```yaml
# values.yaml
settings:
  environment: dev
  serviceaccount: vault-auth-dev-myapp

# deployment.yaml
spec:
  template:
    spec:
      serviceAccountName: {{ .Values.settings.serviceaccount }}
      containers:
        - name: myapp
          env:
            - name: VAULT_ROLE
              value: "{{ .Values.settings.environment }}-myapp"
            - name: VAULT_PATH
              value: "ORG/{{ .Values.settings.environment | upper }}/MYAPP"
            - name: VAULT_K8S_AUTH_MOUNT_POINT
              value: "kubernetes-{{ .Values.settings.environment }}-myapp"
```

## Local Development

Vault is disabled when `VAULT_ADDR` is not set. For local development, set secrets directly:

```yaml
# docker-compose.yml
services:
  myapp:
    environment:
      # VAULT_ADDR intentionally absent — Vault disabled
      - AWS_DEFAULT_REGION=us-east-1
      - DATABASE_URL=postgresql://localhost:5432/mydb
```

The application reads them via `os.getenv()` the same way it would after Vault injection.
