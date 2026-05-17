# beam2 SSO Certificates — Ansible Flow

> **Scope**: All three cert categories managed by the `ansible-shibboleth-sso/` repo:
> §1 Shibboleth SP signing certs (`monigle`, `monigle2`)
> §2 Apache wildcard SSL (`*.monigle.net`, `*.monigle2.net`)
> §3 Per-client IdP metadata XML (contains the IdP's signing cert)
>
> **Not covered here**: HCP Vault-managed brand-portal TLS certs (Corteva, Anthem, Deloitte). See [`renewal-process.md`](renewal-process.md).

## Shared setup

**Repo root** (all commands assume you are `cd`'d here):
```
/Users/brayest/Work/MediaValet/Repositories/infrastructure/environment/beam2-cloud-infrastructure/ansible-shibboleth-sso
```

**Ansible-vault password file** — configured in `ansible.cfg`:
```
~/.ansible/vault_password   # 0600 permissions, never commit
```

**Inventories**:

| File | Host | `env_name` | SP entityID |
|---|---|---|---|
| `inventory/production.yml` | `10.132.63.235` | `prod` | `https://sp.monigle.net/shibboleth` |
| `inventory/staging.yml` | `10.131.50.113` | `staging` | `https://sp.monigle2.net/shibboleth` |

SSH key for both: `~/Work/MediaValet/AWS/beam2_prod_infrastructure.pem`, user `ubuntu`.

**Verify playbook** — run after any rotation:
```bash
ansible-playbook -i inventory/production.yml playbooks/verify.yml
# Checks: apache + shibd running, configs valid, SP+Apache cert dates via openssl,
# each client's https://{domain}/Shibboleth.sso/Metadata endpoint returns 200.
```

**CWD quirk** (applies to §3 and `deploy_client.yml`): the playbook tasks with `delegate_to: localhost` resolve relative paths against `playbooks/`, not your invocation CWD. Symptom: `FAILED! => {"msg": "Metadata file not found: roles/shibboleth/files/prod/...-IDP-metadata.xml"}` even when the file exists. Fix: `cd ansible-shibboleth-sso` before invoking, and pass absolute paths with `$PWD/...` for `new_metadata_path`.

**Inspecting encrypted vault content** (read-only):
```bash
ansible-vault view vault/certificates.yml
ansible-vault view vault/client_secrets.yml
```
**Editing** (decrypts to a tmpfile, opens `$EDITOR`, re-encrypts on save):
```bash
ansible-vault edit vault/certificates.yml
```

**Never commit** decrypted vault output. The plaintext IdP metadata XML (§3) *is* committed — that's public IdP info.

---

## §1 Shibboleth SP signing certs (`monigle`, `monigle2`)

SAML SP credentials used by Shibboleth to sign/decrypt assertions. The `monigle` cert is the default for every client unless overridden. `monigle2` is the staging/secondary set.

### Where it lives

| Layer | Location |
|---|---|
| Encrypted source | `vault/certificates.yml` |
| Variables | `vault_monigle_sp_cert_2026`, `vault_monigle_sp_key_2026`, `vault_monigle2_sp_cert_2026`, `vault_monigle2_sp_key_2026` |
| Wiring | `inventory/group_vars/shibboleth_servers.yml:19-32` — `sp_certificates.{monigle,monigle2}.{cert,key}_content` |
| Deployed to server | `/etc/shibboleth/monigle-sp-{cert,key}-2026.pem`, `/etc/shibboleth/monigle2-sp-{cert,key}-2026.pem` |
| Deploy task | `roles/shibboleth/tasks/main.yml:25-47` (`copy` module, cert 0644, key 0600, owner `_shibd:_shibd`) |
| Consumed at runtime | `roles/shibboleth/templates/shibboleth2.xml.j2` → `<CredentialResolver>` |
| Per-client override | `client_configs/{env}/active/{client}.yml` key `sp_certificate_name: monigle|monigle2` (default `monigle` — set in `shibboleth_servers.yml:19` as `sp_certificate_default`) |
| Handler | `restart shibd` (on cert change) |

### Rotation workflow

1. **Obtain** new cert + key from CA (see §2 — currently the SP cert and Apache wildcard share the same DigiCert-issued wildcard, so one CSR covers both).
2. **Edit vault** — keep variable names, replace only the content:
   ```bash
   cd ansible-shibboleth-sso
   ansible-vault edit vault/certificates.yml
   ```
   Replace the body of `vault_monigle_sp_cert_2026`, `vault_monigle_sp_key_2026`, and the `monigle2` pair if also rotating. Preserve YAML indentation (leading 2-space indent on every line of the `|` literal block).
3. **Deploy**:
   ```bash
   ansible-playbook -i inventory/production.yml playbooks/site.yml --tags certificates
   ```
   Triggers `restart shibd` via handler.
4. **Verify**:
   ```bash
   ansible-playbook -i inventory/production.yml playbooks/verify.yml
   ssh ubuntu@10.132.63.235 -i ~/Work/MediaValet/AWS/beam2_prod_infrastructure.pem \
     'openssl x509 -in /etc/shibboleth/monigle-sp-cert-2026.pem -noout -dates -subject'
   ```
5. **Publish new SP metadata to IdPs** — each client's IdP admin may need to re-import the new public cert. Give them:
   ```
   https://{client}.monigle.net/Shibboleth.sso/Metadata
   ```

### Blast radius

Rotating `monigle` re-keys SAML for **every prod client using the default** — currently all 15 except any that set `sp_certificate_name: monigle2`. Before rotating:
```bash
grep -l "sp_certificate_name" client_configs/prod/active/*.yml
```
Staging uses the same `monigle` default in its client configs (confirmed in `client_configs/staging/active/allstatesso.yml`), so rotating on staging exercises the same code path. Use staging to dry-run first.

---

## §2 Apache wildcard SSL (`*.monigle.net`, `*.monigle2.net`)

Serves HTTPS for all `{client}.monigle.net` (prod) and `{client}.monigle2.net` (staging) subdomains.

### Where it lives

| Layer | Location |
|---|---|
| Encrypted source | `vault/certificates.yml` |
| Variables | `vault_apache_ssl_cert`, `vault_apache_ssl_key`, `vault_apache_ssl_chain` |
| Wiring | `inventory/group_vars/shibboleth_servers.yml:34-41` — `apache_ssl_cert_content` / `_key_content` / `_chain_content` |
| Deployed to server | `/etc/apache2/ssl/star.monigle.net.crt`, `.key`, `-int.crt` |
| Deploy task | `roles/apache/tasks/main.yml:34-53` (cert+chain 0644, key 0600, owner `root:root`) |
| Handler | `restart apache2` |

### Rotation workflow

1. **Generate CSR** locally — the CN should be `*.monigle.net` (and a separate one for `*.monigle2.net`):
   ```bash
   openssl genrsa -out star.monigle.net.key 2048
   chmod 600 star.monigle.net.key
   openssl req -new -key star.monigle.net.key -out star.monigle.net.csr \
     -subj "/C=US/ST=Colorado/L=Denver/O=Monigle Associates Inc./CN=*.monigle.net" \
     -addext "subjectAltName=DNS:*.monigle.net,DNS:monigle.net"
   ```
   Confirm the subject matches the current cert first:
   ```bash
   ansible-vault view vault/certificates.yml | grep -A100 'vault_apache_ssl_cert:' | head -40 \
     | sed 's/^  //' | openssl x509 -noout -subject -issuer
   ```
2. **Submit to DigiCert**, receive new `.crt` + intermediate chain.
3. **Edit vault** — replace all three of `vault_apache_ssl_cert`, `vault_apache_ssl_key`, `vault_apache_ssl_chain`:
   ```bash
   ansible-vault edit vault/certificates.yml
   ```
4. **Deploy**:
   ```bash
   ansible-playbook -i inventory/production.yml playbooks/site.yml --tags certificates
   ```
5. **Verify**:
   ```bash
   ssh ubuntu@10.132.63.235 -i ~/Work/MediaValet/AWS/beam2_prod_infrastructure.pem \
     'openssl x509 -in /etc/apache2/ssl/star.monigle.net.crt -noout -dates -subject'
   # And from the client side:
   openssl s_client -connect allstatesso.monigle.net:443 -servername allstatesso.monigle.net </dev/null 2>/dev/null \
     | openssl x509 -noout -dates -subject
   ```

### Shared-cert gotcha

As of the 2025-01-07 → 2026-02-07 rotation, the `vault_monigle_sp_cert_2026` and `vault_apache_ssl_cert` variables hold the **same DigiCert-issued `*.monigle.net` wildcard** (verified by decrypt + `openssl x509 -noout -subject` — same CN, same issuer). Renewing the DigiCert wildcard therefore covers both §1 and §2 — update all the cert/key variables in one `ansible-vault edit` session, deploy once with `--tags certificates`. The `monigle2` set is the equivalent `*.monigle2.net` wildcard.

This is convenient today but not structurally guaranteed. If the org ever decides to separate SAML-signing credentials from public TLS (recommended security-wise — SAML signing doesn't need a public-CA cert), §1 and §2 will diverge.

---

## §3 Per-client IdP metadata

SAML 2.0 metadata XML from each client's IdP (Okta, Azure AD, Google, IBM FIM, etc.). Contains the IdP's signing certificate inside `<md:KeyDescriptor use="signing"><ds:X509Certificate>...`. Shibboleth validates every incoming assertion against these certs.

### Where it lives

| Layer | Location |
|---|---|
| Plaintext source (committed to git) | `roles/shibboleth/files/{prod|staging}/{client_id}-IDP-metadata.xml` |
| Active clients (prod) | 15: `aigsso2`, `allstatesso`, `bcbsasso`, `bcbsasso2`, `bcbsasso3`, `bnymsso2`, `cgisso`, `chevronsso`, `cortevasso`, `deloitte2sso`, `gartnersso2`, `petrocanadasso2`, `rbcsso2`, `storyspacesso`, `suttersso` |
| Active clients (staging) | Above + `gartnersso3` (16 total) |
| Client config referencing it | `client_configs/{env}/active/{client_id}.yml` keys `metadata_source_type: file` + `metadata_filename: "{{ client_id }}-IDP-metadata.xml"` |
| Deployed to server | `/etc/shibboleth/{client_id}-IDP-metadata.xml` (owner `_shibd:_shibd`, 0644) |
| Deploy tasks | Bulk: `roles/shibboleth/tasks/main.yml:70-80`. Single client: `playbooks/deploy_client.yml:105-131`. Targeted update: `playbooks/update_idp_metadata.yml:79-86` |
| Handler | `restart shibd` |

### When this rotates

- Client's IdP rotates their signing cert (most common — IdP certs are 1-2 year lifetimes).
- Client changes IdP vendor (Okta → Azure AD, etc.) — also likely brings a new `idp_entity_id`, which requires a `client_configs/` change too.
- Client federation adds/removes endpoints (SingleLogoutService, NameIDFormat).

### Rotation workflow

1. **Receive** the new metadata XML from the client's IdP admin. Save to an absolute path:
   ```
   ~/Downloads/{client_id}-IDP-metadata-NEW.xml
   ```
2. **Sanity-check** before deploying — verify all embedded signing certs are valid and not yet expired:
   ```bash
   python3 <<'PY'
   import re, sys
   xml = open('/tmp/new-metadata.xml').read()
   for i, b64 in enumerate(re.findall(r'<(?:ds:)?X509Certificate>\s*([^<]+?)\s*</(?:ds:)?X509Certificate>', xml)):
       b64 = re.sub(r'\s+','',b64)
       pem = '-----BEGIN CERTIFICATE-----\n' + '\n'.join(b64[j:j+64] for j in range(0,len(b64),64)) + '\n-----END CERTIFICATE-----\n'
       open(f'/tmp/idp-{i}.pem','w').write(pem)
       print(f'--- cert[{i}] ---')
   PY
   for f in /tmp/idp-*.pem; do openssl x509 -in "$f" -noout -subject -startdate -enddate; done
   rm /tmp/idp-*.pem
   ```
   Multi-cert metadata is normal — many IdPs ship two `<KeyDescriptor use="signing">` blocks during a rollover window. Shibboleth accepts signatures from any of them.
3. **Deploy** via the dedicated playbook:
   ```bash
   cd ansible-shibboleth-sso   # REQUIRED — see CWD quirk above
   ansible-playbook -i inventory/production.yml playbooks/update_idp_metadata.yml \
     -e client_name=allstatesso \
     -e "new_metadata_path=$HOME/Downloads/allstatesso-IDP-metadata-NEW.xml"
   ```
   Or omit `-e` and answer the `vars_prompt` interactively. Absolute path required either way.
4. **What the playbook does** (`playbooks/update_idp_metadata.yml:1-106`):
   - Validates the client config exists.
   - Validates the new file exists and contains `entityID`.
   - Backs up `roles/shibboleth/files/{env}/{client}-IDP-metadata.xml` to `.bak`.
   - Copies new file into the repo (overwrites `roles/shibboleth/files/{env}/{client}-IDP-metadata.xml`).
   - Copies to `/etc/shibboleth/{client}-IDP-metadata.xml` on the server.
   - Triggers `restart shibd`.
5. **Verify**:
   ```bash
   ssh ubuntu@10.132.63.235 -i ~/Work/MediaValet/AWS/beam2_prod_infrastructure.pem \
     'sudo grep -i "loaded\|'"$CLIENT"'" /var/log/shibboleth/shibd.log | tail -20'
   # End-to-end: browse to https://{client_id}.monigle.net/ and attempt SSO.
   ```
6. **Commit the repo change**:
   ```bash
   git add roles/shibboleth/files/prod/allstatesso-IDP-metadata.xml
   git diff --staged roles/shibboleth/files/prod/allstatesso-IDP-metadata.xml.bak \
                      roles/shibboleth/files/prod/allstatesso-IDP-metadata.xml
   git commit -m "Update IdP metadata for allstatesso (IdP cert rotation)"
   # Clean up the .bak (or gitignore it)
   rm roles/shibboleth/files/prod/allstatesso-IDP-metadata.xml.bak
   ```

### Alternative: edit in-place + bulk deploy

If you edit the committed XML file directly (e.g. the client sent a diff, not a full replacement):
```bash
# After editing roles/shibboleth/files/prod/{client}-IDP-metadata.xml
ansible-playbook -i inventory/production.yml playbooks/site.yml --tags metadata --limit shibboleth_servers
```
The `metadata` tag on the bulk task in `roles/shibboleth/tasks/main.yml:70-80` loops through all `active_clients` and copies each file. Idempotent — only changed files trigger the handler.

### What you never touch

- `idp_entity_id` in the metadata — if it changes, also update `client_configs/{env}/active/{client}.yml`, otherwise Shibboleth rejects assertions with "entityID mismatch".
- The bundled IdP SLO / SSO endpoints — if those move, the client-sent metadata will already reflect that.

---

## Troubleshooting

### `ansible-vault`: "Decryption failed"
Password in `~/.ansible/vault_password` is wrong or file doesn't exist. Check `ansible.cfg` `vault_password_file` line.

### `update_idp_metadata.yml` fails with "Metadata file not found" even though the file exists
CWD quirk — see **Shared setup** above. Fix: `cd ansible-shibboleth-sso` first, and pass `-e "new_metadata_path=$PWD/..."` or use a fully absolute path.

### After rotation, a specific client gets "invalid signature" / "signature validation failed"
- Wrong cert for the wrong client (metadata file got mixed up). Diff the `.bak` vs current and confirm the `entityID` matches what the client config expects.
- Clock skew on the server — `shibboleth_clock_skew` is set to 180s (`shibboleth_servers.yml:10`); check server time.
- IdP still signing with old cert during overlap window. Wait or ask IdP admin to confirm which cert is active.

### After SP cert rotation (§1), some clients fail SSO
Those IdPs still have the old SP public cert pinned. Send them the new SP metadata URL (`https://{client}.monigle.net/Shibboleth.sso/Metadata`) and have their admin re-import.

### Apache wildcard (§2) rotation breaks DigiCert chain validation
Make sure you updated `vault_apache_ssl_chain` with the **intermediate** chain (not the root, not the end-entity cert). Verify locally before deploy:
```bash
openssl verify -CAfile chain.crt star.monigle.net.crt
# should print: star.monigle.net.crt: OK
```
