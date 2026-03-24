# beam2 SSO Architecture

## System Components

The beam2 SSO system has three layers: a Shibboleth relay server, the IdP, and the beam2 application server.

```
Browser → Shibboleth Relay (*.monigle.net) ↔ IdP (Okta/OneLogin/Azure/etc.)
                    ↓
            beam2 App Server (brand.{client}.com)
                    ↓
            MySQL Database (idmadmin + idmuseraccount)
```

### Shibboleth Relay Server (`10.132.63.235`)

Single server hosting ALL clients. Each client gets its own Apache vhost and PHP relay:

- Apache 2.4 + mod_shib 3.x + PHP 8.3
- Handles SAML authentication against the IdP
- Extracts user attributes, generates hash, redirects to beam2
- Managed by Ansible: `infrastructure/environment/beam2-cloud-infrastructure/ansible-shibboleth-sso/`

**Key config files on the server:**

```
/etc/shibboleth/
├── shibboleth2.xml                 # Main SP config (auto-generated from Ansible)
├── {client}-IDP-metadata.xml       # IdP SAML metadata per client
├── {client}-attribute-map.xml      # Maps SAML attributes → $_SERVER keys
├── monigle-sp-cert-2026.pem        # Shared SP certificate
└── monigle-sp-key-2026.pem         # SP private key

/var/www/{client_id}.monigle.net/
├── index.php                       # PHP relay handler (auto-generated)
└── logs/
    ├── access.log                  # Per-client access log
    └── error.log
```

**Apache vhost pattern (same for every client):**

```apache
<Location />
    AuthType shibboleth
    ShibRequestSetting requireSession 1
    Require valid-user
    ShibUseEnvironment On           # Attributes in $_SERVER, not headers
</Location>
<Location /Shibboleth.sso>
    SetHandler shib                 # Shibboleth handler endpoint
</Location>
```

### beam2 Application Server

Each beam2 tenant runs on a separate app server. For gartner: `10.132.62.169`.

**Key source files:**

```
applications/beam2/
├── core-protected/
│   ├── modules/api/controllers/sso/
│   │   └── LoginAction.php         # SSO entry point (/api/sso/login/)
│   ├── modules/api/models/
│   │   └── SSO.php                 # Hash validation + JIT provisioning
│   ├── models/
│   │   └── idmUserAccount.php      # User model: authenticate(), isExpired()
│   └── components/web/
│       └── UserIdentity.php        # Yii auth wrapper
└── {client}/
    └── client-objects/
        └── ClientSSO.php           # Client-specific role mapping + overrides
```

**Database tables involved:**

| Table | Purpose |
|-------|---------|
| `idmadmin` | SSO settings (salt, feature flags, default role) |
| `idmuseraccount` | User accounts — created by JIT or admin |
| `userroletype` | Available roles |
| `users_roles` | Junction: user ↔ role assignments |

### Ansible Source of Truth

All relay server config is generated from:

```
ansible-shibboleth-sso/
├── client_configs/active/{client_id}.yml   # Per-client config
├── vault/client_secrets.yml                # Encrypted salts + certs
└── roles/
    ├── shibboleth/templates/shibboleth2.xml.j2
    ├── shibboleth/templates/attribute-map-{idp_type}.xml.j2
    └── sso_redirect/templates/index.php.j2
```

## Multi-Client Architecture

The single Shibboleth SP handles multiple clients via `ApplicationOverride` blocks in `shibboleth2.xml`:

```xml
<RequestMapper type="Native">
  <RequestMap>
    <Host name="gartnersso3.monigle.net" applicationId="gartnersso3" .../>
    <Host name="gartnersso2.monigle.net" applicationId="gartnersso2" .../>
    <!-- one per active client -->
  </RequestMap>
</RequestMapper>

<ApplicationOverride id="gartnersso3" entityID="gartnersso3.monigle.net">
  <Sessions>
    <SessionInitiator entityID="{onelogin_idp_entity_id}" .../>
  </Sessions>
  <MetadataProvider path="gartnersso3-IDP-metadata.xml"/>
  <AttributeExtractor path="gartnersso3-attribute-map.xml"/>
  <CredentialResolver key="monigle-sp-key-2026.pem" certificate="monigle-sp-cert-2026.pem"/>
</ApplicationOverride>
```

## Supported IdP Types

| `idp_type` | Provider | Attribute format |
|------------|----------|-----------------|
| `okta` | Okta | basic |
| `onelogin` | OneLogin | basic |
| `azure_ad` | Microsoft Azure AD | unspecified (URI claims) |
| `google` | Google Workspace | basic |
| `ibm_fim` | IBM Tivoli FIM | URI |
| `generic` | Custom/Other | basic |

## Logging Locations

```bash
# Shibboleth session events (relay server)
ssh ubuntu@10.132.63.235
tail -f /var/log/shibboleth/shibd.log

# Per-client PHP relay requests
tail /var/www/{client_id}.monigle.net/logs/access.log

# beam2 app SSO requests (app server)
ssh ubuntu@{app_server}
grep 'api/sso/login' /var/log/apache2/{client}-access.log

# beam2 application errors
cat /var/www/{client}/protected/runtime/application.log
```
