# Operations Guide — vault_manager.py

## Full CLI Reference

The script lives at `scripts/vault_manager.py` in the btp-cope-extractor repo. Run with `python3`.

### Global Flags

| Flag | Purpose |
|------|---------|
| `--vault-url URL` | Override Vault URL (default: `http://vault.btp-utility.int/`) |
| `--token TOKEN` | Override Vault token (default: resolved from `~/.vault-token-btp`) |

### Subcommands

#### `envs` — List environments
```bash
python3 scripts/vault_manager.py envs [--json]
```
Returns: DEV, DR, PROD, QA, UTILITY

#### `services` — List services in an environment
```bash
python3 scripts/vault_manager.py services --env ENV [--json]
```

#### `read` — Read all secrets (masked)
```bash
python3 scripts/vault_manager.py read --env ENV --service SERVICE [--json]
```
Sensitive values are masked. Use `get` or `export` for unmasked values.

#### `get` — Get a single secret value (unmasked)
```bash
python3 scripts/vault_manager.py get --env ENV --service SERVICE --key KEY [--json]
```
Returns the raw value. Fails with available keys listed if key doesn't exist.

#### `update` — Update an existing key
```bash
python3 scripts/vault_manager.py update --env ENV --service SERVICE --key KEY --value VALUE [--dry-run]
```
Fails if key does NOT exist. This is intentional — prevents typos from creating phantom keys. Use `add` for new keys.

#### `add` — Add a new key
```bash
python3 scripts/vault_manager.py add --env ENV --service SERVICE --key KEY --value VALUE [--dry-run]
```
Fails if key already exists. Use `update` for existing keys.

#### `delete` — Delete a key
```bash
python3 scripts/vault_manager.py delete --env ENV --service SERVICE --key KEY [--dry-run] [--confirm]
```
Requires `--confirm` to actually delete. Without it (and without `--dry-run`), exits with error.

#### `bulk-update` — Update/add multiple keys from JSON
```bash
python3 scripts/vault_manager.py bulk-update --env ENV --service SERVICE --data '{"K1":"V1","K2":"V2"}' [--dry-run] [--json]
```
Accepts JSON string via `--data` or reads from stdin with `--data -`:
```bash
echo '{"K1":"V1"}' | python3 scripts/vault_manager.py bulk-update --env DEV --service COPE-API --data -
```
Returns summary of added and updated keys.

#### `compare` — Compare keys across environments
```bash
python3 scripts/vault_manager.py compare --service SERVICE [--envs DEV QA PROD] [--json]
```
Shows which keys exist in which environments. Values are never compared — keys only. Defaults to DEV, QA, PROD if `--envs` is omitted.

#### `export` — Export unmasked secrets as JSON
```bash
python3 scripts/vault_manager.py export --env ENV --service SERVICE
```
Outputs raw JSON to stdout. Redirect to file for backup:
```bash
python3 scripts/vault_manager.py export --env PROD --service COPE-API > backup.json
```

## Error Handling

All errors are printed to stderr and exit non-zero. No silent failures.

| Error | Meaning | Fix |
|-------|---------|-----|
| `RuntimeError: No Vault token found` | Neither `~/.vault-token-btp` nor `VAULT_TOKEN` exists | Create/refresh token file |
| `RuntimeError: Failed to authenticate` | Token is invalid or expired | Get a new token |
| `ValueError: Environment 'X' not found` | Typo in environment name | Check with `envs` command |
| `ValueError: Service 'X' not found` | Typo in service name | Check with `services --env ENV` |
| `KeyError: Key 'X' does not exist... Use 'add'` | Tried to `update` a non-existent key | Use `add` instead |
| `KeyError: Key 'X' already exists... Use 'update'` | Tried to `add` an existing key | Use `update` instead |

## Using as a Python Module

The `VaultManager` class can be imported directly:

```python
from vault_manager import VaultManager

vm = VaultManager()  # uses default URL and auto-resolved token
envs = vm.list_environments()
secrets = vm.read_secrets("DEV", "COPE-API", masked=True)
value = vm.read_secret("DEV", "COPE-API", "AWS_DEFAULT_REGION")
```

All methods raise exceptions on failure (no None returns, no fallbacks).

## Common Workflows

### Check if configs are in sync across environments
```bash
python3 scripts/vault_manager.py compare --service EXTRACTION-AGENT --envs DEV QA PROD
```
Look for `DIFF` status — those keys exist in some environments but not all.

### Promote a config change from DEV to QA and PROD
```bash
# 1. See what's different
python3 scripts/vault_manager.py compare --service COPE-API --envs DEV QA PROD --json

# 2. Get the DEV value
python3 scripts/vault_manager.py get --env DEV --service COPE-API --key NEW_SETTING

# 3. Add/update in QA (dry-run first)
python3 scripts/vault_manager.py add --env QA --service COPE-API --key NEW_SETTING --value "the-value" --dry-run
python3 scripts/vault_manager.py add --env QA --service COPE-API --key NEW_SETTING --value "the-value"

# 4. Repeat for PROD
python3 scripts/vault_manager.py add --env PROD --service COPE-API --key NEW_SETTING --value "prod-value" --dry-run
python3 scripts/vault_manager.py add --env PROD --service COPE-API --key NEW_SETTING --value "prod-value"
```

### Back up and restore
```bash
# Export
python3 scripts/vault_manager.py export --env PROD --service COPE-API > /tmp/cope-api-prod-backup.json

# Restore (if needed)
python3 scripts/vault_manager.py bulk-update --env PROD --service COPE-API --data - --dry-run < /tmp/cope-api-prod-backup.json
python3 scripts/vault_manager.py bulk-update --env PROD --service COPE-API --data - < /tmp/cope-api-prod-backup.json
```

### Audit all services in an environment
```bash
for svc in $(python3 scripts/vault_manager.py services --env PROD --json | python3 -c "import sys,json; [print(s) for s in json.load(sys.stdin)]"); do
  echo "=== $svc ==="
  python3 scripts/vault_manager.py read --env PROD --service "$svc"
  echo
done
```
