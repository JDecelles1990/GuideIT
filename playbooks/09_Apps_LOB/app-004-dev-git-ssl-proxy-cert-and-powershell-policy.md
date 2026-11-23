---
id: app-004
domain: 09_Apps_LOB
subject: Applications & LOB
subcategory: browsers_sso_dev_tools
title: Developer Git/NPM/PIP SSL Proxy Certificate Errors & PowerShell ExecutionPolicy
tier: L2
keywords_en:
  - git ssl certificate problem
  - self signed cert in chain
  - npm ssl proxy error
  - pip tls verify failed
  - powershell running scripts disabled
  - corporate proxy zscaler ssl inspection
keywords_fr:
  - erreur certificat ssl git npm
  - certificat auto signe chaine
  - proxy entreprise inspection ssl
  - execution script powershell desactivee
  - erreur tls pip python developpeur
error_codes:
  - SELF_SIGNED_CERT_IN_CHAIN
  - PSSecurityException
tags:
  - dev_ssl_proxy_cert
  - git_powershell_policy
os:
  - windows
  - macos
  - linux
  - cross_platform
environment:
  - local_endpoint
  - network
  - saas
tools:
  - Git CLI
  - Node.js / npm / Python pip
  - PowerShell (ExecutionPolicy & Cert:\)
  - OpenSSL
risk_level: medium
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - sec-003
  - id-004
  - id-006
  - srv-015
linked_scripts:
  - 05_Security_Defender/Get-ExpiringCertificates.ps1
  - 02_Network/Test-PortConnectivity.ps1
  - 99_Custom/Sample-CustomDiagnostic.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Which specific CLI/tool fails (**`git`**, **`npm`**, **`pip`**, **`az` CLI**, or **PowerShell `.ps1` script / `.venv\Scripts\Activate.ps1`**)?
2. Does the exact same `git clone` / `npm install` work on a **mobile hotspot / home internet** and fail ONLY when on **corporate VPN / office Wi-Fi / Zscaler**? *(Proves corporate TLS Inspection Root CA interception!)*
3. Screenshot the exact terminal error (`SELF_SIGNED_CERT_IN_CHAIN` vs `PSSecurityException: running scripts is disabled on this system`).
4. **Security Rule:** NEVER tell developers to disable `sslVerify` (`false`) or set system-wide `ExecutionPolicy Bypass` permanently!

### Initial Scope & Classification
- **`SELF_SIGNED_CERT_IN_CHAIN`:** CLI OpenSSL runtimes (`git`, `npm`, `pip`) don't read Windows/macOS Enterprise Trusted Root CAs automatically unless configured (`schannel` / `NODE_EXTRA_CA_CERTS` / combined PEM).
- **`PSSecurityException`:** PowerShell `Restricted` policy (`CurrentUser` vs GPO/Intune `MachinePolicy`) or downloaded `Mark of the Web` (`Unblock-File`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Quick Isolation & Restart IDE)
1. **Check Active VPN/Proxy + Browser Test:** Open `https://github.com` or `https://registry.npmjs.org` in Edge/Chrome -> click the URL **lock icon -> Connection is secure -> Certificate** -> check **`Issued by`**: if it shows **Fortinet / Zscaler / Netskope / PaloAlto / Corp Root CA**, confirm with L2 which approved corporate Root CA `.pem` file path is standard!
2. **Check VS Code / Terminal Restart & `Mark of the Web`:** For single `.ps1` files downloaded from email/SharePoint throwing `PSSecurityException`, check **Right-click script -> Properties -> Unblock** (only if script is approved & internal!). Also note **VS Code** must be restarted cleanly after changing Windows User Environment Variables!

### L2 Technical Diagnostics
Inspect existing Git, Node/npm, Python, environment proxy variables, and PowerShell ExecutionPolicy scopes read-only:

```powershell
# 1. Check PowerShell ExecutionPolicy precedence (MachinePolicy/UserPolicy GPO overrides LocalMachine/CurrentUser)
Get-ExecutionPolicy -List

# 2. Check active HTTP/HTTPS proxy & TLS certificate environment variables
Get-ChildItem Env: | Where-Object { $_.Name -match "PROXY|CERT|SSL|CA_BUNDLE" } | Format-Table Name, Value -AutoSize

# 3. Inspect corporate Root CA certificates installed in Windows Trusted Root store
Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Subject -match "Zscaler|Fortinet|Netskope|PaloAlto|Corp|Root" } |
  Select-Object Subject, Thumbprint, NotAfter | Format-Table -AutoSize
```

Inspect developer CLI configs (works on Windows, macOS, and Linux):

```bash
# Git SSL backend & CA config origin
git config --list --show-origin | grep -iE "ssl|http|proxy"

# npm / pip config (avoid printing auth tokens)
npm config get cafile strict-ssl proxy https-proxy
pip config list
```

## Deep-Dive Investigation (L3)
Determine which runtime lacks trust of the corporate Inspection CA (or why PowerShell blocks scripts):

1. **Git on Windows:** Defaults to OpenSSL (`curl-ca-bundle.crt`) which ignores Windows Enterprise Root CAs deployed via GPO/Intune unless switched to `schannel` (Windows Certificate Store) or explicitly given the corporate CA PEM file.
2. **Node.js / `npm` / Electron CLI tools:** Bundle static Mozilla CAs internally and ignore OS trust stores unless `NODE_EXTRA_CA_CERTS` points to the corporate Root CA `.pem` file.
3. **Python / `pip` / Azure CLI (`az`):** Bundle `certifi` CAs and require `REQUESTS_CA_BUNDLE` (and `SSL_CERT_FILE` / `pip config --user set global.cert ...`) pointing to a combined CA bundle (built-in `certifi` + corporate Root CA PEM) — note replacing the entire bundle with ONLY the single corporate CA can break direct non-inspected domains unless combined!
4. **PowerShell `MachinePolicy` / `UserPolicy` Override (`PSSecurityException`):** If `Get-ExecutionPolicy -List` shows `MachinePolicy: Restricted` or `AllSigned`, **Intune or AD GPO enforces it** and local `Set-ExecutionPolicy` commands will fail with `Scope Override` error unless changed in GPO/Intune or scripts are code-signed / run via `npx.cmd`.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER recommend `git config --global http.sslVerify false`, `npm config set strict-ssl false`, or `Set-ExecutionPolicy Bypass` as permanent configuration — disabling certificate checks weakens endpoint security and exposes supply-chain downloads. Configure explicit trust of the verified corporate Root CA instead.

1. **Trust Verified Corporate Root CA Across Developer Tools (Approved Pattern):**
   - Scope: Single developer workstation using the verified corporate inspection Root CA exported from `Cert:\LocalMachine\Root` (PEM/Base-64 `.cer`/`.crt`).
   - **Git (Windows):** Switch Git cleanly to Windows native certificate trust (reads Enterprise GPO/Intune Root CAs automatically):
     ```powershell
     git config --global http.sslBackend schannel
     ```
   - **Node.js / `npm`:** Set user environment variable `NODE_EXTRA_CA_CERTS` to the corporate Root CA `.pem` path (`C:\ProgramData\CorpCerts\corp-root-ca.pem`) and restart terminal/IDE.
   - **Python / `pip` / `az`:** Export combined CA bundle (`certifi` + corporate Root CA `.pem`) and configure `REQUESTS_CA_BUNDLE` / `pip.ini` `cert` cleanly, OR confirm with Network Admin if developer package registries (`registry.npmjs.org`, `pypi.org`) should be SSL-bypassed/cert-pinned on the proxy.
2. **Fix PowerShell Script Block (`PSSecurityException`):**
   - If `MachinePolicy` & `UserPolicy` are `Undefined`, scope strictly to `CurrentUser` with `RemoteSigned` (allows local unsigned dev scripts like `.venv\Scripts\Activate.ps1` while still requiring signatures on internet-downloaded scripts):
     ```powershell
     # Run ONLY after verifying no MachinePolicy GPO/Intune locks ExecutionPolicy
     Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
     ```
   - If blocked by `Mark of the Web` on an approved internal file, use `Unblock-File -Path "<script.ps1>"`.
   - If locked by `MachinePolicy: AllSigned`, enroll the developer workstation in the approved **Intune/GPO Developer Profile** or sign internal helper scripts with the enterprise Code Signing certificate.

## Verification & Post-Fix Checks
- Verify in a fresh terminal session (after restarting VS Code / Terminal so updated environment variables load) that `git ls-remote https://github.com/octocat/Hello-World.git`, `npm ping`, and `pip check` complete without `SELF_SIGNED_CERT_IN_CHAIN`.
- Confirm `http.sslVerify` and `npm strict-ssl` remain `true`.
- Verify `Get-ExecutionPolicy -Scope CurrentUser` (or approved developer policy) permits local `.venv\Scripts\Activate.ps1` without `PSSecurityException`.

## Cross-Subject Escalation & Pivot Links
- **Export and verify corporate TLS inspection Root CA causing SELF_SIGNED_CERT_IN_CHAIN:** [sec-003 — TLS/SSL Certificate Expired, Missing Intermediate Chain, and Untrusted Root CA](../06_Security_Access/sec-003-tls-ssl-certificate-expired-and-untrusted-ca.md)
- **PowerShell MachinePolicy/AllSigned restriction is enforced via AD GPO (gpresult):** [id-004 — Active Directory GPO Not Applying, SYSVOL Permissions, and DFSR Replication Errors](../01_Identity_AD_Entra/id-004-ad-gpo-not-applying-replication-and-dfsr.md)
- **Once CLI SSL trust works, developer still hits Entra app consent/secret error (AADSTS65001):** [id-006 — Entra ID App Registration Permissions, Admin Consent & Developer Secret Failures](../01_Identity_AD_Entra/id-006-entra-app-registration-permissions-and-admin-consent.md)
- **Docker container build or registry pull fails HTTPS behind same TLS inspection proxy:** [srv-015 — Docker Container CrashLoopBackOff, Port Conflicts (EADDRINUSE) & Overlay2 Disk Full](../08_Servers_Cloud_Infra/srv-015-docker-container-crashloop-and-overlay-disk.md)

## Useful Links & External Tools
- [Microsoft Entra Admin Center](https://entra.microsoft.com/) — Verify Intune/GPO security groups if developer policies are assigned via group membership.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, your developer CLI and PowerShell errors (`SELF_SIGNED_CERT_IN_CHAIN` / `PSSecurityException`) were caused by corporate TLS inspection certificates not being trusted by `<Git/Node/Python>` or PowerShell's script execution scope. Rather than disabling SSL verification, we configured explicit trust for the verified corporate Root CA (`schannel` / `NODE_EXTRA_CA_CERTS` / combined bundle) and set the approved `RemoteSigned` user scope. Please restart your terminal/IDE and test again.
- **FR:** Bonjour `<user>`, vos erreurs Git/NPM/PIP ou PowerShell (`SELF_SIGNED_CERT_IN_CHAIN` / `PSSecurityException`) venaient du certificat racine d'inspection TLS d'entreprise ou de la stratégie d'exécution PowerShell. Sans désactiver la vérification SSL, nous avons configuré la confiance explicite du certificat racine autorisé (`schannel` / `NODE_EXTRA_CA_CERTS` / bundle CA) et ajusté la portée approuvée. Merci de redémarrer votre terminal/IDE et de revalider.
