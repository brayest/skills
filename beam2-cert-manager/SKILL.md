---
name: beam2-cert-manager
description: Use when renewing any beam2 certificate. Routes between two systems — (1) HCP Vault at http://vault.monigle-utility.int for brand-portal client TLS certs (Corteva, Anthem, Deloitte), and (2) the ansible-shibboleth-sso repo for beam2 SSO certs (Shibboleth SP signing certs `monigle`/`monigle2`, Apache wildcard `*.monigle.net`/`*.monigle2.net`, and per-client IdP metadata XML). Trigger on any of: renew/rotate cert, CSR, SSL renewal, SP cert, SAML signing cert, IdP metadata, shibboleth cert, `*.monigle.net` wildcard, `update {client}sso metadata`, or specific client IDs (allstatesso, cortevasso, gartnersso2/3, bcbsasso, aigsso2, bnymsso2, cgisso, chevronsso, deloitte2sso, petrocanadasso2, rbcsso2, storyspacesso, suttersso).
---

# beam2 Certificate Manager

## Which flow?

beam2 has **two independent cert systems**. Identify which the user is asking about before doing anything else.

| Ask / symptom | Cert category | System | Reference |
|---|---|---|---|
| "Renew Corteva / Anthem / Deloitte portal cert" — brand-portal TLS (`brandcenter.corteva.com`, `brandhub.elevancehealth.com`, etc.) | Per-client brand-portal TLS | HCP Vault `kv/CLIENTS/{CLIENT_NAME}` at `http://vault.monigle-utility.int` | [references/renewal-process.md](references/renewal-process.md) |
| "Renew `monigle` SP cert" / "SAML signing cert expired" / "Shibboleth SP cred" | Shibboleth SP signing cert (`monigle`, `monigle2`) | `ansible-shibboleth-sso/vault/certificates.yml` (ansible-vault) | [references/ansible-sso-certs.md §1 SP signing certs](references/ansible-sso-certs.md) |
| "Renew `*.monigle.net` / `*.monigle2.net` wildcard" | Apache wildcard SSL | `ansible-shibboleth-sso/vault/certificates.yml` (ansible-vault) | [references/ansible-sso-certs.md §2 Apache wildcard SSL](references/ansible-sso-certs.md) |
| "Update IdP metadata for {client}sso" / "Client's IdP cert rotated" / "Allstate sent new metadata" | Per-client IdP metadata XML (contains IdP signing cert) | Plaintext at `ansible-shibboleth-sso/roles/shibboleth/files/{env}/{client}-IDP-metadata.xml` | [references/ansible-sso-certs.md §3 Per-client IdP metadata](references/ansible-sso-certs.md) |

**Disambiguation rules**:
- `*sso.monigle.net` / `*sso.monigle2.net` → ansible flow.
- Brand-portal domains (custom client TLDs like `*.corteva.com`, `*.elevancehealth.com`, `*.deloitte.com`) → HCP Vault flow.
- If the user says "SSO cert" without qualifying further, ask whether they mean the shared SP cert (rotates everyone), the wildcard TLS, or a specific client's IdP metadata.

## Pre-flight (both flows)

1. Confirm **prod or staging** — the ansible flow has separate inventories and file trees per env; the HCP Vault flow is prod-only.
2. Required tools: `curl`, `jq`, `openssl`, plus `ansible`/`ansible-vault` for the ansible flow.
3. Credentials:
   - HCP Vault flow: token file at `~/.vault-token-xp`.
   - Ansible flow: vault password file at `~/.ansible/vault_password` (0600). Referenced by `ansible-shibboleth-sso/ansible.cfg`.
4. Ansible flow only: always `cd ansible-shibboleth-sso` before running playbooks. The `update_idp_metadata.yml` and `deploy_client.yml` playbooks use `delegate_to: localhost` with relative paths that resolve against `playbooks/` — running from anywhere else makes the `stat` tasks fail with "not found".

## Flow A — HCP Vault brand-portal TLS

CSR → CA → `curl` update into HCP Vault at `http://vault.monigle-utility.int` under `kv/CLIENTS/{CLIENT_NAME}` (standard fields: `KEY`, `CERTIFICATE`, `CERT_CHAIN` — plus client-specific metadata like DB creds, CAPTCHA keys, historical year keys that must be preserved on update).

Full 6-step workflow with client-specific examples (Corteva, Anthem, Deloitte): [references/renewal-process.md](references/renewal-process.md).

## Flow B — Ansible SSO certs

All three SSO cert categories live in the `ansible-shibboleth-sso/` repo at `/Users/brayest/Work/MediaValet/Repositories/infrastructure/environment/beam2-cloud-infrastructure/ansible-shibboleth-sso/`. Rotation is playbook-driven, not curl-driven:

- **SP signing certs** (`monigle`, `monigle2`) and **Apache wildcard SSL** live in encrypted `vault/certificates.yml` — edit via `ansible-vault edit`, deploy with `ansible-playbook ... --tags certificates`.
- **Per-client IdP metadata** is plaintext XML in `roles/shibboleth/files/{prod|staging}/{client}-IDP-metadata.xml`. Rotate via the dedicated `playbooks/update_idp_metadata.yml`.
- Post-rotation: run `ansible-playbook -i inventory/{env}.yml playbooks/verify.yml` (checks shibd/apache status, cert dates, metadata endpoints).

Full commands, file paths, variable names, blast-radius notes, and the known CWD quirk: [references/ansible-sso-certs.md](references/ansible-sso-certs.md).

## Cross-cutting rules

- **Always generate new private keys on renewal.** Never reuse.
- **Field preservation (HCP Vault flow):** the `kv/CLIENTS/{NAME}` secret holds cert + key + chain *and* unrelated client metadata (DB creds, API keys). Always read → preserve non-cert fields → write.
- **Never commit plaintext secrets.** HCP Vault cert material stays in Vault. Ansible-vault cert material stays encrypted in `vault/certificates.yml`. **Plaintext IdP metadata XML** *is* committed to git — that's expected; the cert inside is the IdP's public signing cert, not a secret.
- **Verify expiry before and after** rotation. `openssl x509 -noout -dates` on the deployed file on the server.
- **Blast radius awareness (ansible flow):** the shared `monigle` SP cert is used by nearly every prod SSO client. Rotating it re-keys SAML for all of them — coordinate with each client's IdP admin. The per-client IdP metadata, in contrast, only affects that one client.
