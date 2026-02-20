# CI/CD Pipeline Patterns

## Pipeline Overview

```
push to branch
    ↓
detect-changes        ← dorny/paths-filter: determine which services changed
    ↓
build (matrix)        ← docker build + push to ECR per changed service
    ↓
deploy (matrix)       ← helm upgrade --install per changed service
    ↓
integration-test      ← health checks + smoke test
```

All jobs use self-hosted Kubernetes runners that are ephemeral (destroyed after each run). Any tool not pre-baked into the runner image must be installed and cached.

---

## Branch → Environment Mapping

```yaml
env:
  ENVIRONMENT: >-
    ${{ github.ref_name == 'main' && 'prod' ||
        github.ref_name == 'qa'   && 'qa'   ||
        'dev' }}
```

Always map at the workflow level so all downstream jobs inherit it.

---

## Change Detection (detect-changes job)

Use `dorny/paths-filter@v3` to determine which services changed:

```yaml
- uses: dorny/paths-filter@v3
  id: changes
  with:
    base: ${{ github.ref }}
    ref: ${{ github.sha }}
    filters: |
      service-a:
        - 'service-a/**'
      service-a-values:
        - 'charts/values/service-a.yaml'
      service-b:
        - 'service-b/**'
      service-b-values:
        - 'charts/values/service-b.yaml'
      backend-chart:
        - 'charts/backend/**'
      frontend-chart:
        - 'charts/frontend/**'
```

**Rules**:
- Service code changes trigger only that service
- Chart template changes (`charts/backend/**`) trigger ALL services using that chart
- Values file changes trigger only the specific service
- All three trigger types result in build + deploy (no deploy-only path — ephemeral K8s runners cannot look up existing image tags reliably)

### Matrix Construction

```bash
BUILD_SERVICES=()
DEPLOY_SERVICES=()

service_matrix() {
  local path=$1 service=$2 tag_prefix=$3 runner=$4 chart=$5 has_domain=$6
  echo "{\"path\":\"$path\",\"service\":\"$service\",\"tag_prefix\":\"$tag_prefix\",\"runner\":\"$runner\",\"chart\":\"$chart\",\"has_domain\":\"$has_domain\"}"
}

# service-a: code, chart, or values change → build+deploy
if [[ "$SERVICE_A" == "true" || "$BACKEND_CHART" == "true" || "$SERVICE_A_VALUES" == "true" ]]; then
  entry=$(service_matrix "service-a" "service-a" "svc-a" "runners-arm" "backend" "true")
  BUILD_SERVICES+=("$entry")
  DEPLOY_SERVICES+=("$entry")
fi

# frontend service: only frontend-chart or values triggers
if [[ "$SERVICE_UI" == "true" || "$FRONTEND_CHART" == "true" || "$SERVICE_UI_VALUES" == "true" ]]; then
  entry=$(service_matrix "service-ui" "service-ui" "ui" "runners-arm" "frontend" "true")
  BUILD_SERVICES+=("$entry")
  DEPLOY_SERVICES+=("$entry")
fi

# Output matrices
HAS_BUILD=$([ ${#BUILD_SERVICES[@]} -gt 0 ] && echo "true" || echo "false")
echo "build_services=[$(IFS=,; echo "${BUILD_SERVICES[*]}")]" >> $GITHUB_OUTPUT
echo "has_build_changes=$HAS_BUILD" >> $GITHUB_OUTPUT
echo "deploy_services=[$(IFS=,; echo "${DEPLOY_SERVICES[*]}")]" >> $GITHUB_OUTPUT
echo "has_deploy_changes=$HAS_BUILD" >> $GITHUB_OUTPUT
```

---

## Build Job

```yaml
build:
  needs: detect-changes
  if: needs.detect-changes.outputs.has_build_changes == 'true'
  strategy:
    matrix:
      service: ${{ fromJson(needs.detect-changes.outputs.build_services) }}
  runs-on: ${{ matrix.service.runner }}
  steps:
    - uses: actions/checkout@v4

    - uses: docker/setup-buildx-action@v3
      with:
        driver-opts: image=moby/buildkit:master

    - uses: aws-actions/amazon-ecr-login@v1

    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: ${{ matrix.service.path }}/
        push: true
        tags: ${{ env.ECR_REGISTRY }}/btp-{app}:${{ matrix.service.tag_prefix }}-${{ github.sha }}
        cache-from: type=s3,region=us-east-1,bucket=btp-utility-buildx-cache-us-east-1,name=${{ matrix.service.service }}
        cache-to: type=s3,region=us-east-1,bucket=btp-utility-buildx-cache-us-east-1,name=${{ matrix.service.service }},mode=max
```

**Image tag format**: `{tag_prefix}-{github.sha}` — unique per commit, traceable to source.

**BuildKit S3 cache**: Stores layer cache in utility account S3. Dramatically reduces build times for stable base images. The cache bucket is shared across environments.

---

## Deploy Job

```yaml
deploy:
  needs: [detect-changes, build]
  if: |
    always() &&
    needs.detect-changes.outputs.has_deploy_changes == 'true' &&
    (needs.build.result == 'success' || needs.build.result == 'skipped')
  strategy:
    matrix:
      service: ${{ fromJson(needs.detect-changes.outputs.deploy_services) }}
  runs-on: ${{ matrix.service.runner }}
  steps:
    - uses: actions/checkout@v4

    # AWS CLI — install to home dir (system path requires root, runner is non-root)
    - name: Cache AWS CLI
      id: cache-aws
      uses: actions/cache@v4
      with:
        path: ~/.aws-cli
        key: aws-cli-aarch64-2.33.14     # Pin version in cache key

    - name: Install AWS CLI
      if: steps.cache-aws.outputs.cache-hit != 'true'
      run: |
        curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"
        unzip -q awscliv2.zip
        ./aws/install --install-dir $HOME/.aws-cli --bin-dir $HOME/.aws-cli/bin
        rm -rf aws awscliv2.zip

    - name: Add AWS CLI to PATH
      run: echo "$HOME/.aws-cli/bin" >> $GITHUB_PATH    # Must run every time, not just on install

    - name: Setup Helm
      uses: azure/setup-helm@v3
      with:
        version: v3.9.2

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ env.ASSUME_ROLE }}          # DEV/QA/PROD_ASSUME_ROLE from secrets
        aws-region: us-east-1
        role-duration-seconds: 900

    - name: Update kubeconfig
      run: aws eks update-kubeconfig --name btp-${{ env.ENVIRONMENT }} --region us-east-1

    - name: Deploy
      run: |
        IMAGE_TAG="${{ matrix.service.tag_prefix }}-${{ github.sha }}"

        HELM_CMD="helm upgrade --install ${{ matrix.service.service }} \
          ./charts/${{ matrix.service.chart }} \
          --values ./charts/values/${{ matrix.service.service }}.yaml \
          --namespace {app-namespace} \
          --set image.repository=${{ env.ECR_REGISTRY }}/{app-image} \
          --set image.tag=$IMAGE_TAG \
          --set settings.environment=${{ env.ENVIRONMENT }}"

        # Inject domain (environment-specific) for services with ingress
        if [[ "${{ matrix.service.has_domain }}" == "true" ]]; then
          case "${{ matrix.service.service }}" in
            "service-a")
              HELM_CMD="$HELM_CMD --set domains[0]=service-a.btp-${{ env.ENVIRONMENT }}.int"
              ;;
            "service-ui")
              HELM_CMD="$HELM_CMD --set domains[0]=service-ui.btp-${{ env.ENVIRONMENT }}.int"
              HELM_CMD="$HELM_CMD --set tlsPrivate[0].secretName=service-ui-tls-secret"
              HELM_CMD="$HELM_CMD --set tlsPrivate[0].hosts[0]=service-ui.btp-${{ env.ENVIRONMENT }}.int"
              ;;
          esac
        fi

        # Enable Datadog observability in non-dev environments
        if [[ "${{ env.ENVIRONMENT }}" != "dev" ]]; then
          HELM_CMD="$HELM_CMD --set observability.enabled=true"
        fi

        eval $HELM_CMD
```

### AWS CLI Caching — Critical Note

Self-hosted K8s runners run as non-root. `actions/cache` restores via tar, which cannot write to `/usr/local/`. Always install CLI tools to `$HOME` paths:

| ❌ Fails | ✓ Works |
|---------|---------|
| `path: /usr/local/aws-cli` | `path: ~/.aws-cli` |
| `./aws/install` (default: /usr/local) | `./aws/install --install-dir $HOME/.aws-cli --bin-dir $HOME/.aws-cli/bin` |

Always add an explicit `echo "$HOME/.aws-cli/bin" >> $GITHUB_PATH` step that runs on every job (not conditional on cache miss) — GitHub PATH context is not persisted between steps.

---

## Per-Service Domain Injection

Domains are injected at deploy time (not hardcoded in values files) because the domain suffix changes per environment (`btp-dev.int`, `btp-qa.int`, `btp-prod.int`):

```bash
--set domains[0]={service}.btp-$ENVIRONMENT.int
```

The Route53 record for `{service}.btp-{env}.int` is created by the `btp_service_cross` module. The Helm domain must match exactly.

---

## Integration Test Job

```yaml
integration-test:
  needs: [detect-changes, deploy]
  if: needs.deploy.result == 'success'
  runs-on: btp-runners
  steps:
    - name: Wait for deployments
      run: |
        kubectl rollout status deployment/service-a -n {namespace} --timeout=300s
        kubectl rollout status deployment/service-b -n {namespace} --timeout=300s

    - name: Verify pod health
      run: |
        # Wait for old ReplicaSets to terminate
        MAX_RETRIES=12
        for i in $(seq 1 $MAX_RETRIES); do
          ACTIVE_RS=$(kubectl get rs -n {namespace} \
            -l app=service-a \
            --field-selector='status.availableReplicas>0' \
            -o json | jq '.items | length')
          [ "$ACTIVE_RS" -le 1 ] && break
          sleep 15
        done

        # Verify API health
        for i in $(seq 1 $MAX_RETRIES); do
          curl -sf http://service-a.{namespace}.svc.cluster.local:{port}/health && break
          sleep 15
        done
```

---

## Multi-Architecture Runners

Different services may require different runner architectures:

```yaml
# In matrix definitions:
runner: "btp-runners"          # ARM64 (aarch64) — default, cost-efficient
runner: "btp-runners-x86"     # x86_64 — required for GPU workloads, some C extensions
```

Match `--arch` in AWS CLI download URL to runner architecture:
- ARM: `awscli-exe-linux-aarch64.zip`
- x86: `awscli-exe-linux-x86_64.zip`

---

## Shared Config Files

Some applications mount configuration files from a `config/` directory into the container at `/usr/share/env/`. The CI/CD copies these into the chart directory before deploying, then cleans up:

```bash
cp -r ./config ./charts/${{ matrix.service.chart }}/config
eval $HELM_CMD
rm -rf ./charts/${{ matrix.service.chart }}/config
```

The `deployment.yaml` template then mounts these files as a ConfigMap or volume.

---

## GitHub Secrets Naming Convention

```
ECR_REGISTRY                  # {account}.dkr.ecr.us-east-1.amazonaws.com
DEV_ASSUME_ROLE               # arn:aws:iam::{dev-account}:role/github-runner-role
QA_ASSUME_ROLE                # arn:aws:iam::{qa-account}:role/github-runner-role
PROD_ASSUME_ROLE              # arn:aws:iam::{prod-account}:role/github-runner-role
```

Select via environment mapping:
```bash
ASSUME_ROLE=${{ env.ENVIRONMENT == 'prod' && secrets.PROD_ASSUME_ROLE ||
                env.ENVIRONMENT == 'qa'   && secrets.QA_ASSUME_ROLE   ||
                secrets.DEV_ASSUME_ROLE }}
```
