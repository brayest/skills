# CI/CD Pipeline Patterns

## Pipeline Overview

```
push to branch
    ↓
detect-changes        ← dorny/paths-filter: figure out which services changed
    ↓
build (matrix)        ← docker build + push to ECR per changed service
    ↓
deploy (matrix)       ← helm upgrade --install per changed service
    ↓
integration-test      ← rollout status + smoke health checks
```

All jobs run on self-hosted Kubernetes runners that are ephemeral (destroyed after each run). Any tool not pre-baked into the runner image must be installed and cached, and installs must go to `$HOME` since the runner runs as non-root.

---

## Branch → Environment Mapping

Map the environment once at the workflow level so all downstream jobs inherit it:

```yaml
env:
  ENVIRONMENT: >-
    ${{ github.ref_name == 'main' && 'prod' ||
        github.ref_name == 'qa'   && 'qa'   ||
        'dev' }}
```

---

## Change Detection (`detect-changes` job)

Use `dorny/paths-filter@v3` to determine which services changed:

```yaml
- uses: dorny/paths-filter@v3
  id: changes
  with:
    base: ${{ github.ref }}
    ref:  ${{ github.sha }}
    filters: |
      <service-a>:
        - 'services/<service-a>/**'
      <service-a>-values:
        - 'charts/values/<service-a>.yaml'
      <service-b>:
        - 'services/<service-b>/**'
      <service-b>-values:
        - 'charts/values/<service-b>.yaml'
      chart:
        - 'charts/<chart>/**'
      infrastructure:
        - 'infrastructure/**'
```

**Rules:**
- Service code change → builds and deploys that service.
- Chart template change (`charts/<chart>/**`) → builds and deploys ALL services using that chart.
- Values file change → builds and deploys that one service.
- Code, chart, and values changes all funnel into build + deploy. There is no deploy-only path — ephemeral K8s runners cannot reliably resolve "the current image tag" so each pipeline rebuilds.
- Optional: include an `infrastructure` filter if you want infra changes to gate downstream concerns (e.g., post a comment or run a plan). Apply itself is still done manually via `terragrunt`.

### Matrix Construction (Bash)

```bash
BUILD_SERVICES=()
DEPLOY_SERVICES=()

service_matrix() {
  local path=$1 service=$2 tag_prefix=$3 runner=$4 chart=$5 has_domain=$6
  echo "{\"path\":\"$path\",\"service\":\"$service\",\"tag_prefix\":\"$tag_prefix\",\"runner\":\"$runner\",\"chart\":\"$chart\",\"has_domain\":\"$has_domain\"}"
}

# service-a: code, chart, or values change → build + deploy
if [[ "$SERVICE_A" == "true" || "$CHART" == "true" || "$SERVICE_A_VALUES" == "true" ]]; then
  entry=$(service_matrix "services/<service-a>" "<service-a>" "<tag-prefix>" "<runner-label>" "<chart>" "true")
  BUILD_SERVICES+=("$entry")
  DEPLOY_SERVICES+=("$entry")
fi

# Repeat per service...

HAS_BUILD=$([ ${#BUILD_SERVICES[@]} -gt 0 ] && echo "true" || echo "false")
echo "build_services=[$(IFS=,; echo "${BUILD_SERVICES[*]}")]"   >> "$GITHUB_OUTPUT"
echo "has_build_changes=$HAS_BUILD"                              >> "$GITHUB_OUTPUT"
echo "deploy_services=[$(IFS=,; echo "${DEPLOY_SERVICES[*]}")]"  >> "$GITHUB_OUTPUT"
echo "has_deploy_changes=$HAS_BUILD"                             >> "$GITHUB_OUTPUT"
```

Keep this builder agnostic of service count — every service is one `if` block that calls `service_matrix`. Add or remove services by editing this block plus the `filters:` map.

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
        tags: ${{ env.ECR_REGISTRY }}/<ecr-repo>:${{ matrix.service.tag_prefix }}-${{ github.sha }}
        cache-from: type=s3,region=us-east-1,bucket=<buildkit-cache-bucket>,name=${{ matrix.service.service }}
        cache-to:   type=s3,region=us-east-1,bucket=<buildkit-cache-bucket>,name=${{ matrix.service.service }},mode=max
```

**Image tag**: `<tag_prefix>-<github.sha>` — unique per commit, traceable to source.

**BuildKit S3 cache**: stores layer cache in a shared S3 bucket (typically in the utility account). The `name=` parameter is the **per-service cache key** — sharing one cache key across services causes layer-hash collisions and silent cache misses. Keep one key per service.

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

    # AWS CLI — install to $HOME (system paths require root; runner is non-root)
    - name: Cache AWS CLI
      id: cache-aws
      uses: actions/cache@v4
      with:
        path: ~/.aws-cli
        key: aws-cli-aarch64-2.33.14    # Pin version in the cache key

    - name: Install AWS CLI
      if: steps.cache-aws.outputs.cache-hit != 'true'
      run: |
        curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"
        unzip -q awscliv2.zip
        ./aws/install --install-dir "$HOME/.aws-cli" --bin-dir "$HOME/.aws-cli/bin"
        rm -rf aws awscliv2.zip

    - name: Add AWS CLI to PATH
      run: echo "$HOME/.aws-cli/bin" >> "$GITHUB_PATH"   # Must run every job, not just on install

    - uses: azure/setup-helm@v3
      with:
        version: v3.9.2

    - uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ env.ASSUME_ROLE }}
        aws-region: us-east-1
        role-duration-seconds: 900

    - name: Update kubeconfig
      run: aws eks update-kubeconfig --name <eks-cluster-name> --region us-east-1

    - name: Deploy
      run: |
        IMAGE_TAG="${{ matrix.service.tag_prefix }}-${{ github.sha }}"

        HELM_CMD="helm upgrade --install ${{ matrix.service.service }} \
          ./charts/${{ matrix.service.chart }} \
          --values ./charts/values/${{ matrix.service.service }}.yaml \
          --namespace <namespace> \
          --set image.repository=${{ env.ECR_REGISTRY }}/<ecr-repo> \
          --set image.tag=$IMAGE_TAG \
          --set settings.environment=${{ env.ENVIRONMENT }}"

        # Inject env-specific domain for services with ingress
        if [[ "${{ matrix.service.has_domain }}" == "true" ]]; then
          case "${{ matrix.service.service }}" in
            "<service-a>")
              HELM_CMD="$HELM_CMD --set domains[0]=<service-a>.<internal-domain-suffix-for-env>"
              ;;
            "<service-ui>")
              HELM_CMD="$HELM_CMD --set domains[0]=<service-ui>.<internal-domain-suffix-for-env>"
              HELM_CMD="$HELM_CMD --set tlsPrivate[0].secretName=<service-ui>-tls-secret"
              HELM_CMD="$HELM_CMD --set tlsPrivate[0].hosts[0]=<service-ui>.<internal-domain-suffix-for-env>"
              ;;
          esac
        fi

        # Enable observability in non-dev environments
        if [[ "${{ env.ENVIRONMENT }}" != "dev" ]]; then
          HELM_CMD="$HELM_CMD --set observability.enabled=true"
        fi

        eval "$HELM_CMD"
```

### AWS CLI Install Gotcha (read this once, save yourself an afternoon)

Self-hosted K8s runners run as non-root. `actions/cache` restores via `tar`, which cannot write to `/usr/local/`. Install CLI tools under `$HOME`:

| Fails | Works |
|---|---|
| `path: /usr/local/aws-cli` | `path: ~/.aws-cli` |
| `./aws/install` (default `/usr/local`) | `./aws/install --install-dir $HOME/.aws-cli --bin-dir $HOME/.aws-cli/bin` |

Add an unconditional `echo "$HOME/.aws-cli/bin" >> "$GITHUB_PATH"` step on **every** deploy job, not just on cache miss — `$GITHUB_PATH` is not persisted between jobs.

---

## Per-Service Domain Injection

Domains are injected at deploy time, not hardcoded in values files, because the domain suffix changes per environment (`<internal-domain-suffix-for-dev>`, `<internal-domain-suffix-for-qa>`, `<internal-domain-suffix-for-prod>`):

```bash
--set domains[0]=<service>.<internal-domain-suffix-for-${ENVIRONMENT}>
```

The Route53 record for `<service>.<internal-domain-suffix-for-env>` is created by the service-wiring module in Terraform. The Helm domain must match exactly.

---

## Integration Test Job

```yaml
integration-test:
  needs: [detect-changes, deploy]
  if: needs.deploy.result == 'success'
  runs-on: <runner-label>
  steps:
    - name: Wait for deployments
      run: |
        kubectl rollout status deployment/<service-a> -n <namespace> --timeout=300s
        kubectl rollout status deployment/<service-b> -n <namespace> --timeout=300s

    - name: Verify pod health
      run: |
        # Wait for old ReplicaSets to terminate
        MAX_RETRIES=12
        for i in $(seq 1 $MAX_RETRIES); do
          ACTIVE_RS=$(kubectl get rs -n <namespace> \
            -l app=<service-a> \
            --field-selector='status.availableReplicas>0' \
            -o json | jq '.items | length')
          [ "$ACTIVE_RS" -le 1 ] && break
          sleep 15
        done

        # Hit the health endpoint
        for i in $(seq 1 $MAX_RETRIES); do
          curl -sf http://<service-a>.<namespace>.svc.cluster.local:<port>/health && break
          sleep 15
        done
```

---

## Multi-Architecture Runners

Different services may need different runner architectures:

```yaml
# In matrix entries:
runner: "<runner-label-aarch64>"    # ARM — default, cost-efficient
runner: "<runner-label-x86>"        # x86 — required for GPU workloads and some C extensions
```

Match the `--arch` segment of the AWS CLI download URL to the runner architecture:

- ARM: `awscli-exe-linux-aarch64.zip`
- x86: `awscli-exe-linux-x86_64.zip`

---

## Shared Config Files

Some applications mount config files from a `config/` directory into the container at runtime. The deploy job copies the directory into the chart's working tree before `helm upgrade` and removes it afterwards (so the chart on disk stays clean):

```bash
cp -r ./config "./charts/${{ matrix.service.chart }}/config"
eval "$HELM_CMD"
rm -rf "./charts/${{ matrix.service.chart }}/config"
```

The chart's `deployment.yaml` then mounts these files as a ConfigMap or volume.

---

## GitHub Secrets Naming Convention

```
ECR_REGISTRY                 # <account>.dkr.ecr.us-east-1.amazonaws.com
DEV_ASSUME_ROLE              # arn:aws:iam::<dev-account>:role/<github-runner-role>
QA_ASSUME_ROLE               # arn:aws:iam::<qa-account>:role/<github-runner-role>
PROD_ASSUME_ROLE             # arn:aws:iam::<prod-account>:role/<github-runner-role>
```

Select via the environment mapping at workflow level:

```yaml
env:
  ASSUME_ROLE: >-
    ${{ env.ENVIRONMENT == 'prod' && secrets.PROD_ASSUME_ROLE ||
        env.ENVIRONMENT == 'qa'   && secrets.QA_ASSUME_ROLE   ||
        secrets.DEV_ASSUME_ROLE }}
```
