# beam2 SSO Authentication Flow

## Complete Flow (15 Steps)

```
Step 1   Browser → GET https://{client_id}.monigle.net/

Step 2   Apache mod_shib: no Shibboleth session
         → 302 to IdP SAML SSO endpoint
           (entityID from shibboleth2.xml ApplicationOverride)

Step 3   Browser → IdP login page
         User enters IdP credentials (Okta, OneLogin, Azure AD, etc.)

Step 4   IdP authenticates user
         Constructs SAML assertion with attributes:
           - email / firstname / lastname / groups (IdP-dependent)

Step 5   IdP → Browser → POST https://{client_id}.monigle.net/Shibboleth.sso/SAML2/POST
         Shibboleth SP validates SAML signature using IdP metadata
         Creates session, maps SAML attributes via {client}-attribute-map.xml
         → 302 to /

Step 6   Browser → GET https://{client_id}.monigle.net/
         (Shibboleth session active, ShibUseEnvironment On → attributes in $_SERVER)

Step 7   index.php executes:
           $email  = isset($_SERVER["email"])     ? $_SERVER["email"]     : "";
           $fname  = isset($_SERVER["firstname"]) ? $_SERVER["firstname"] : "";
           $lname  = isset($_SERVER["lastname"])  ? $_SERVER["lastname"]  : "";

           // Fallback if IdP sent no email
           if (empty($email) || !str_contains($email, "@"))
               $email = "no_email_account@{fallback_email_domain}";

Step 8   index.php generates hash:
           $SSO_String = $email . "|" . $salt;
           $hash = hash('sha256', $SSO_String);

Step 9   index.php builds redirect params:
           HTTP_MAIL              = $email
           HTTP_GIVENNAME         = $fname
           HTTP_SN                = $lname
           HTTP_SHIBSESSIONID     = $hash
           HTTP_UNSCOPEDAFFILIATION = $redirectURL (from query string, optional)
           HTTP_AFFILIATION       = ""
           HTTP_EPPN              = ""
           HTTP_REMOTEUSER        = ""
           HTTP_SHIBAUTHENTICATIONINSTANT = ""

         → 302 to {sso_destination_url}?{params}
           (e.g. https://brand.gartner.com/api/sso/login/?HTTP_MAIL=...&HTTP_SHIBSESSIONID=...)

Step 10  Browser → GET https://brand.{client}.com/api/sso/login/?{params}
         LoginAction.php runs:
           if (is_file(INC_ROOT . '/client-objects/ClientSSO.php'))
               $model = new ClientSSO();
           else
               $model = new SSO();

Step 11  $model->attributes = $_GET
         $model->validate():
           - HTTP_MAIL required
           - HTTP_MAIL email regex: /^((?!monigle).)*$/i
             (rejects Monigle employee emails)
           - field length max 255

Step 12  $model->loginSSO():
           // Recompute hash on beam2 side
           $salt      = idMAdmin::getString('sso.salt');   // from idmadmin table
           $SSO_String = $HTTP_MAIL . "|" . $salt;
           $phpHash   = hash('sha256', $SSO_String);

           // Validate
           if ($phpHash !== $HTTP_SHIBSESSIONID) return false;  // HASH FAIL

           // Optional: timestamp check
           if ((int)idMAdmin::getString('sso.seconds') != 0) {
               if (empty($ssotimestamp)) return false;
               if ((now - $ssotimestamp) > sso.seconds) return false;
               // Hash includes timestamp: sha256($email|$timestamp|$salt)
           }

Step 13  User lookup:
           $account = idmUserAccount::findByAttributes(['EmailAddress' => $HTTP_MAIL]);

           if (!$account) {
               // JIT provision: create new account
               $this->createAccount();
               // → sets default role from idmadmin 'default.sso.role'
               // → ClientSSO maps HTTP_ROLE attribute to role if present
           } else {
               // Update rotating password hash (security measure)
               $account->setPswd($this->_password = time() . $salt);
               $account->save(false, ['Password', 'Notes']);
           }

Step 14  $this->login():
           UserIdentity::authenticate($HTTP_MAIL, $plain_password):
             1. Find user by email
             2. password_verify($plain, $stored_hash)  → ERROR_PASSWORD_INVALID
             3. IsDeleted check                         → ERROR_USERNAME_INVALID
             4. IsActive check                          → ERROR_USERNAME_INVALID
             5. isExpired(): ActiveUntil < now          → ERROR_USERNAME_INVALID
             6. passwordExpired()                       → redirect to /site/forcepass
             7. All OK                                  → ERROR_NONE

           If ERROR_NONE:
             Yii::app()->user->login($identity)
             Record LastLogin, FirstLogin timestamps

Step 15  LoginAction result:
           SUCCESS → redirect to:
             1. HTTP_UNSCOPEDAFFILIATION (if set) — deep link to specific page
             2. Yii returnUrl (if set and not SSO endpoint)
             3. landing.page.path from idmadmin
           FAILURE → Yii flash 'error' + redirect to /site/login/
```

## Access Log Response Size Heuristic

Check beam2 access log to quickly determine success/failure:

```bash
grep 'api/sso/login' /var/log/apache2/{client}-access.log | tail -10
```

| Response size | Meaning |
|--------------|---------|
| `302 ~5000+` bytes | Likely SUCCESS — redirect to landing page |
| `302 ~500-900` bytes | Likely FAILURE — redirect to /site/login/ |

## Hash Verification (Manual Debug)

```bash
# Compute expected hash
echo -n "{email}|{sso.salt}" | sha256sum

# Compare to HTTP_SHIBSESSIONID in the access log URL
# They must match exactly
```

## Salt Source Chain

```
Ansible vault (vault/client_secrets.yml)
    vault_{client_id}_salt: "uuid-value"
        ↓ Ansible deploys
/var/www/{client}.monigle.net/index.php
    $salt = "uuid-value";
        ↓ PHP computes hash → HTTP_SHIBSESSIONID
beam2 database (idmadmin table)
    key='sso.salt', value='uuid-value'
        ↓ PHP recomputes hash and compares
```

**All three values must be identical.** Any divergence causes silent hash mismatch → `/site/login/`.

## JIT Provisioning Details

When `createAccount()` runs (new user):

```php
// Base SSO::createAccount()
$userAccount->IsActive    = 1;
$userAccount->IsDeleted   = 0;
$userAccount->FirstName   = $this->HTTP_GIVENNAME;
$userAccount->LastName    = $this->HTTP_SN;
$userAccount->EmailAddress = $this->HTTP_MAIL;
$userAccount->Notes       = 'user added by SSO';
$userAccount->roles       = [idMAdmin::getString('default.sso.role')];

// ClientSSO override: map IdP group → beam2 role
if ($this->HTTP_ROLE && isset($roleMap[$this->HTTP_ROLE]))
    $userAccount->roles = [$roleMap[$this->HTTP_ROLE]];

$userAccount->createAccount();
$this->UserAccountID = $userAccount->UserAccountID;
```

**Known bug in `ClientSSO::createAccount()`**: `$this->_password` is set to the bcrypt hash rather than plaintext, causing the first login attempt for a NEW user to fail authentication. On the second attempt, the user exists → the else branch runs correctly with plaintext. Workaround: retry once after initial failure.
