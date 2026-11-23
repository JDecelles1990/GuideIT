---
id: sec-003
domain: 06_Security_Access
subject: "Security & Access"
subcategory: tls_certs_purview_dlp
title: TLS/SSL Certificate Expired, Missing Intermediate Chain, and Untrusted Root CA
tier: L2
keywords_en:
  - ssl certificate expired
  - your connection is not private
  - untrusted root certificate
  - schannel event 36871 36887
  - err cert authority invalid
keywords_fr:
  - certificat ssl expire
  - connexion non privee certificat
  - autorite certification non approuvee
  - erreur certificat navigateur https
  - chaine certificat intermediaire manquante
error_codes:
  - "NET::ERR_CERT_DATE_INVALID"
  - "NET::ERR_CERT_AUTHORITY_INVALID"
  - "NET::ERR_CERT_COMMON_NAME_INVALID"
  - "36871"
  - "36887"
tags:
  - tls_cert_expired
  - untrusted_root_ca
os:
  - windows
  - macos
  - linux
  - cross_platform
environment:
  - network
  - cloud_infra
  - on_prem_ad
  - saas
tools:
  - Browser Certificate Viewer
  - openssl
  - PowerShell
  - certlm.msc
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - app-001
  - app-004
  - net-002
  - m365-001
linked_scripts:
  - 05_Security_Defender/Get-ExpiringCertificates.ps1
  - 02_Network/Get-WebProxyAndTLSDiagnostics.ps1
  - 02_Network/Test-PortConnectivity.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Does the `"Your connection is not private"` / certificate warning appear on **EVERY website (`google.com`, `microsoft.com`)** OR on **ONLY ONE specific internal/client website**?
2. Click **Advanced** on the browser warning page and read the exact error code (`NET::ERR_CERT_DATE_INVALID`, `NET::ERR_CERT_AUTHORITY_INVALID`, `NET::ERR_CERT_COMMON_NAME_INVALID`).
3. Look at the **Date & Time in the user's taskbar corner**: is the year/month/day wrong on `PC-LAB-01`? *(Wrong PC clock breaks ALL HTTPS certificates immediately!)*
4. Are you using **Mozilla Firefox** vs Edge/Chrome, OR connected to a new corporate firewall / proxy / hotel Wi-Fi?

### Initial Scope & Classification
- **`NET::ERR_CERT_DATE_INVALID`:** Server cert expired OR `PC-LAB-01` system clock is wrong.
- **`NET::ERR_CERT_AUTHORITY_INVALID`:** Missing Intermediate CA on server, self-signed internal cert, OR corporate Firewall SSL Inspection (DPI) missing its Root CA on `PC-LAB-01` (or inside Firefox!).
- **`NET::ERR_CERT_COMMON_NAME_INVALID`:** URL visited (e.g. `https://app`) doesn't match certificate SAN (`app.example.com`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Browser Lock Icon & Clock Check)
1. **Check `PC-LAB-01` System Clock & Hotel Captive Portal First:** Look at taskbar clock date/time! On Guest/Hotel Wi-Fi, an un-accepted login portal often triggers `ERR_CERT_AUTHORITY_INVALID` on HTTPS sites until you open `http://neverssl.com` to sign in!
2. **Inspect Who Issued the Certificate (3-Click Browser Check):** Click **`Not Secure` / Warning icon** left of URL bar -> **Certificate is not valid -> Details / General**:
   - Check **`Valid to` date** (did a public SSL cert expire today?).
   - Check **`Issued by`** — if it says **Fortinet / Zscaler / Sophos / SonicWall / Bitdefender**, HTTPS Inspection is active and `PC-LAB-01` or Firefox lacks that proxy Root CA!
   - Test **Edge/Chrome vs Firefox** (Firefox maintains its own trust store unless `security.enterprise_roots.enabled` is set!).

### L2 Technical Diagnostics
1. **Check Client System Date/Time & Inspect Remote TLS Chain Live (read-only):**
   ```powershell
   Get-Date
   ```
   ```bash
   echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
   ```
   *(If `openssl` reports `Verify return code: 21 (unable to verify the first certificate)`, the web server forgot to bundle its **Intermediate CA** chain!)*
2. **Check Windows Certificate Store & Schannel Errors (`Event ID 36871`, `36887`, `36888`, read-only):**
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Schannel'; Id = 36870, 36871, 36887, 36888; StartTime = (Get-Date).AddDays(-3) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, Message
   Get-ChildItem Cert:\LocalMachine\My | Where-Object { $_.NotAfter -lt (Get-Date).AddDays(30) } |
       Select-Object Subject, NotAfter, Thumbprint
   ```
3. **Check Who Issued the Presented Cert in Browser:**
   - If the `Issuer` of `https://example.com` shows the client's firewall vendor (Fortinet, Sophos, SonicWall, Zscaler, Umbrella) or local AV (`Bitdefender`/`Kaspersky`), **DPI/HTTPS inspection** is active and the endpoint lacks that proxy's Root CA certificate!

## Deep-Dive Investigation (L3)
1. **Windows vs. Firefox/Python/Java Custom Trust Stores:** Edge, Chrome, and Safari use the OS trust store (`certlm.msc` / macOS Keychain), whereas **Firefox** (`security.enterprise_roots.enabled`), **Python (`certifi`)**, **Node (`NODE_EXTRA_CA_CERTS`)**, and **Java (`cacerts`)** ignore Windows Root CA certificates unless configured explicitly!
2. **ACME / Let's Encrypt Auto-Renewal Failure (`certbot`):** On Linux web servers (`[srv-007]`), port `80` HTTP-01 firewall block or failed post-hook `systemctl reload nginx` leaves the old expired cert loaded in RAM even though a new cert exists on disk!
3. **Deprecated TLS 1.0 / 1.1 or Weak Cipher Mismatch (`36871` / `36887`):** Legacy LOB servers or appliances supporting only TLS 1.0 fail modern Windows Schannel handshakes (`TLS 1.2+`).

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `PC-LAB-01` clock is skewed (`w32tm /resync`), correct time sync first (`[srv-012]`).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If an **internal Enterprise CA or approved SSL-Inspection Firewall Root CA** is missing on endpoints, deploy the verified Root CA `.cer` via **GPO / Intune Trusted Certificate Profile** (`Root` store) rather than asking users to click `"Proceed anyway"`!
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If a **server certificate expired** or lacks its **Intermediate CA chain**, renew the cert cleanly (`certbot renew` + reload web service, or renew from internal ADCS/public CA), install the full chain on the server/load balancer, and verify zero leftover bindings hold the old thumbprint (IIS bindings / Exchange `Enable-ExchangeCertificate`).

## Verification & Post-Fix Checks
1. Run `openssl s_client -connect <host>:443 -servername <host>` (or open in fresh Edge/Chrome window) and confirm `Verify return code: 0 (ok)` with a valid future `NotAfter` date and matching `SAN`.
2. Confirm Schannel `Event ID 36871 / 36887` stops logging errors on affected servers/workstations.

## Cross-Subject Escalation & Pivot Links
- **Browser blocks internal/SaaS portal with NET::ERR_CERT_DATE_INVALID or breaks SSO flow:** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](../09_Apps_LOB/app-001-browser-sso-and-lob-crash.md)
- **Corporate proxy Root CA works in browsers yet breaks git, npm, pip, or az CLI:** [app-004 — Developer Git/NPM/PIP SSL Proxy Certificate Errors & PowerShell ExecutionPolicy](../09_Apps_LOB/app-004-dev-git-ssl-proxy-cert-and-powershell-policy.md)
- **802.1X EAP-TLS Wi-Fi fails because RADIUS server or SCEP client certificate expired:** [net-002 — Wi-Fi Random Disconnects, Connected Without Internet, and 802.1X Auth Triage](../04_Network_VPN_VoIP/net-002-wifi-drops-and-8021x-auth.md)
- **Outlook Autodiscover HTTPS rejects mismatched internal SAN certificate:** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](../02_M365_Email_Collab/m365-001-outlook-auth-loop.md)

## Useful Links & External Tools
- **[Qualys SSL Labs Server Test](https://www.ssllabs.com/ssltest/)** — Audit public HTTPS endpoints for expired certificates, **Incomplete Intermediate CA Chains**, and weak TLS 1.0/1.1 protocols (check *"Do not show the results on the boards"*).
- **[DNS Checker](https://dnschecker.org/)** — Verify ACME/CA DNS validation `TXT` or `CNAME` records propagated globally during certificate renewal.

## Client Update Snippets (EN / FR)
- **EN:** We verified the TLS/SSL certificate chain and trusted Root CA configuration for the affected service, renewed/deployed the valid certificate, and confirmed HTTPS connections now verify cleanly without security warnings.
- **FR:** Nous avons vérifié la chaîne de certificats TLS/SSL et la configuration de l'autorité racine de confiance, renouvelé/déployé le certificat valide et confirmé que les connexions HTTPS fonctionnent sans alerte de sécurité.
