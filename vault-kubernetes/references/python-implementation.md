# Python Implementation

## Dependencies

```
hvac>=2.1.0
```

## Custom Exceptions

```python
class VaultConfigurationError(Exception):
    """Vault server is misconfigured, uninitialized, or sealed."""

class VaultAuthenticationError(Exception):
    """Kubernetes auth to Vault failed."""

class VaultSecretError(Exception):
    """Secret retrieval or validation failed."""
```

## VaultSecretManager

```python
import os
import time
import logging
from typing import Any, Dict, List, Optional

import hvac
from hvac.exceptions import Forbidden, InvalidPath, VaultError

logger = logging.getLogger(__name__)

SA_TOKEN_PATH = "/var/run/secrets/kubernetes.io/serviceaccount/token"


class VaultSecretManager:
    """Fetches secrets from Vault at startup using Kubernetes auth."""

    def __init__(self) -> None:
        self.vault_url: str = os.environ["VAULT_ADDR"]
        self.vault_role: str = os.environ["VAULT_ROLE"]
        self.vault_path: str = os.environ["VAULT_PATH"]
        self.vault_mount_point: str = os.getenv("VAULT_MOUNT_POINT", "kv")
        self.k8s_auth_mount_point: str = os.environ["VAULT_K8S_AUTH_MOUNT_POINT"]
        self.sa_token_path: str = SA_TOKEN_PATH

        self.connection_timeout: int = int(os.getenv("VAULT_TIMEOUT", "30"))
        self.max_retries: int = int(os.getenv("VAULT_MAX_RETRIES", "3"))
        self.retry_delay: int = int(os.getenv("VAULT_RETRY_DELAY", "5"))

        self.client: Optional[hvac.Client] = None
        self.authenticated: bool = False
        self.secrets_loaded: bool = False

    # ── Client ──────────────────────────────────────────

    def _create_client(self) -> hvac.Client:
        client = hvac.Client(url=self.vault_url, timeout=self.connection_timeout)

        if not client.sys.is_initialized():
            raise VaultConfigurationError("Vault server is not initialized")
        if client.sys.is_sealed():
            raise VaultConfigurationError("Vault server is sealed")

        logger.debug("Vault client created — server is initialized and unsealed")
        return client

    # ── Authentication ──────────────────────────────────

    def _read_service_account_token(self) -> str:
        try:
            with open(self.sa_token_path, "r") as f:
                token = f.read().strip()
        except FileNotFoundError:
            raise VaultAuthenticationError(
                f"SA token not found at {self.sa_token_path}. "
                "Pod must have a service account with automountServiceAccountToken enabled."
            )

        if not token:
            raise VaultAuthenticationError("SA token file is empty")

        logger.debug("Service account token read successfully")
        return token

    def _authenticate(self) -> None:
        sa_token = self._read_service_account_token()

        logger.debug(
            f"Authenticating with Vault — role={self.vault_role}, "
            f"mount={self.k8s_auth_mount_point}"
        )

        try:
            auth_response = self.client.auth.kubernetes.login(
                role=self.vault_role,
                jwt=sa_token,
                mount_point=self.k8s_auth_mount_point,
            )
        except VaultError as e:
            raise VaultAuthenticationError(f"Vault K8s login failed: {e}") from e

        auth_data = auth_response.get("auth")
        if not auth_data or "client_token" not in auth_data:
            raise VaultAuthenticationError(
                "Invalid auth response — missing client_token"
            )

        self.client.token = auth_data["client_token"]

        if not self.client.is_authenticated():
            raise VaultAuthenticationError("Post-login authentication check failed")

        self.authenticated = True
        logger.info("Vault authentication successful")
        logger.debug(
            f"Token TTL: {auth_data.get('lease_duration', 'unknown')}s, "
            f"policies: {auth_data.get('policies', [])}"
        )

    # ── Secret Retrieval ────────────────────────────────

    def _fetch_secrets(self) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=self.vault_path,
                    mount_point=self.vault_mount_point,
                )
                secrets = response["data"]["data"]
                logger.info(f"Fetched {len(secrets)} secrets from {self.vault_path}")
                return secrets

            except InvalidPath:
                raise VaultSecretError(
                    f"Secret path not found: {self.vault_mount_point}/{self.vault_path}"
                )
            except Forbidden:
                raise VaultSecretError(
                    f"Access denied to: {self.vault_mount_point}/{self.vault_path}"
                )
            except VaultError as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt}/{self.max_retries} failed: {e}"
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        raise VaultSecretError(
            f"Failed after {self.max_retries} attempts: {last_error}"
        )

    # ── Validation & Injection ──────────────────────────

    def _validate_required(
        self, secrets: Dict[str, Any], required: List[str]
    ) -> None:
        missing = [k for k in required if k not in secrets]
        if missing:
            raise VaultSecretError(f"Missing required secrets: {missing}")

    @staticmethod
    def _inject_to_environment(secrets: Dict[str, Any]) -> None:
        for key, value in secrets.items():
            os.environ[key] = str(value) if value is not None else ""

            if any(
                s in key.lower()
                for s in ("password", "secret", "key", "token")
            ):
                logger.debug(f"Injected: {key} = ***masked***")
            else:
                logger.debug(f"Injected: {key}")

    # ── Public API ──────────────────────────────────────

    def initialize(
        self, required_secrets: Optional[List[str]] = None
    ) -> None:
        """
        Full initialization sequence:
        1. Create client and verify server health
        2. Authenticate via Kubernetes SA
        3. Fetch all secrets with retry
        4. Validate required secrets are present
        5. Inject into os.environ

        Raises on any failure — no fallbacks.
        """
        self.client = self._create_client()
        self._authenticate()
        secrets = self._fetch_secrets()

        if required_secrets:
            self._validate_required(secrets, required_secrets)

        self._inject_to_environment(secrets)
        self.secrets_loaded = True
        logger.info("Vault secrets loaded and injected into environment")

    def get_status(self) -> Dict[str, Any]:
        return {
            "authenticated": self.authenticated,
            "secrets_loaded": self.secrets_loaded,
            "vault_url": self.vault_url,
            "vault_path": self.vault_path,
            "vault_role": self.vault_role,
        }
```

## Application Entry Point

```python
import os
import logging

logger = logging.getLogger(__name__)

REQUIRED_SECRETS = [
    "AWS_DEFAULT_REGION",
    "DATABASE_URL",
    # Add service-specific required secrets here
]


def initialize_vault() -> None:
    """Initialize Vault if VAULT_ADDR is set. Raises on failure."""
    vault_addr = os.getenv("VAULT_ADDR")
    if not vault_addr:
        logger.debug("Vault disabled — VAULT_ADDR not set")
        return

    from vault_client import VaultSecretManager

    manager = VaultSecretManager()
    manager.initialize(required_secrets=REQUIRED_SECRETS)


# Call before any imports that depend on environment variables
initialize_vault()
```

## Security Considerations

- **No long-lived credentials** — K8s SA tokens are short-lived JWTs rotated by the kubelet
- **No Vault tokens stored** — client token lives only in process memory during the fetch
- **Least privilege** — each role grants read-only access to exactly one KV path
- **Namespace binding** — roles bind to specific namespaces to prevent cross-namespace access
- **Startup-only fetch** — no persistent Vault connection after initialization
- **Mask sensitive values in logs** — log key names only, never values

## Failure Modes

| Failure | Behavior | Resolution |
|---------|----------|------------|
| `VAULT_ADDR` not set | Vault skipped, app uses existing env vars | Expected for local dev |
| SA token file missing | `VaultAuthenticationError` — app crashes | Verify `serviceAccountName` in deployment |
| Vault sealed/uninitialized | `VaultConfigurationError` — app crashes | Unseal Vault or check `VAULT_ADDR` |
| K8s login rejected | `VaultAuthenticationError` — app crashes | Check role binding (SA name, namespace) |
| Secret path not found (404) | `VaultSecretError` — app crashes | Verify `VAULT_PATH` and KV mount |
| Access denied (403) | `VaultSecretError` — app crashes | Check policy attached to role |
| Required secret missing | `VaultSecretError` — app crashes | Add missing key to Vault KV path |
| Transient network error | Retried up to `VAULT_MAX_RETRIES` times | Check network/DNS to Vault |

All failures are loud and immediate — no silent fallbacks, no default values.
