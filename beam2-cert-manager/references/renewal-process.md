# Certificate Renewal Process - Universal Guide

## Overview

This document provides a **standardized, repeatable process** for renewing SSL/TLS certificates for **all clients**. All certificates are managed in HashiCorp Vault and follow the same renewal workflow.

**Key Principle**: The process is identical for every client - only the client name, domain, and organization details change.

### How to Use This Guide

1. Identify your client's variables (see [Quick Start](#quick-start))
2. Follow the 6-step process, substituting your client's values
3. Refer to the examples for similar clients

---

## Quick Start

Before starting, identify these variables for your client:

| Variable | Description | How to Find |
|----------|-------------|-------------|
| `{CLIENT_NAME}` | Vault client identifier (uppercase) | Check Vault path or existing folder name |
| `{DOMAIN}` | Primary domain for the certificate | Check existing certificate or client documentation |
| `{ORGANIZATION}` | Legal organization name | Extract from current certificate |
| `{STATE}` | State/Province | Extract from current certificate |
| `{COUNTRY}` | Country code (e.g., US) | Extract from current certificate |

### Common Client Examples

| Client | CLIENT_NAME | DOMAIN | ORGANIZATION | STATE |
|--------|-------------|--------|--------------|-------|
| Corteva | `CORTEVA` | `brandcenter.corteva.com` | `Corteva Agriscience MCS LLC` | `Iowa` |
| Anthem | `ANTHEM` | `brandhub.elevancehealth.com` | `Elevance Health, Inc.` | `Indiana` |
| Deloitte | `DELOITTE` | `brandportal.deloitte.com` | `Deloitte` | Varies |

---

## Prerequisites

Before starting the renewal process, ensure you have:

### 1. Vault Access
- Valid Vault token stored in `~/.vault-token-xp`
- Network access to `http://vault.monigle-utility.int`
- Read/Write permissions for client secrets

### 2. Required Tools
```bash
# Verify tools are installed
which curl jq openssl
```

Required:
- `curl` - for Vault API calls
- `jq` - for JSON parsing
- `openssl` - for certificate and CSR operations

### 3. Client Folder
Create a folder for the client if it doesn't exist:
```bash
mkdir -p /Users/brayest/Work/MediaValet/Clients/{ClientName}
```

---

## Vault Configuration

**Vault Details (Same for All Clients)**:
- **Vault URL**: `http://vault.monigle-utility.int`
- **Secret Path Pattern**: `kv/data/CLIENTS/{CLIENT_NAME}`
- **API Endpoint Pattern**: `http://vault.monigle-utility.int/v1/kv/data/CLIENTS/{CLIENT_NAME}`

**Standard Certificate Fields** (All clients):
- `KEY` - Private key
- `CERTIFICATE` - SSL certificate
- `CERT_CHAIN` - Certificate chain

**Client-Specific Fields** (Varies by client):
- Database: `DB_NAME`, `DB_PASSWORD`, `DB_USER`, `DB_HOST`
- API Keys: `CAPTCHA_PRIVATE`, `CAPTCHA_PUBLIC`, `TEMPLAFY_SECRET`
- Historical Keys: `2023_KEY`, `2024_KEY`, etc.

⚠️ **Important**: When updating certificates, you **must preserve** all client-specific fields.

---

## Step-by-Step Renewal Process

### Step 1: Verify Vault Access

Verify that your Vault token is valid and you can access the client's secrets.

**Template Command**:
```bash
export VAULT_ADDR="http://vault.monigle-utility.int"
export VAULT_TOKEN=$(cat ~/.vault-token-xp | tr -d '\n')

# List available keys for the client
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} | jq '.data.data | keys'
```

**Example: Corteva**
```bash
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/CORTEVA | jq '.data.data | keys'
```

**Example: Anthem**
```bash
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/ANTHEM | jq '.data.data | keys'
```

**Expected Output**: Array of field names including `KEY`, `CERTIFICATE`, `CERT_CHAIN`

**Troubleshooting**: If you see `"invalid token"` or `"permission denied"`, your token may be expired. Contact your Vault administrator.

---

### Step 2: Retrieve Current Certificate Details

Extract the current certificate from Vault to understand its structure.

**Template Commands**:
```bash
export VAULT_ADDR="http://vault.monigle-utility.int"
export VAULT_TOKEN=$(cat ~/.vault-token-xp | tr -d '\n')

# Save current certificate to temp file
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} | \
  jq -r '.data.data.CERTIFICATE' > /tmp/{client}-current-cert.pem

# Extract subject information
openssl x509 -in /tmp/{client}-current-cert.pem -noout -subject -text | \
  grep -A2 "Subject:\|Subject Alternative Name"

# Check expiration dates
openssl x509 -in /tmp/{client}-current-cert.pem -noout -dates
```

**Example: Corteva**
```bash
# Retrieve Corteva certificate
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/CORTEVA | \
  jq -r '.data.data.CERTIFICATE' > /tmp/corteva-current-cert.pem

# View details
openssl x509 -in /tmp/corteva-current-cert.pem -noout -subject -text | \
  grep -A2 "Subject:\|Subject Alternative Name"
```

**Expected Output Example** (Corteva):
```
Subject: C=US, ST=Iowa, O=Corteva Agriscience MCS LLC, CN=brandcenter.corteva.com
Subject Alternative Name:
    DNS:brandcenter.corteva.com, DNS:www.brandcenter.corteva.com
```

**Note the following for CSR creation**:
- Country (C)
- State (ST)
- Organization (O)
- Common Name (CN)
- All DNS names in Subject Alternative Name

---

### Step 3: Generate New Private Key

⚠️ **Security Best Practice**: Always generate a NEW private key for certificate renewals. Do not reuse the old key.

**Template Commands**:
```bash
cd /Users/brayest/Work/MediaValet/Clients/{ClientName}

# Generate new 2048-bit RSA private key
openssl genrsa -out {domain}.key 2048

# Set secure permissions (read/write for owner only)
chmod 600 {domain}.key

# Verify key generation
openssl rsa -in {domain}.key -noout -text | head -n 1
```

**Example: Corteva**
```bash
cd /Users/brayest/Work/MediaValet/Clients/Corteva

openssl genrsa -out brandcenter.corteva.com.key 2048
chmod 600 brandcenter.corteva.com.key
openssl rsa -in brandcenter.corteva.com.key -noout -text | head -n 1
```

**Example: Deloitte**
```bash
cd /Users/brayest/Work/MediaValet/Clients/Deloitte

openssl genrsa -out brandportal.deloitte.com.key 2048
chmod 600 brandportal.deloitte.com.key
```

**Expected Output**: `Private-Key: (2048 bit)`

---

### Step 4: Create Certificate Signing Request (CSR)

Create a CSR using the new private key with the correct subject information and Subject Alternative Names.

**Template Command**:
```bash
cd /Users/brayest/Work/MediaValet/Clients/{ClientName}

openssl req -new \
  -key {domain}.key \
  -out {domain}.csr \
  -subj "/C={COUNTRY}/ST={STATE}/O={ORGANIZATION}/CN={DOMAIN}" \
  -addext "subjectAltName=DNS:{DOMAIN},DNS:www.{DOMAIN}"
```

**Example: Corteva**
```bash
cd /Users/brayest/Work/MediaValet/Clients/Corteva

openssl req -new \
  -key brandcenter.corteva.com.key \
  -out brandcenter.corteva.com.csr \
  -subj "/C=US/ST=Iowa/O=Corteva Agriscience MCS LLC/CN=brandcenter.corteva.com" \
  -addext "subjectAltName=DNS:brandcenter.corteva.com,DNS:www.brandcenter.corteva.com"
```

**Example: Anthem (ElevanceHealth)**
```bash
cd /Users/brayest/Work/MediaValet/Clients/ElevanceHealth

openssl req -new \
  -key brandhub.elevancehealth.com.key \
  -out brandhub.elevancehealth.com.csr \
  -subj "/C=US/ST=Indiana/L=Indianapolis/O=Elevance Health, Inc./CN=brandhub.elevancehealth.com" \
  -addext "subjectAltName=DNS:brandhub.elevancehealth.com"
```

**Verify CSR Contents**:
```bash
# Template
openssl req -in {domain}.csr -noout -text | grep -A1 "Subject:\|DNS:"

# Example: Corteva
openssl req -in brandcenter.corteva.com.csr -noout -text | grep -A1 "Subject:\|DNS:"
```

**Package CSR for Submission**:
```bash
# Template
zip {domain}.csr.zip {domain}.csr

# Example: Corteva
zip brandcenter.corteva.com.csr.zip brandcenter.corteva.com.csr
```

---

### Step 5: Submit CSR to Certificate Authority

**Submission Process**:

1. **Locate the CSR file**: `{ClientName}/{domain}.csr` or the `.zip` file
2. **Determine the CA**: Check the current certificate issuer
   ```bash
   openssl x509 -in /tmp/{client}-current-cert.pem -noout -issuer
   ```
   Common CAs: Sectigo, DigiCert, Let's Encrypt

3. **Submit to CA**:
   - If you handle procurement: Submit CSR to the Certificate Authority
   - If client handles it: Send the CSR file to the client

4. **Wait for Response**: Typical turnaround is 1-5 business days

**What You'll Receive**:
- New SSL certificate (`.crt` or `.pem` file)
- Certificate chain (may be separate or bundled)
- Sometimes a root certificate

---

### Step 6: Update Vault with New Certificate

Once you receive the new certificate from the CA, update Vault with the new key, certificate, and chain.

⚠️ **CRITICAL**: You must preserve all existing client-specific fields when updating Vault.

#### Step 6a: Retrieve All Current Fields

**Template**:
```bash
export VAULT_ADDR="http://vault.monigle-utility.int"
export VAULT_TOKEN=$(cat ~/.vault-token-xp | tr -d '\n')

# Save current data to file
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} > /tmp/{client}-current-data.json

# View all current fields
jq '.data.data | keys' /tmp/{client}-current-data.json
```

**Example: Corteva**
```bash
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/CORTEVA > /tmp/corteva-current-data.json

jq '.data.data | keys' /tmp/corteva-current-data.json
```

**Output shows all fields**:
```json
["CAPTCHA_PRIVATE", "CAPTCHA_PUBLIC", "CERTIFICATE", "CERT_CHAIN", "DB_NAME", "DB_PASSWORD", "DB_USER", "KEY"]
```

#### Step 6b: Update Vault (Method 1: Vault CLI)

**Template**:
```bash
export VAULT_ADDR="http://vault.monigle-utility.int"
export VAULT_TOKEN=$(cat ~/.vault-token-xp | tr -d '\n')

# Create update command preserving all existing fields
vault kv put kv/CLIENTS/{CLIENT_NAME} \
  KEY=@{domain}.key \
  CERTIFICATE=@{domain}.crt \
  CERT_CHAIN=@chain.crt \
  $(jq -r '.data.data | to_entries | map(select(.key | IN("KEY", "CERTIFICATE", "CERT_CHAIN") | not)) | map("\(.key)=\(.value|@sh)") | .[]' /tmp/{client}-current-data.json)
```

#### Step 6b: Update Vault (Method 2: curl API - Recommended)

This method gives you more control and visibility.

**Step-by-step Process**:

1. **Extract current non-certificate fields**:
```bash
# Template
jq '.data.data | with_entries(select(.key | IN("KEY", "CERTIFICATE", "CERT_CHAIN") | not))' \
  /tmp/{client}-current-data.json > /tmp/{client}-preserve.json
```

2. **Create update payload**:
```bash
# Template - Create JSON payload
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
```

3. **Update Vault**:
```bash
# Template
curl -X POST \
  -H "X-Vault-Token: $VAULT_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/{client}-update.json \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME}
```

**Complete Example: Corteva**
```bash
cd /Users/brayest/Work/MediaValet/Clients/Corteva

# 1. Extract fields to preserve
jq '.data.data | with_entries(select(.key | IN("KEY", "CERTIFICATE", "CERT_CHAIN") | not))' \
  /tmp/corteva-current-data.json > /tmp/corteva-preserve.json

# 2. Create update payload (assuming you have the new files)
cat > /tmp/corteva-update.json <<EOF
{
  "data": {
    "KEY": "$(cat brandcenter.corteva.com.key | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g')",
    "CERTIFICATE": "$(cat brandcenter.corteva.com.crt | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g')",
    "CERT_CHAIN": "$(cat chain.crt | sed -e ':a' -e 'N' -e '$!ba' -e 's/\n/\\n/g')",
    $(jq -r 'to_entries | map("\"\(.key)\": \"\(.value)\"") | join(",\n    ")' /tmp/corteva-preserve.json)
  }
}
EOF

# 3. Update Vault
curl -X POST \
  -H "X-Vault-Token: $VAULT_TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/corteva-update.json \
  $VAULT_ADDR/v1/kv/data/CLIENTS/CORTEVA
```

#### Step 6c: Verify Update

```bash
# Template
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} | \
  jq -r '.data.data.CERTIFICATE' | \
  openssl x509 -noout -subject -dates -issuer

# Example: Corteva
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/CORTEVA | \
  jq -r '.data.data.CERTIFICATE' | \
  openssl x509 -noout -subject -dates -issuer
```

**Expected**: New certificate with updated dates and correct subject.

---

## Troubleshooting

### Issue: "invalid token" or "permission denied"

**Cause**: Vault token has expired or is invalid.

**Solution**:
1. Check token file exists: `ls -la ~/.vault-token-xp`
2. Verify token format (should start with `hvs.`)
3. Contact Vault administrator for a new token
4. Update `~/.vault-token-xp` with the new token

### Issue: "unknown option -ext" when using openssl

**Cause**: macOS uses LibreSSL which doesn't support the `-ext` flag.

**Solution**: Use `-text` flag instead:
```bash
# Don't use this (won't work on macOS):
openssl x509 -ext subjectAltName

# Use this instead:
openssl x509 -text | grep -A2 "Subject Alternative Name"
```

### Issue: CSR missing Subject Alternative Names

**Cause**: The `-addext` flag might not work with older OpenSSL versions.

**Solution**: Create a config file instead:
```bash
cat > csr.conf <<EOF
[req]
default_bits = 2048
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
C = {COUNTRY}
ST = {STATE}
O = {ORGANIZATION}
CN = {DOMAIN}

[req_ext]
subjectAltName = @alt_names

[alt_names]
DNS.1 = {DOMAIN}
DNS.2 = www.{DOMAIN}
EOF

# Generate CSR with config
openssl req -new -key {domain}.key -out {domain}.csr -config csr.conf
```

### Issue: Lost client-specific fields after Vault update

**Cause**: Didn't preserve non-certificate fields when updating Vault.

**Prevention**: Always follow Step 6a and 6b carefully to preserve all existing fields.

**Recovery**:
1. Check Vault version history: `vault kv metadata get kv/CLIENTS/{CLIENT_NAME}`
2. Restore from previous version if needed: `vault kv get -version=N kv/CLIENTS/{CLIENT_NAME}`

### Issue: Certificate/Key mismatch

**Cause**: Received certificate doesn't match the private key used in CSR.

**Verification**:
```bash
# Check if modulus matches (both commands should produce same hash)
openssl req -in {domain}.csr -noout -modulus | md5
openssl x509 -in {domain}.crt -noout -modulus | md5
openssl rsa -in {domain}.key -noout -modulus | md5
```

**Solution**: Ensure you're using the correct private key that was used to generate the CSR.

---

## Security Best Practices

### Key Management
- ✅ **DO** generate a new private key for each renewal
- ✅ **DO** set file permissions to 600 on private keys: `chmod 600 *.key`
- ✅ **DO** store private keys securely (Vault, encrypted storage)
- ✅ **DO** use at least 2048-bit keys (4096-bit for high security)
- ❌ **DON'T** reuse private keys across renewals
- ❌ **DON'T** commit private keys to git repositories
- ❌ **DON'T** share private keys via email or unencrypted channels
- ❌ **DON'T** store unencrypted keys on shared file systems

### Token Management
- ✅ **DO** check token expiration regularly
- ✅ **DO** store tokens in secure files with restricted permissions
- ✅ **DO** use environment variables for tokens in scripts
- ✅ **DO** rotate tokens periodically
- ❌ **DON'T** hardcode tokens in scripts
- ❌ **DON'T** commit tokens to version control
- ❌ **DON'T** share tokens between team members

### Certificate Verification
- ✅ **DO** verify CSR contents before submission
- ✅ **DO** verify received certificates match your CSR
- ✅ **DO** check certificate expiration dates after renewal
- ✅ **DO** test certificates in a staging environment first
- ✅ **DO** verify the certificate chain is complete

### Vault Updates
- ✅ **DO** always preserve existing client-specific fields
- ✅ **DO** verify the update was successful
- ✅ **DO** document any changes to field names or structure
- ❌ **DON'T** overwrite Vault data without backing up current values
- ❌ **DON'T** assume all clients have the same field structure

---

## Verification

### Verify CSR Before Submission

```bash
# Check subject
openssl req -in {domain}.csr -noout -subject

# Check SANs
openssl req -in {domain}.csr -noout -text | grep -A2 "Subject Alternative Name"

# Verify key matches CSR (modulus should match)
openssl req -in {domain}.csr -noout -modulus | md5
openssl rsa -in {domain}.key -noout -modulus | md5
```

### Verify Certificate After Receiving It

```bash
# Check certificate details
openssl x509 -in {domain}.crt -noout -subject -dates -issuer

# Verify certificate matches private key (modulus should match)
openssl x509 -in {domain}.crt -noout -modulus | md5
openssl rsa -in {domain}.key -noout -modulus | md5

# Verify certificate chain
openssl verify -CAfile chain.crt {domain}.crt

# Check that SANs are correct
openssl x509 -in {domain}.crt -noout -text | grep -A2 "Subject Alternative Name"
```

### Test Updated Vault Secrets

```bash
export VAULT_ADDR="http://vault.monigle-utility.int"
export VAULT_TOKEN=$(cat ~/.vault-token-xp | tr -d '\n')

# Retrieve and verify the updated certificate
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} | \
  jq -r '.data.data.CERTIFICATE' | \
  openssl x509 -noout -subject -dates -issuer

# Verify all fields were preserved
curl -s -H "X-Vault-Token: $VAULT_TOKEN" \
  $VAULT_ADDR/v1/kv/data/CLIENTS/{CLIENT_NAME} | \
  jq '.data.data | keys'
```

---

## Common OpenSSL Commands Reference

```bash
# View certificate details
openssl x509 -in certificate.crt -noout -text

# Check certificate expiration
openssl x509 -in certificate.crt -noout -dates

# View certificate subject
openssl x509 -in certificate.crt -noout -subject

# View certificate issuer
openssl x509 -in certificate.crt -noout -issuer

# View CSR details
openssl req -in request.csr -noout -text

# View CSR subject
openssl req -in request.csr -noout -subject

# Check private key
openssl rsa -in private.key -noout -check

# Extract public key from certificate
openssl x509 -in certificate.crt -noout -pubkey

# Get certificate modulus (for matching)
openssl x509 -in certificate.crt -noout -modulus | md5

# Get private key modulus (for matching)
openssl rsa -in private.key -noout -modulus | md5

# Get CSR modulus (for matching)
openssl req -in request.csr -noout -modulus | md5

# Verify certificate chain
openssl verify -CAfile chain.pem certificate.crt

# Convert formats (if needed)
openssl x509 -in cert.der -inform DER -out cert.pem -outform PEM
```

---

## File Organization

### Root Structure
```
Clients/
├── README.md                    # This generalized guide
├── Corteva/                     # Client folder
├── ElevanceHealth/              # Client folder
├── Deloitte/                    # Client folder
└── [OtherClients]/              # Additional client folders
```

### Per-Client Folder Structure
```
{ClientName}/
├── README.md                    # (Optional) Client-specific notes
├── {domain}.key                 # Private key (chmod 600)
├── {domain}.csr                 # Certificate Signing Request
├── {domain}.csr.zip             # Packaged CSR for submission
├── {domain}.crt                 # New certificate (after receiving)
├── chain.crt                    # Certificate chain (after receiving)
└── csr.conf                     # (Optional) OpenSSL config for CSR
```

### Git Ignore Recommendations

Add to `.gitignore` in the Clients folder:
```gitignore
# Private keys - NEVER commit
*.key
*.pem

# Certificates (may contain sensitive info)
*.crt
*.cer

# CSRs (optional - may be safe to commit)
# *.csr

# Temporary files
/tmp/
*.swp
.DS_Store
```

---

## What We Learned (Process Notes)

### What Worked ✅
1. Using Vault token from `~/.vault-token-xp` file
2. Direct Vault API calls with curl for flexibility
3. Using `jq` for robust JSON parsing and manipulation
4. Using `openssl x509 -text` to extract certificate details (macOS compatible)
5. Using `openssl req` with `-subj` and `-addext` for CSR generation
6. Organizing files in client-specific folders
7. Template-based approach with variable substitution

### What Didn't Work ❌
1. Assuming Vault tokens are always valid (check first!)
2. Using `openssl x509 -ext` flag (not supported in macOS LibreSSL)
3. Using `cd` with relative paths in shell eval contexts
4. Overwriting Vault data without preserving client-specific fields
5. Hardcoding client-specific values in scripts

### Best Practices Going Forward 🎯
1. **Always verify Vault token validity** before starting
2. **Always use absolute paths** in commands and scripts
3. **Always generate new keys** for each renewal (never reuse)
4. **Always preserve client-specific fields** when updating Vault
5. **Always verify** CSR and certificate contents before submission/deployment
6. **Document client-specific details** in dedicated READMEs within client folders
7. **Use this generalized guide** as the single source of truth for the process

---

## Client-Specific README Template

For complex clients, create a `README.md` in their folder with:

```markdown
# Certificate Renewal - {Client Name}

## Client Information
- Organization: {Full Legal Name}
- Domain(s): {primary.domain.com, additional.domain.com}
- State: {State}
- Country: {Country}
- Certificate Authority: {Sectigo, DigiCert, etc.}

## Vault Details
- Client Name (Vault): {CLIENT_NAME}
- Special Fields: List any non-standard fields
- Notes: Any client-specific requirements

## Subject Details
\`\`\`
C={COUNTRY}
ST={STATE}
L={LOCALITY} (if applicable)
O={ORGANIZATION}
CN={COMMON_NAME}
\`\`\`

## Subject Alternative Names
- DNS: {domain1}
- DNS: {domain2}
- etc.

## Contact Information
- Technical Contact: {name, email}
- Certificate Procurement: {Who handles it}
- Renewal Schedule: {When to renew}

## Special Notes
- Any special requirements
- Historical issues
- Client preferences
```

---

**Process Version**: 2.0
**Last Updated**: 2026-02-10
**Maintained By**: MediaValet Team

For questions or issues with this process, refer to the troubleshooting section or contact the team.
