---
name: btp-vault-management
description: "Use this skill when managing, reading, updating, comparing, or exporting HashiCorp Vault secrets for any BTP service. Trigger whenever the user mentions Vault secrets, environment configs, secret rotation, config sync across environments (DEV/QA/PROD), or wants to check what services or keys exist in Vault. Also trigger when the user asks about BTP service configuration values, environment variables stored in Vault, or needs to add/remove/modify a config key for any BTP service (COPE-API, DOC-PROCESSOR, EXTRACTION-AGENT, BTP-PROPERTY-API, BTP-IAM-API, BTP-EMAIL-SERVICE, BTP-EXPOSURE-SERVICE, BTP-HELP-CENTER-API, BTP-PROPERTY-UI, BTP-PUBLIC-UI, INSURDATA, etc). This skill wraps the vault_manager.py CLI tool and covers all CRUD operations on the Vault KV v2 engine at kv/BTP/{ENV}/{SERVICE}."
---

# BTP Vault Secret Management

## Overview

BTP platform secrets live in HashiCorp Vault KV v2 at `http://vault.btp-utility.int/` under `kv/BTP/{ENV}/{SERVICE}`. Each service has a single KV v2 entry containing all its config as a flat key-value map.

The `vault_manager.py` script at `scripts/vault_manager.py` (in the btp-cope-extractor repo) provides all CRUD operations. Auth is resolved automatically from `~/.vault-token-btp`.

## When to Use This Skill

- User asks about Vault secrets for any BTP service
- User wants to read, update, compare, or export environment configs
- User wants to check what services exist in an environment
- User needs to rotate or modify a secret value
- User wants to sync or compare configs across DEV/QA/PROD
- User asks "what's the value of X in PROD?" for any config key
- User wants to add a new config key to a service
- User asks about config drift between environments

## Safety Principles

These matter because a mistake in Vault can take down production services.

1. **Dry-run first** — Always use `--dry-run` before any mutation (update, add, delete, bulk-update). Show the user what would change before executing.
2. **Confirm deletes** — The script requires `--confirm` for deletes and will refuse without it. Never bypass this.
3. **Compare before promoting** — Before syncing config across environments, run `compare` to show the diff.
4. **Export before bulk changes** — Take a backup with `export` before any bulk-update.
5. **update vs add** — `update` fails if the key doesn't exist (prevents typo-created phantom keys). `add` fails if the key already exists. Use the right one.
6. **Sensitive masking** — Keys containing password, secret, key, token, or salt are automatically masked in `read` output. Use `get` or `export` for unmasked values.

## Quick Reference — Intent to Command

| User wants to... | Command |
|---|---|
| List environments | `python3 scripts/vault_manager.py envs` |
| List services in an env | `python3 scripts/vault_manager.py services --env DEV` |
| See all config for a service | `python3 scripts/vault_manager.py read --env DEV --service COPE-API` |
| Get a specific value | `python3 scripts/vault_manager.py get --env DEV --service COPE-API --key AWS_DEFAULT_REGION` |
| Update an existing key | `python3 scripts/vault_manager.py update --env DEV --service COPE-API --key LOG_LEVEL --value DEBUG --dry-run` |
| Add a new key | `python3 scripts/vault_manager.py add --env DEV --service COPE-API --key NEW_KEY --value val --dry-run` |
| Delete a key | `python3 scripts/vault_manager.py delete --env DEV --service COPE-API --key OLD_KEY --dry-run` |
| Bulk update from JSON | `python3 scripts/vault_manager.py bulk-update --env DEV --service COPE-API --data '{"K":"V"}' --dry-run` |
| Compare across envs | `python3 scripts/vault_manager.py compare --service COPE-API --envs DEV QA PROD` |
| Export for backup | `python3 scripts/vault_manager.py export --env PROD --service COPE-API > backup.json` |

Use `--json` on read commands when you need to parse output programmatically. The script runs with `python3` and resolves Vault auth automatically.

## Safety Workflows

**Sync DEV config to QA:**
1. `compare --service X --envs DEV QA` — see what differs
2. `export --env DEV --service X > /tmp/dev-backup.json` — backup source
3. `export --env QA --service X > /tmp/qa-backup.json` — backup target
4. `bulk-update --env QA --service X --data '...' --dry-run` — preview changes
5. Remove the `--dry-run` to execute

**Rotate a secret:**
1. `get --env PROD --service X --key SECRET_KEY` — check current value
2. `update --env PROD --service X --key SECRET_KEY --value NEW_VALUE --dry-run` — preview
3. Remove `--dry-run` to execute
4. `get --env PROD --service X --key SECRET_KEY` — verify

**Add config for a new service:**
1. Prepare a JSON file with all key-value pairs
2. `bulk-update --env DEV --service NEW-SERVICE --data '...' --dry-run` — preview
3. Remove `--dry-run` to execute
4. Repeat for QA and PROD with environment-appropriate values

## Deeper Reference

- For Vault architecture details (path hierarchy, environments, services, auth model): consult `references/01-vault-structure.md`
- For full CLI reference, error handling, and importable Python usage: consult `references/02-operations-guide.md`
