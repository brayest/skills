# beam2 SSO Troubleshooting

## Symptom: User redirected to `/site/login/` after SSO

Work through these checks in order.

### Step 1 — Did Shibboleth create a session?

```bash
ssh ubuntu@10.132.63.235
tail -50 /var/log/shibboleth/shibd.log | grep {client_id}
```

**Expected**: `new session created: ID (...) IdP (...)`

**If missing**: The problem is at the IdP layer — the user is not assigned to the SAML app in Okta/OneLogin/Azure AD. Fix: assign user in the IdP admin console.

**Warnings to note** (non-fatal):
- `skipping empty AttributeValue` — an attribute is empty (e.g. `groups`). Only a problem if it's `email`.
- `skipping SAML 2.0 Attribute with Name: ...` — attribute sent but not mapped. Usually fine.

---

### Step 2 — Did the PHP relay redirect to beam2?

```bash
tail -20 /var/www/{client_id}.monigle.net/logs/access.log
```

**Expected flow**:
1. `GET /` → 302 (Shibboleth initiates auth)
2. `POST /Shibboleth.sso/SAML2/POST` → 302 (Shibboleth processes SAML)
3. `GET /` → 302 ~4000+ bytes (PHP redirects to beam2)

**If step 3 shows 302 ~500 bytes**: PHP ran but didn't build the full redirect. The email might be empty → `no_email_account@domain` used.

**If step 3 shows 200 ~1600 bytes**: PHP is NOT redirecting — possible PHP error or `$display_all = true` in `index.php`.

---

### Step 3 — Did beam2 receive the request?

```bash
ssh ubuntu@{app_server}
grep 'api/sso/login' /var/log/apache2/{client}-access.log | tail -5
```

**Expected**: A `GET /api/sso/login/?HTTP_MAIL=user@domain.com&...&HTTP_SHIBSESSIONID=abc123...` entry.

Note the `HTTP_SHIBSESSIONID` value for step 4.

---

### Step 4 — Does the hash match?

```bash
# Compute expected hash
echo -n "{HTTP_MAIL_value}|{sso.salt_from_db}" | sha256sum
```

Get `sso.salt` from DB:
```sql
SELECT value FROM idmadmin WHERE `key` = 'sso.salt';
```

Compare the computed hash to the `HTTP_SHIBSESSIONID` in the access log.

**If they differ**: The salt in `index.php` on the relay server doesn't match the salt in beam2's `idmadmin`. Check the deployed `index.php` on the relay server and compare to the DB. Redeploy via Ansible if they diverged.

---

### Step 5 — Check the user account status

```sql
SELECT UserAccountID, EmailAddress, IsActive, IsDeleted, ActiveUntil, Notes
FROM idmuseraccount
WHERE EmailAddress = '{email}';
```

**Possible issues**:

| Field | Bad value | Fix |
|-------|-----------|-----|
| `IsActive` | 0 | `UPDATE idmuseraccount SET IsActive = 1 WHERE UserAccountID = X;` |
| `IsDeleted` | 1 | `UPDATE idmuseraccount SET IsDeleted = 0 WHERE UserAccountID = X;` |
| `ActiveUntil` | past date | `UPDATE idmuseraccount SET ActiveUntil = NULL WHERE UserAccountID = X;` |
| Row not found | — | Account wasn't JIT-created; check step 4 hash, or create manually via `/panel/account/add/` |

---

## Issue Reference Table

| Issue | Symptom | Root Cause | Fix |
|-------|---------|------------|-----|
| **Account expired** | `/site/login/` after SSO | `ActiveUntil` < today | `SET ActiveUntil = NULL` |
| **Hash mismatch** | `/site/login/` after SSO | Salt in index.php ≠ DB `sso.salt` | Compare and redeploy Ansible |
| **User not in IdP app** | Shibboleth session never created | Not assigned to SAML app | Assign in Okta/OneLogin admin |
| **Empty email from IdP** | Account `no_email_account@domain` created | IdP not sending `email` attribute | Fix attribute-map.xml; check IdP attribute config |
| **Account not created (first login)** | `/site/login/`, no account in DB | `createAccount()` failed silently | Check DB constraints; verify `default.sso.role` exists in `userroletype` |
| **First-login password bug** | `/site/login/` for brand-new user; account in DB with `IsActive=1` | `ClientSSO::createAccount()` sets `$this->_password` = hash not plaintext | Retry SSO once — second attempt succeeds |
| **`sso.seconds` rejection** | `/site/login/`; `sso.seconds` > 0 | index.php sends empty timestamp | Set `sso.seconds = 0` in `idmadmin`, or fix PHP to send timestamp |
| **Role doesn't exist** | Account created, no access | `default.sso.role` = non-existent role ID | Check `SELECT * FROM userroletype;` then fix `idmadmin` |
| **Validate() fails** | `/site/login/`; email from Monigle domain | Email matches `/monigle/i` regex | Monigle employees cannot use client SSO — expected |
| **SP cert expired** | SAML signature validation failure | `monigle-sp-cert-2026.pem` expired | Renew via beam2-cert-manager skill |

---

## Database Queries

```sql
-- Get all SSO-related admin settings
SELECT data_type, `key`, value FROM idmadmin WHERE `key` LIKE '%sso%';

-- Check if user exists and account status
SELECT UserAccountID, EmailAddress, IsActive, IsDeleted, ActiveUntil, JoinDate, LastLogin, Notes
FROM idmuseraccount WHERE EmailAddress = '{email}';

-- Check user's assigned roles
SELECT ur.role_id, utr.UserRoleTypeDescription
FROM users_roles ur
JOIN userroletype utr ON ur.role_id = utr.UserRoleTypeID
WHERE ur.user_id = {UserAccountID};

-- All available roles
SELECT UserRoleTypeID, UserRoleTypeDescription FROM userroletype ORDER BY UserRoleTypeID;

-- Fix expired account
UPDATE idmuseraccount SET ActiveUntil = NULL WHERE UserAccountID = {id};

-- Reactivate disabled account
UPDATE idmuseraccount SET IsActive = 1, IsDeleted = 0 WHERE UserAccountID = {id};
```

DB connection (from app server):
```bash
mysql -h maindb.beam2.monigle.net -u root -p{root_pass} {dbname}
# Read-only replica:
mysql -h reporting.beam2.monigle.net -u prodreporting -p{report_pass} {dbname}
```

---

## Enable Debug Mode (Temporarily)

To see all Shibboleth attributes being passed to PHP, temporarily set `$display_all = true` in the deployed `index.php`:

```bash
ssh ubuntu@10.132.63.235
# Edit /var/www/{client}.monigle.net/index.php
# Change: $display_all = false;
# To:     $display_all = true;
```

Then hit `https://{client_id}.monigle.net/` — you'll see all `$_SERVER` variables instead of a redirect. **Revert immediately after debugging.**

---

## Access Log Response Size Quick Reference

```bash
grep 'api/sso/login' /var/log/apache2/{client}-access.log | awk '{print $9, $10}' | tail -20
```

- `302 5000+` → SUCCESS (redirect to landing page)
- `302 500-900` → FAILURE (redirect to /site/login/)

Successful logins have a larger redirect body because the landing page URL is longer than `/site/login/`.
