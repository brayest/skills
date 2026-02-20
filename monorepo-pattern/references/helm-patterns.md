# Helm Chart Patterns

## Chart Organization

```
charts/
├── backend/                  # Generic chart for Python/worker services
│   ├── Chart.yaml
│   ├── values.yaml           # Sensible defaults (all features disabled by default)
│   └── templates/
│       ├── _helpers.tpl      # Name helpers — vaultService, selectorService, labels
│       ├── deployment.yaml   # Main workload template
│       ├── service.yaml      # ClusterIP (conditional)
│       ├── ingress.yaml      # Nginx ingress (conditional)
│       └── hpa.yaml          # HPA with CPU + memory (conditional)
├── frontend/                 # Generic chart for UI services (nginx/Next.js)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── _helpers.tpl
│       ├── deployment.yaml
│       ├── service.yaml
│       ├── ingress.yaml
│       └── hpa.yaml
└── values/
    ├── {service-a}.yaml      # Per-service overrides — only what differs from defaults
    ├── {service-b}.yaml
    └── {service-c}.yaml
```

One chart serves many services. Per-service `values/` files only override what differs from `values.yaml` defaults.

---

## Chart.yaml Conventions

```yaml
apiVersion: v2
name: backend
description: {App} Backend Service — generic chart for all Python backend services
version: 0.1.0
appVersion: 1.0.0
keywords: [backend, python]
```

Keep `version` and `appVersion` static — image versioning is handled by `image.tag` set at deploy time.

---

## _helpers.tpl — Critical Helpers

Three helpers are fundamental to how services are wired to Vault and how immutable selectors are handled:

```yaml
{{/*
Release name — used for Deployment name, Service name, Ingress name, HPA name.
*/}}
{{- define "backend.release" -}}
{{- .Release.Name }}
{{- end }}

{{/*
Vault service name — defaults to release name (= Helm release = service name from CI/CD).
Override via settings.vaultService ONLY during service renames to avoid downtime.
This name must match the Kubernetes ServiceAccount created by btp_service_cross module:
  vault-auth-{env}-{vaultService}
And the Vault auth mount point:
  kubernetes-{env}-{vaultService}
*/}}
{{- define "backend.vaultService" -}}
{{- default .Release.Name .Values.settings.vaultService }}
{{- end }}

{{/*
Selector service — IMMUTABLE after first deploy. Used as the pod selector label.
If a Deployment was first deployed with a different release name (old service rename),
set this to the original release name to avoid "field is immutable" errors.
Override via settings.selectorService.
*/}}
{{- define "backend.selectorService" -}}
{{- default .Release.Name .Values.settings.selectorService }}
{{- end }}

{{/*
Standard labels applied to all resources.
*/}}
{{- define "backend.labels" -}}
app: {{ include "backend.selectorService" . }}
chart: {{ .Chart.Name }}-{{ .Chart.Version }}
release: {{ .Release.Name }}
environment: {{ .Values.settings.environment | default "dev" }}
{{- end }}
```

### Vault Wiring in deployment.yaml

The deployment template uses these helpers to populate Vault-related environment variables:

```yaml
spec:
  serviceAccountName: vault-auth-{{ .Values.settings.environment }}-{{ include "backend.vaultService" . }}

  containers:
    env:
    - name: VAULT_ROLE
      value: "{{ .Values.settings.environment }}-{{ include "backend.vaultService" . }}"
    - name: VAULT_PATH
      value: "BTP/{{ .Values.settings.environment | upper }}/{{ include "backend.vaultService" . | upper }}"
    - name: VAULT_K8S_AUTH_MOUNT_POINT
      value: "kubernetes-{{ .Values.settings.environment }}-{{ include "backend.vaultService" . }}"
    - name: VAULT_ADDR
      value: "http://vault.btp-utility.int/"
```

All four values must align with the Terraform-provisioned infrastructure from `btp_service_cross`.

---

## values.yaml — Default Structure

Keep defaults minimal and safe. All optional features default to disabled:

```yaml
replicaCount: 1

settings:
  host: ""                    # Required override in per-service values file
  environment: dev            # Overridden by --set settings.environment={ENVIRONMENT} at deploy
  nodeSelector: default       # "default" | "gpu" — maps to Karpenter node group
  # vaultService: ""          # Only set during service renames
  # selectorService: ""       # Only set when selector label must differ from release name

image:
  repository: ""              # Set by CI/CD via --set image.repository={ECR}
  tag: latest                 # Set by CI/CD via --set image.tag={SHA}
  pullPolicy: Always

service:
  enabled: true               # Disable for pure Kafka/queue workers
  port: 8000
  targetPort: 8000

command: []                   # Use Dockerfile CMD by default; override for observability wrapper
observabilityCommand: []      # Used when observability.enabled=true (e.g., ddtrace-run ...)

health:
  enabled: true               # Disable for headless workers (Kafka consumers)
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
  enabled: false             # Enable for services that expose HTTP externally
  path: /

domains: []                  # ["service.btp-{env}.int"] — set per-service

tls: []
tlsPrivate: []               # [{secretName: "...", hosts: ["..."]}] for internal TLS

observability:
  enabled: false             # Set to true at deploy for qa/prod environments
  llm: false                 # Enables DD_LLMOBS_ENABLED + LLM tracing (for AI workloads)

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
  prodMinReplicas: 1         # Used when settings.environment == "prod"
  targetCPUUtilizationPercentage: 60
  targetMemoryUtilizationPercentage: 95

shm:                         # Shared memory — GPU workloads only
  enabled: false
  sizeLimit: "1Gi"

tolerations: []              # GPU tolerations go here
podAnnotations: {}           # e.g., karpenter.sh/do-not-disrupt: "true"
```

---

## Per-Service Values Files

Each service gets one file in `charts/values/`. Only override what differs from the chart defaults:

### API / HTTP service

```yaml
settings:
  host: {service-name}
  nodeSelector: default

image:
  tag: api-latest             # Tag prefix from CI/CD

service:
  enabled: true
  port: 8000

observabilityCommand: ["ddtrace-run", "python", "-m", "uvicorn", "main:api", "--host", "0.0.0.0", "--port", "8000"]

health:
  enabled: true
  path: /health

ingress:
  enabled: true
  path: /

domains:
  - {service-name}.btp-dev.int    # Must match Route53 record created by btp_service_cross

hpa:
  minReplicas: 1
  maxReplicas: 10
  prodMinReplicas: 2
```

### Kafka/Queue Worker (headless)

```yaml
settings:
  host: {service-name}
  nodeSelector: default

image:
  tag: {service-name}-latest

service:
  enabled: false              # No HTTP endpoint

command: ["python", "main.py"]
observabilityCommand: ["ddtrace-run", "python", "main.py"]

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
  host: {service-name}
  nodeSelector: gpu

image:
  tag: {service-name}-latest

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

### Frontend (nginx)

```yaml
settings:
  host: {service-name}

image:
  tag: ui-latest

domains:
  - {service-name}.btp-dev.int

env:
  backendApiUrl: http://{backend-service}:8000
  backendApiHost: {backend-service}:8000
```

---

## Immutable Selector Gotcha

Kubernetes `Deployment.spec.selector` is immutable after creation. When deploying a renamed service:

1. **First deploy with old release name** sets selector `app: old-name`
2. **Rename to new release name** but set `settings.selectorService: old-name` in values file to preserve the selector
3. **Once pods are replaced and traffic is stable**, remove `settings.selectorService`

Alternatively: delete the old deployment before deploying with new name (causes brief downtime).

---

## Helm Deploy Command Pattern

```bash
helm upgrade --install {release-name} ./charts/{chart} \
  --values ./charts/values/{service}.yaml \
  --namespace {namespace} \
  --create-namespace \
  --set image.repository={ECR_REPO} \
  --set image.tag={IMAGE_TAG} \
  --set settings.environment={ENVIRONMENT} \
  --set domains[0]={service}.btp-{env}.int \
  --set observability.enabled=true    # qa/prod only
```

For services with TLS:
```bash
  --set tlsPrivate[0].secretName={service}-tls-secret \
  --set tlsPrivate[0].hosts[0]={service}.btp-{env}.int
```

---

## Environment-Specific Helm Behavior

| Setting | dev | qa | prod |
|---------|-----|----|------|
| `observability.enabled` | false | true | true |
| `hpa.minReplicas` | `minReplicas` | `minReplicas` | `prodMinReplicas` |
| `image.tag` | `{prefix}-{sha}` | `{prefix}-{sha}` | `{prefix}-{sha}` |
| `settings.environment` | dev | qa | prod |

The `hpa.yaml` template checks `settings.environment` to choose between `minReplicas` and `prodMinReplicas`.
