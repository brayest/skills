# Local Development

## `compose.yaml` With Profiles

Local development uses Docker Compose with **named profiles**, so a developer can bring up only what they need. The `common` profile holds the dependencies every service requires; opt-in profiles cover variants (alternate DB engines, GPU-adjacent services, optional collaborators) that aren't always needed.

```yaml
services:
  postgres:
    image: postgres:16
    profiles: ["common", "db"]
    environment:
      POSTGRES_PASSWORD: <local-password>
      POSTGRES_HOST_AUTH_METHOD: trust
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  # Opt-in variant: spatial-enabled DB, only needed for services using geospatial features
  postgres-postgis:
    image: postgis/postgis:16-3.4
    profiles: ["geo"]
    environment:
      POSTGRES_PASSWORD: <local-password>
      POSTGRES_HOST_AUTH_METHOD: trust
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 2s
      timeout: 5s
      retries: 15
    volumes:
      - postgis_data:/var/lib/postgresql/data
    restart: unless-stopped

  kafka:
    image: apache/kafka:3.9.0
    profiles: ["common"]
    ports:
      - "9092:9092"
      - "29092:29092"
    environment:
      # KRaft mode — no Zookeeper
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093,PLAINTEXT_HOST://:29092
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,PLAINTEXT_HOST://localhost:29092
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      CLUSTER_ID: <fixed-cluster-id>
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    healthcheck:
      test: ["CMD-SHELL", "/opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list"]
      interval: 2s
      timeout: 5s
      retries: 15
    volumes:
      - kafka_data:/var/lib/kafka/data
    restart: unless-stopped

  localstack:
    image: localstack/localstack:latest
    profiles: ["common"]
    environment:
      SERVICES: s3,dynamodb,sqs
      DEFAULT_REGION: us-east-1
      AWS_DEFAULT_REGION: us-east-1
    ports:
      - "4566:4566"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4566/_localstack/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock"
      - localstack_data:/var/lib/localstack
    restart: unless-stopped

volumes:
  postgres_data:
  postgis_data:
  kafka_data:
  localstack_data:
```

Usage:

```bash
docker compose --profile common up -d      # Everyday dev — bring up the standard stack
docker compose --profile geo up -d         # Add the spatial DB variant
docker compose down                        # Stop everything (keep volumes)
docker compose down -v                     # Stop and wipe volumes (clean reset)
```

If your runtime supports it (e.g., Spring Boot's Docker Compose support), `mvn spring-boot:run` or the equivalent can auto-start the `common` profile.

---

## Health Checks Are Mandatory

Every service in `compose.yaml` should declare a `healthcheck`. Two reasons:

1. **Bootstrap scripts can wait on them.** A migration runner that loops `docker compose ps --format json | jq '.[].Health'` until everything reports `healthy` is more reliable than a `sleep 30`.
2. **CI parity.** Production has readiness/liveness probes; local should have something analogous so dev and prod behave similarly.

Pick health checks that are both *cheap* and *meaningful* — `pg_isready` for Postgres, `kafka-topics.sh --list` for Kafka, `curl /_localstack/health` for LocalStack. Avoid generic TCP-port probes that succeed before the process is ready to accept queries.

---

## Bootstrap Scripts in `scripts/`

`scripts/` holds idempotent bash scripts for the operations that bridge "Compose is up" and "the dev environment is usable."

Conventions:

- One concern per script (DB migrations, seed data, local secret loader, fixture generator).
- `#!/usr/bin/env bash` + `set -euo pipefail` at the top of every script.
- Accept flags like `--fresh` for destructive operations (drop schemas, recreate volumes) so the default is safe.
- Idempotent — running twice should not break anything. Use `IF NOT EXISTS`, `--if-not-exists`, etc.
- Read configuration from env vars with sensible local defaults; never hardcode credentials.

Example skeleton for a migration runner:

```bash
#!/usr/bin/env bash
set -euo pipefail

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

FRESH=false
for arg in "$@"; do
  case "$arg" in
    --fresh) FRESH=true ;;
    *) echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

if [[ "$FRESH" == "true" ]]; then
  echo "[fresh] dropping schemas..."
  # destructive: drop and recreate
fi

# Run migrations for each schema your services own
for schema in <schema-a> <schema-b> <schema-c>; do
  echo "Migrating $schema..."
  # invoke flyway / atlas / sqlx / whatever
done
```

Wire scripts into the developer onboarding doc (often `README.md`): "After `docker compose up`, run `./scripts/<bootstrap>.sh` once."

---

## AWS Credentials in Compose

Local dev should mirror production's no-access-key posture. Two safe options:

**Mount the host's `~/.aws` read-only and set a profile:**

```yaml
services:
  <my-service>:
    environment:
      AWS_PROFILE: <local-dev-profile>
      AWS_REGION: us-east-1
    volumes:
      - "${HOME}/.aws:/root/.aws:ro"
```

The service uses the local SSO/SAML session from your shell. When the session expires, refresh on the host (`aws sso login --profile <local-dev-profile>`) and the container picks it up.

**Or use LocalStack** for fully offline dev — point AWS SDK clients at `http://localstack:4566` via an endpoint override.

What to never do: hardcode `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `compose.yaml`, `.env`, or anywhere else in the repo. If a service requires real cloud access (Bedrock, a partner-managed S3 bucket), use the mounted profile; if it only needs S3/DynamoDB/SQS for local dev, point it at LocalStack.

---

## Volume Hygiene

Named volumes (`postgres_data`, `kafka_data`, etc.) survive `docker compose down` so dev data persists across restarts. To start completely fresh:

```bash
docker compose down -v        # Stops containers AND removes named volumes
```

Use this when:
- You changed the DB image tag (e.g., Postgres major version) and want a clean cluster.
- A migration left things in an inconsistent state.
- You want to validate bootstrap scripts run end-to-end from zero.

Avoid mounting host directories for stateful services (`./data:/var/lib/postgresql/data`) — they introduce file-permission surprises across macOS/Linux and slow I/O on macOS Docker Desktop. Stick with named volumes.

---

## Local-vs-CI Parity Checklist

A clean local stack should be reproducible by anyone in the team. Before saying "works on my machine":

- [ ] `docker compose --profile common up -d` succeeds from a fresh checkout.
- [ ] All services reach `healthy` within a reasonable window.
- [ ] `./scripts/<bootstrap>.sh` runs cleanly on a fresh stack.
- [ ] `./scripts/<bootstrap>.sh --fresh` also runs cleanly (destructive path works).
- [ ] Every credential the app reads has a local-safe default or a clear instruction for what to set.
