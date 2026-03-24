---
name: beam2-sso
description: Use when debugging, extending, or explaining the beam2 SAML SSO system. Covers the full auth flow from Shibboleth SP relay (*.monigle.net) to PHP hash handler to beam2 LoginAction to JIT user provisioning. Includes known failure modes (expired accounts, hash mismatch, empty email, first-login password bug), salt validation mechanics, idmadmin settings, and client configuration. Client-agnostic, applies to all beam2 tenants using SSO (Okta, OneLogin, Azure AD, IBM FIM, etc.). Use when a user is redirected to /site/login/ after SSO, when setting up a new SSO client, or when tracing attribute mapping from IdP through to beam2 user provisioning.
---

# beam2 SSO Skill

## Overview

beam2 uses a Shibboleth SP relay architecture for SAML SSO. A single relay server (`10.132.63.235`) handles all clients; each client has its own domain (`{client_id}.monigle.net`), IdP configuration, and cryptographic salt. After IdP authentication, a PHP handler generates a `sha256(email|salt)` hash and redirects to the beam2 app, which revalidates the hash and provisions or authenticates the user.

## System Architecture

```
Browser → {client}.monigle.net (Shibboleth relay, 10.132.63.235)
              ↕ SAML
          IdP (Okta / OneLogin / Azure AD / IBM FIM)
              ↓ sha256 hash + SAML attributes
          brand.{client}.com/api/sso/login/ (beam2 app server)
              ↓
          JIT provisioning or account update → authenticated session
```

See `references/architecture.md` for component map, file locations, and logging paths.

## Authentication Flow Summary

Complete 15-step flow is in `references/authentication-flow.md`.

**Critical path**:
1. Shibboleth creates session after IdP auth (`shibd.log`: `new session created`)
2. PHP extracts `$_SERVER["email"]`, computes `sha256(email|salt)` → `HTTP_SHIBSESSIONID`
3. Redirect to beam2 with all params including the hash
4. beam2 recomputes hash using `idmadmin.sso.salt`, rejects if mismatch
5. User lookup → `createAccount()` (JIT) or update password hash
6. `UserIdentity::authenticate()` → checks password, IsActive, `isExpired()` → session

## Debugging: User Lands on /site/login/

Work through in order. Full details in `references/troubleshooting.md`.

**Step 1** — Did Shibboleth create a session?
```bash
ssh ubuntu@10.132.63.235
tail -f /var/log/shibboleth/shibd.log | grep {client_id}
# Must see: "new session created: ID (...)"
```
If missing: user not assigned to the SAML app in the IdP. Fix in IdP admin console.

**Step 2** — Did PHP redirect to beam2?
```bash
tail /var/www/{client_id}.monigle.net/logs/access.log
# After SAML POST, expect: GET / → 302 ~4000+ bytes (full redirect to beam2)
# 302 ~500 bytes = short redirect; email likely empty
```

**Step 3** — Verify the hash
```bash
echo -n "{HTTP_MAIL}|{sso.salt from idmadmin}" | sha256sum
# Must match HTTP_SHIBSESSIONID in beam2 access log
grep 'api/sso/login' /var/log/apache2/{client}-access.log | tail -3
```

**Step 4** — Check account status
```sql
SELECT IsActive, IsDeleted, ActiveUntil FROM idmuseraccount
WHERE EmailAddress = '{email}';
-- ActiveUntil in the past = account expired
UPDATE idmuseraccount SET ActiveUntil = NULL WHERE UserAccountID = X;
```

## Salt Configuration

Three locations must all contain the same UUID. Any divergence = silent hash failure → `/site/login/`.

| Location | Format |
|----------|--------|
| `vault/client_secrets.yml` | `vault_{client_id}_salt: "uuid"` |
| `/var/www/{client}.monigle.net/index.php` | `$salt = "uuid";` |
| `idmadmin` DB table | `key='sso.salt', value='uuid'` |

## User Provisioning

- JIT (default): accounts auto-created on first successful SSO login
- Role: from `idmadmin.default.sso.role`, or from IdP group attribute via `ClientSSO::createAccount()` role map
- **Known bug**: first login for a brand-new user fails — `ClientSSO::createAccount()` incorrectly sets `$this->_password` to the bcrypt hash instead of plaintext. Retry once; second attempt (existing user path) succeeds.
- Manual provisioning: create via `/panel/account/add/` using the same email address as the IdP identity

## Key idmadmin Settings

```sql
SELECT data_type, `key`, value FROM idmadmin WHERE `key` LIKE '%sso%';
```

| key | purpose |
|-----|---------|
| `sso.salt` | shared secret for hash validation (must match index.php) |
| `sso.seconds` | max token age in seconds (0 or absent = disabled) |
| `default.sso.role` | role ID assigned to JIT-provisioned users |
| `sso.login` | feature flag to enable/disable SSO globally |
| `login.page.url.sso.button` | SSO button URL shown on the login page |

## Adding a New Client

Full 7-step process in `references/client-management.md`:

1. Create `client_configs/active/{client_id}.yml`
2. Add IdP metadata XML to `roles/shibboleth/files/`
3. Add salt to Ansible vault (`vault/client_secrets.yml`)
4. Configure beam2 `idmadmin`: `sso.salt`, `default.sso.role`, `sso.login`
5. Create `{client}/client-objects/ClientSSO.php` (if custom role mapping needed)
6. Deploy: `ansible-playbook playbooks/deploy_client.yml --extra-vars "client_id=..."`
7. Verify with `playbooks/verify.yml`

## Infrastructure Quick Reference

| Resource | Value |
|----------|-------|
| Shibboleth relay | `ssh ubuntu@10.132.63.235` |
| Gartner app server | `ssh ubuntu@10.132.62.169` |
| SSH key | `~/Work/MediaValet/AWS/beam2_prod_infrastructure.pem` |
| DB write | `maindb.beam2.monigle.net` (user: `root`) |
| DB read | `reporting.beam2.monigle.net` (user: `prodreporting`) |
| Ansible source | `infrastructure/environment/beam2-cloud-infrastructure/ansible-shibboleth-sso/` |
| Full system doc | `BEAM2_SSO_SYSTEM.md` in that directory |

## References

- `references/architecture.md` — component map, servers, all config file paths
- `references/authentication-flow.md` — complete 15-step flow with code snippets
- `references/troubleshooting.md` — issue table, diagnostic commands, DB queries
- `references/client-management.md` — adding clients, attribute mapping, salt rotation
