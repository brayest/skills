# Helm Chart Patterns

## One Chart, Many Values Files

A single parameterized Helm chart serves every service in the monorepo. Per-service overrides live as separate values files; defaults stay safe and minimal.

```
charts/
├── <chart>/                       # The one chart, reused by all services
│   ├── Chart.yaml
│   ├── values.yaml                # Sensible defaults — optional features disabled by default
│   └── templates/
│       ├── _helpers.tpl           # Name helpers, Vault wiring helpers, labels
│       ├── deployment.yaml        # Main workload
│       ├── service.yaml           # ClusterIP (conditional on service.enabled)
│       ├── ingress.yaml           # Ingress (conditional on ingress.enabled)
│       └── hpa.yaml               # HPA on CPU + memory (conditional on hpa.enabled)
└── values/
    ├── <service-a>.yaml           # Per-service overrides — only what differs from defaults
    ├── <service-b>.yaml
    └── <service-c>.yaml
```

A second chart is justified only when two service classes have fundamentally different runtime shapes — e.g., a frontend nginx chart vs. a backend service chart. Even then, lean toward parameterizing one chart before splitting.

---

## `Chart.yaml`

```yaml
apiVersion: v2
name: <chart>
description: Generic service chart — reused for all services in this monorepo
version: 0.1.0
appVersion: 1.0.0
keywords: [backend, generic]
```

Keep `version` and `appVersion` static. Image versioning is driven by `image.tag` set at deploy time, not by chart versioning.

---

## `_helpers.tpl` — The Vault Wiring Contract

Three template helpers govern how the chart hooks into the K8s ServiceAccount and Vault auth backend that Terraform provisioned. The helpers' values must match the service-wiring module's naming exactly, or pods will fail to authenticate.

```yaml
{{/*
Release name — drives Deployment name, Service name, Ingress name, HPA name.
*/}}
{{- define "<chart>.release" -}}
{{- .Release.Name }}
{{- end }}

{{/*
Vault service identifier — defaults to release name. Override via settings.vaultService
ONLY during a service rename, to keep pods authenticating against the old Vault infra
while new infra is provisioned. Must match the Terraform map key for this service.

This name drives:
  - Kubernetes ServiceAccount: vault-auth-<env>-<vaultService>
  - Vault auth mount:          kubernetes-<env>-<vaultService>
  - Vault KV path:             <ORG>/<ENV>/<vaultService upper>
  - Vault role name:           <env>-<vaultService>
*/}}
{{- define "<chart>.vaultService" -}}
{{- default .Release.Name .Values.settings.vaultService }}
{{- end }}

{{/*
Selector service — IMMUTABLE after first deploy. Used as the pod selector label.
If a Deployment was first deployed under a different release name (rename case),
set settings.selectorService to the original name to keep the selector valid.
*/}}
{{- define "<chart>.selectorService" -}}
{{- default .Release.Name .Values.settings.selectorService }}
{{- end }}

{{/*
Standard labels applied to all resources.
*/}}
{{- define "<chart>.labels" -}}
app: {{ include "<chart>.selectorService" . }}
chart: {{ .Chart.Name }}-{{ .Chart.Version }}
release: {{ .Release.Name }}
environment: {{ .Values.settings.environment | default "dev" }}
{{- end }}
```

### Vault Env Vars in `deployment.yaml`

```yaml
spec:
  serviceAccountName: vault-auth-{{ .Values.settings.environment }}-{{ include "<chart>.vaultService" . }}

  containers:
    env:
    - name: VAULT_ROLE
      value: "{{ .Values.settings.environment }}-{{ include "<chart>.vaultService" . }}"
    - name: VAULT_PATH
      value: "<ORG>/{{ .Values.settings.environment | upper }}/{{ include "<chart>.vaultService" . | upper }}"
    - name: VAULT_K8S_AUTH_MOUNT_POINT
      value: "kubernetes-{{ .Values.settings.environment }}-{{ include "<chart>.vaultService" . }}"
    - name: VAULT_ADDR
      value: "{{ .Values.vault.address }}"
```

All four values must align with what the service-wiring module created. A mismatch surfaces as a pod-side Vault auth failure.

---

## `values.yaml` — Default Structure

Defaults are minimal and safe. All optional features default to disabled.

```yaml
replicaCount: 1

settings:
  host: ""                    # Required override in per-service values file
  environment: dev            # Overridden by --set settings.environment=<env> at deploy
  nodeSelector: default       # Maps to a Karpenter / node-pool label
  # vaultService: ""          # Only set during a service rename
  # selectorService: ""       # Only set when the selector must differ from the release name

image:
  repository: ""              # Set by CI/CD via --set image.repository=<ecr-repo>
  tag: latest                 # Set by CI/CD via --set image.tag=<sha>
  pullPolicy: Always

service:
  enabled: true               # Disable for pure queue/Kafka workers
  port: 8000
  targetPort: 8000

command: []                   # Use Dockerfile CMD by default
observabilityCommand: []      # Used when observability.enabled = true

health:
  enabled: true               # Disable for headless workers
  path: /health
  startup:
    initialDelaySeconds: 30
    periodSeconds: 10
    failureThreshold: 30
  readiness:
    initialDelaySeconds: 10
    periodSeconds: 5
    failureThreshold: 5
  liveness:
    initialDelaySeconds: 60
    periodSeconds: 15
    failureThreshold: 3

ingress:
  enabled: false              # Enable for services exposing HTTP externally
  path: /

domains: []                   # ["<service>.<internal-domain-suffix>"] — injected at deploy

tls: []
tlsPrivate: []                # [{ secretName: "...", hosts: ["..."] }] for internal TLS

observability:
  enabled: false              # Set to true at deploy for non-dev environments
  llm: false                  # Enables LLM tracing for AI workloads

resources:
  limits:
    cpu: "1"
    memory: "1Gi"
  requests:
    cpu: "500m"
    memory: "512Mi"

hpa:
  enabled: true
  minReplicas: 1
  maxReplicas: 10
  prodMinReplicas: 1          # Used when settings.environment == "prod"
  targetCPUUtilizationPercentage: 60
  targetMemoryUtilizationPercentage: 95

shm:                          # Shared memory — GPU workloads only
  enabled: false
  sizeLimit: "1Gi"

tolerations: []
podAnnotations: {}            # e.g., karpenter.sh/do-not-disrupt: "true"

vault:
  address: ""                 # Overridden by CI/CD or per-service file if needed
```

---

## Per-Service Values Templates

Each service gets one file in `charts/values/`. Only override what differs from defaults.

### HTTP / API Service

```yaml
settings:
  host: <service>
  nodeSelector: default

image:
  tag: api-latest             # Tag prefix; CI/CD appends the SHA

service:
  enabled: true
  port: 8000

observabilityCommand: ["<runtime-wrapper>", "<entrypoint>", "<args...>"]

health:
  enabled: true
  path: /health

ingress:
  enabled: true
  path: /

# domains[0] is injected at deploy time via --set; do not hardcode the env suffix here

hpa:
  minReplicas: 1
  maxReplicas: 10
  prodMinReplicas: 2
```

### Queue / Kafka Worker (Headless)

```yaml
settings:
  host: <service>
  nodeSelector: default

image:
  tag: <service>-latest

service:
  enabled: false              # No HTTP endpoint

command: ["<entrypoint>", "<args...>"]
observabilityCommand: ["<runtime-wrapper>", "<entrypoint>", "<args...>"]

health:
  enabled: false              # No health probes

observability:
  llm: true                   # If this worker calls LLMs

hpa:
  minReplicas: 4
  maxReplicas: 20
```

### GPU Worker

```yaml
settings:
  host: <service>
  nodeSelector: gpu

image:
  tag: <service>-latest

service:
  enabled: false

resources:
  limits:
    cpu: "3500m"
    memory: "15Gi"
    nvidia.com/gpu: "1"
  requests:
    cpu: "3000m"
    memory: "13Gi"
    nvidia.com/gpu: "1"

tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
  - key: dedicated
    operator: Equal
    value: gpu-workloads
    effect: NoSchedule

shm:
  enabled: true
  sizeLimit: "8Gi"

podAnnotations:
  karpenter.sh/do-not-disrupt: "true"
```

### Frontend (nginx / static)

```yaml
settings:
  host: <service>

image:
  tag: ui-latest

# domains[0] is injected at deploy time

env:
  backendApiUrl: http://<backend-service>:8000
  backendApiHost: <backend-service>:8000
```

---

## Immutable Selector Gotcha

`Deployment.spec.selector` is immutable after the Deployment is created. A rename that changes the release name (and therefore the default `app:` label) will be rejected by the API server. Two options:

1. **Preserve the old selector** — set `settings.selectorService: <old-name>` in the renamed service's values file. The selector keeps the old label; the release name itself can change. Once cutover is complete and the Deployment can be safely recreated, drop the override.
2. **Delete and recreate** — `kubectl delete deployment <old-name> -n <namespace>` before deploying with the new name. Causes brief downtime; usually not worth it for a production service.

The `selectorService` helper handles option 1 cleanly through the `_helpers.tpl` plumbing above.

---

## `helm upgrade --install` Command

```bash
helm upgrade --install <release-name> ./charts/<chart> \
  --values ./charts/values/<service>.yaml \
  --namespace <namespace> \
  --create-namespace \
  --set image.repository=<ecr-repo> \
  --set image.tag=<image-tag> \
  --set settings.environment=<env> \
  --set domains[0]=<service>.<internal-domain-suffix>
```

For services with internal TLS:

```bash
  --set tlsPrivate[0].secretName=<service>-tls-secret \
  --set tlsPrivate[0].hosts[0]=<service>.<internal-domain-suffix>
```

To enable observability in non-dev environments:

```bash
  --set observability.enabled=true
```

---

## Environment-Specific Helm Behavior

| Setting | dev | qa | prod |
|---|---|---|---|
| `observability.enabled` | false | true | true |
| `hpa.minReplicas` | `minReplicas` | `minReplicas` | `prodMinReplicas` |
| `image.tag` | `<prefix>-<sha>` | `<prefix>-<sha>` | `<prefix>-<sha>` |
| `settings.environment` | dev | qa | prod |

The `hpa.yaml` template checks `settings.environment` to pick between `minReplicas` and `prodMinReplicas`. The other variations are controlled by CI/CD at deploy time via `--set`.
