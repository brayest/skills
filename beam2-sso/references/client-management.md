# beam2 SSO Client Management

## Adding a New SSO Client

### 1. Create the client config YAML

File: `client_configs/active/{client_id}.yml`

```yaml
client_id: "myclientsso"
domain: "myclientsso.monigle.net"
status: "active"

# Apache vhost
server_name: "myclientsso.monigle.net"
document_root: "{{ web_root_base }}/myclientsso.monigle.net"
error_log: "{{ web_root_base }}/myclientsso.monigle.net/logs/error.log"
access_log: "{{ web_root_base }}/myclientsso.monigle.net/logs/access.log"

# Shibboleth configuration
idp_type: "okta"             # okta | onelogin | azure_ad | google | ibm_fim | generic
idp_entity_id: "https://..."  # From IdP SAML settings
metadata_source_type: "file"
metadata_filename: "myclientsso-IDP-metadata.xml"

# SP certificate (shared)
sp_certificate_name: "monigle"

# PHP relay
salt: "{{ vault_myclientsso_salt }}"
sso_destination_url: "https://brand.myclient.com/api/sso/login/"
fallback_email_domain: "myclient.com"

# Optional extra attributes
optional_attributes: {}
```

### 2. Add IdP metadata file

Download the IdP's SAML metadata XML and place it at:
```
roles/shibboleth/files/myclientsso-IDP-metadata.xml
```

### 3. Add salt to Ansible vault

```bash
ansible-vault edit vault/client_secrets.yml
# Add line:
# vault_myclientsso_salt: "generate-a-uuid-here"
```

Generate a UUID: `python3 -c "import uuid; print(uuid.uuid4())"`

### 4. Configure beam2 app side

On the beam2 app server for this client:

```sql
-- Set the salt (must match vault_myclientsso_salt)
UPDATE idmadmin SET value = 'same-uuid-as-vault' WHERE `key` = 'sso.salt';

-- Or insert if not present
INSERT INTO idmadmin (data_type, `key`, lang, value)
VALUES ('string', 'sso.salt', 'en', 'same-uuid-as-vault');

-- Ensure SSO is enabled
UPDATE idmadmin SET value = 'true' WHERE data_type = 'feature' AND `key` = 'sso.login';

-- Set default role for JIT users (get role IDs: SELECT * FROM userroletype)
UPDATE idmadmin SET value = '{role_id}' WHERE data_type = 'feature' AND `key` = 'default.sso.role';

-- Set SSO button URL on login page
UPDATE idmadmin SET value = 'https://myclientsso.monigle.net/'
WHERE data_type = 'string' AND `key` = 'login.page.url.sso.button';
```

### 5. Create ClientSSO override (optional)

If the client needs custom role mapping or validation, create:
`{client}/client-objects/ClientSSO.php`

```php
class ClientSSO extends SSO {
    public $HTTP_ROLE;

    public function rules() {
        return array(
            array('HTTP_MAIL', 'required'),
            array('HTTP_MAIL', 'email', 'pattern' => '/^((?!monigle).)*$/i'),
            array('HTTP_GIVENNAME, HTTP_MAIL, ..., HTTP_ROLE', 'length', 'max' => 255)
        );
    }

    public function createAccount() {
        // ... custom role mapping from $this->HTTP_ROLE
    }
}
```

### 6. Deploy

```bash
cd ansible-shibboleth-sso/

# Deploy single client only
ansible-playbook playbooks/deploy_client.yml \
  -i inventory/production.yml \
  --extra-vars "client_id=myclientsso" \
  --ask-vault-pass

# Or full redeploy
ansible-playbook playbooks/site.yml -i inventory/production.yml --ask-vault-pass
```

### 7. Verify

```bash
ansible-playbook playbooks/verify.yml \
  -i inventory/production.yml \
  --extra-vars "client_id=myclientsso"
```

Then test the SSO flow manually:
1. Hit `https://myclientsso.monigle.net/`
2. Should redirect to IdP login
3. After login, should redirect to `brand.myclient.com`
4. Check `shibd.log` for session creation

---

## Archiving a Client

Move the config file:
```bash
mv client_configs/active/{client_id}.yml client_configs/archived/
```

Redeploy to remove the client from the Shibboleth config and disable the Apache vhost.

---

## Updating IdP Metadata

```bash
# Place new metadata file
cp new-idp-metadata.xml roles/shibboleth/files/{client_id}-IDP-metadata.xml

# Redeploy metadata only
ansible-playbook playbooks/update_idp_metadata.yml \
  -i inventory/production.yml \
  --extra-vars "client_id={client_id}" \
  --ask-vault-pass
```

Shibboleth reloads metadata automatically every 7200 seconds (`reloadInterval`). To force immediate reload:
```bash
ssh ubuntu@10.132.63.235
sudo systemctl restart shibd
```

---

## Rotating a Client Salt

**Important**: Salt rotation must be done atomically — both sides must be updated simultaneously or SSO will fail for active users.

1. Generate new UUID
2. Update Ansible vault: `ansible-vault edit vault/client_secrets.yml`
3. Update beam2 DB: `UPDATE idmadmin SET value = 'new-uuid' WHERE key = 'sso.salt'`
4. Redeploy relay: `ansible-playbook playbooks/deploy_client.yml --extra-vars "client_id={id}"`

---

## Client Config Schema Reference

| Field | Required | Purpose |
|-------|----------|---------|
| `client_id` | Yes | Unique identifier, used in file names and XML IDs |
| `domain` | Yes | Apache ServerName for the relay vhost |
| `idp_type` | Yes | Controls which attribute-map template is used |
| `idp_entity_id` | Yes | IdP EntityID from their SAML metadata |
| `metadata_source_type` | Yes | `file` (from files/) or `url` (fetched at runtime) |
| `metadata_filename` | Yes (if `file`) | Filename in `roles/shibboleth/files/` |
| `sp_certificate_name` | Yes | SP cert name — `monigle` uses shared wildcard cert |
| `salt` | Yes | Vault reference: `{{ vault_{client_id}_salt }}` |
| `sso_destination_url` | Yes | beam2 app SSO endpoint URL |
| `fallback_email_domain` | Yes | Domain for `no_email_account@` fallback |
| `optional_attributes` | No | Additional SAML attributes to map (beyond email/name) |

---

## Attribute Mapping by IdP Type

### Okta (`idp_type: okta`)
```xml
<Attribute name="email"     nameFormat="basic" id="email"/>
<Attribute name="firstName" nameFormat="basic" id="firstname"/>
<Attribute name="lastName"  nameFormat="basic" id="lastname"/>
<Attribute name="groups"    nameFormat="basic" id="groups"/>
```

### OneLogin (`idp_type: onelogin`)
```xml
<Attribute name="email"     nameFormat="basic" id="email"/>
<Attribute name="firstname" nameFormat="basic" id="firstname"/>
<Attribute name="lastname"  nameFormat="basic" id="lastname"/>
<Attribute name="groups"    nameFormat="basic" id="groups"/>
```

### Azure AD (`idp_type: azure_ad`)
```xml
<Attribute name="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
           nameFormat="unspecified" id="email"/>
<Attribute name="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname"
           nameFormat="unspecified" id="firstname"/>
<Attribute name="http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname"
           nameFormat="unspecified" id="lastname"/>
```

The `id` value (e.g. `"email"`) becomes `$_SERVER["email"]` in PHP due to `ShibUseEnvironment On`.

---

## `idmadmin` Settings Reference

Query all SSO settings:
```sql
SELECT data_type, `key`, value FROM idmadmin WHERE `key` LIKE '%sso%';
```

| key | data_type | Purpose | Default |
|-----|-----------|---------|---------|
| `sso.salt` | string | Shared secret for hash | Must set |
| `sso.seconds` | string | Token max age (0=disabled) | absent/0 |
| `sso.login` | feature | Enable SSO globally | true |
| `sso.popup` | feature | Show popup on login | false |
| `sso.xframes` | feature | X-Frame-Options for SSO pages | true |
| `default.sso.role` | feature | Default role ID for JIT users | Must set |
| `login.page.url.sso.button` | string | SSO button URL on login page | Must set |
