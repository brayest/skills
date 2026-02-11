---
name: beam2-cert-manager
description: This skill should be used when users need to renew SSL/TLS certificates for clients. The certificates are stored in HashiCorp Vault, and this skill provides the complete workflow for generating CSRs, updating Vault secrets, and managing the renewal process for any client (Corteva, Anthem, Deloitte, etc.).
---

# Certificate Renewal Manager

## Overview

This skill provides a standardized process for renewing SSL/TLS certificates for clients. All certificates are managed in HashiCorp Vault at `http://vault.monigle-utility.int`. The process is identical for every client - only the client name, domain, and organization details change.

## When to Use This Skill

Use this skill when the user:
- Needs to renew an SSL/TLS certificate for a client
- Wants to generate a new CSR (Certificate Signing Request)
- Needs to update certificates in Vault after receiving them from a CA
- Asks about certificate renewal workflow or process
- Mentions clients like Corteva, Anthem, Deloitte, ElevanceHealth

**Trigger keywords**: "renew certificate", "CSR", "Vault certificates", "SSL renewal", "update certificate in Vault"

## Prerequisites

Before starting, verify:

1. **Vault Access**
   - Valid Vault token in `~/.vault-token-xp`
   - Network access to `http://vault.monigle-utility.int`
   - Read/Write permissions for client secrets

2. **Required Tools**
   ```bash
   which curl jq openssl  # Verify all are installed
   ```

3. **Client Variables**
   Identify these for the target client:
   - `{CLIENT_NAME}` - Vault identifier (uppercase, e.g., CORTEVA, ANTHEM)
   - `{DOMAIN}` - Primary domain (e.g., brandcenter.corteva.com)
   - `{ORGANIZATION}` - Legal org name (extract from current cert)
   - `{STATE}` - State/Province (extract from current cert)
   - `{COUNTRY}` - Country code (usually US)

## Certificate Renewal Workflow

Follow these 6 steps in order for any client:

### Step 1: Verify Vault Access

Test authentication and list available secret keys:

```bash
export VAULT_ADDR="http://vault.monigle-utility.int"
export VAULT_TOKEN=$(cat ~/.vault-token-xp | tr -d '\n')

curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} | jq '.data.data | keys'
```

**Expected**: Array including `KEY`, `CERTIFICATE`, `CERT_CHAIN`

### Step 2: Retrieve Current Certificate Details

Extract subject information and SANs from the existing certificate:

```bash
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} | \
  jq -r '.data.data.CERTIFICATE' > /tmp/{client}-current-cert.pem

openssl x509 -in /tmp/{client}-current-cert.pem -noout -subject -text | \
  grep -A2 "Subject:\|Subject Alternative Name"
```

Note the C, ST, O, CN, and all DNS names for CSR creation.

### Step 3: Generate New Private Key

⚠️ **Always generate a NEW key** (never reuse):

```bash
cd /Users/brayest/Work/MediaValet/Clients/{ClientName}

openssl genrsa -out {domain}.key 2048
chmod 600 {domain}.key
```

### Step 4: Create Certificate Signing Request (CSR)

Generate CSR with correct subject and SANs:

```bash
openssl req -new \
  -key {domain}.key \
  -out {domain}.csr \
  -subj "/C={COUNTRY}/ST={STATE}/O={ORGANIZATION}/CN={DOMAIN}" \
  -addext "subjectAltName=DNS:{DOMAIN},DNS:www.{DOMAIN}"

# Verify CSR
openssl req -in {domain}.csr -noout -text | grep -A1 "Subject:\|DNS:"

# Package for submission
zip {domain}.csr.zip {domain}.csr
```

### Step 5: Submit CSR to Certificate Authority

1. Send CSR file to the CA or client
2. Wait for new certificate (typical: 1-5 business days)
3. Receive: certificate (.crt) and chain (.crt) files

### Step 6: Update Vault with New Certificate

⚠️ **CRITICAL**: Preserve all existing client-specific fields

**Method A: Using curl API (Recommended)**

```bash
# 1. Save current non-certificate fields
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} > /tmp/{client}-current.json

jq '.data.data | with_entries(select(.key | IN("KEY", "CERTIFICATE", "CERT_CHAIN") | not))' \
  /tmp/{client}-current.json > /tmp/{client}-preserve.json

# 2. Create update payload with new certs + preserved fields
cat > /tmp/{client}-update.json <<EOF
{
  "data": {
    "KEY": "$(cat {domain}.key | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g')",
    "CERTIFICATE": "$(cat {domain}.crt | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g')",
    "CERT_CHAIN": "$(cat chain.crt | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g')",
    $(jq -r 'to_entries | map("\"\(.key)\": \"\(.value)\"") | join(",\n    ")' /tmp/{client}-preserve.json)
  }
}
EOF

# 3. Update Vault
curl -X POST \
  -H "X-Vault-Token: $VAULT_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/{client}-update.json \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME}

# 4. Verify update
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} | \
  jq -r '.data.data.CERTIFICATE' | \
  openssl x509 -noout -subject -dates
```

## Important Reminders

### Security Best Practices
- ✅ **Always generate NEW private keys** for renewals
- ✅ Set permissions: `chmod 600 *.key`
- ✅ Verify CSR/certificate contents before submission/deployment
- ❌ Never reuse private keys
- ❌ Never commit keys to git
- ❌ Never share keys via unencrypted channels

### Field Preservation
When updating Vault, you **must preserve** all non-certificate fields:
- Database credentials: `DB_NAME`, `DB_PASSWORD`, `DB_USER`, `DB_HOST`
- API keys: `CAPTCHA_PRIVATE`, `CAPTCHA_PUBLIC`, `TEMPLAFY_SECRET`
- Historical keys: `2023_KEY`, `2024_KEY`, etc.

**Failure to preserve these fields will break client applications!**

### Common Client Patterns

| Client | CLIENT_NAME | Example Domain | Typical Fields |
|--------|-------------|---------------|----------------|
| Corteva | `CORTEVA` | brandcenter.corteva.com | DB + CAPTCHA |
| Anthem | `ANTHEM` | brandhub.elevancehealth.com | Historical keys + HSM |
| Deloitte | `DELOITTE` | brandportal.deloitte.com | DB + Templafy |

### Troubleshooting

**"invalid token"**: Token expired - get fresh token and update `~/.vault-token-xp`

**"unknown option -ext"**: macOS LibreSSL issue - use `-text | grep` instead of `-ext`

**CSR missing SANs**: Use config file approach instead of `-addext` flag

**Certificate/key mismatch**: Verify modulus matches:
```bash
openssl req -in {domain}.csr -noout -modulus | md5
openssl x509 -in {domain}.crt -noout -modulus | md5
openssl rsa -in {domain}.key -noout -modulus | md5
# All three should match
```

## Detailed Documentation

For comprehensive documentation including:
- All Vault configuration details
- Detailed troubleshooting guide
- Security best practices
- OpenSSL command reference
- Multi-client examples
- Verification procedures

Refer to: `references/renewal-process.md`

---

**Process applies to**: All clients using Vault-managed certificates
**Vault URL**: http://vault.monigle-utility.int
**Token File**: ~/.vault-token-xp
