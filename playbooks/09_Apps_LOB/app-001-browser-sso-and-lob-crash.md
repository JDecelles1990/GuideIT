---
id: app-001
domain: 09_Apps_LOB
subject: "Applications & LOB"
subcategory: browsers_sso_dev_tools
title: Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage
tier: L1
keywords_en:
  - redirect loop
  - white page login
  - app crashes on launch
  - sso loop
  - browser login error
keywords_fr:
  - page blanche
  - boucle de connexion
  - boucle de redirection
  - application plante
  - plantage application
error_codes:
  - ERR_TOO_MANY_REDIRECTS
  - "1000"
  - HTTP_400
tags:
  - browser_sso_loop
  - lob_app_crash
os:
  - windows
  - macos
environment:
  - saas
  - local_endpoint
  - m365
tools:
  - Microsoft Edge
  - Google Chrome
  - Event Viewer
  - PowerShell
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - net-001
  - sec-003
  - m365-001
  - id-007
linked_scripts:
  - 03_M365/Clear-BrowserCache.ps1
  - 03_M365/Get-EntraRegistrationStatus.ps1
---

## Fast Triage (Under 2 Minutes)
- **Browser SSO / White Page:** Does the redirect loop (`ERR_TOO_MANY_REDIRECTS` / `HTTP 400`) disappear inside an **InPrivate / Incognito** window?
- **LOB App Crash:** Does the application crash only for `jsmith@example.com` on `PC-LAB-01`, or for all users on RDS/local desktops?
- Did an Office, browser, `.NET`, or LOB software update run recently?

## Read-Only Diagnostics (L1-L2)
1. **Browser SSO / Web App Triage:**
   - Test in **InPrivate** (`msedge.exe --inprivate`) or **Incognito** to isolate cookies/extensions vs tenant IdP outage.
   - Verify system clock & time zone accuracy on `PC-LAB-01` (SAML/OIDC tokens fail immediately if clock skew > 5 minutes):
     ```powershell
     Get-Date
     w32tm /query /status
     ```
2. **LOB Desktop Application Crash Triage (read-only):**
   - Inspect `Application` Event Log for `Event ID 1000` (Application Error) and `Event ID 1026` (.NET Runtime) to capture exact `Faulting application name`, `Faulting module name`, and `Exception code`:
     ```powershell
     Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000, 1026; StartTime = (Get-Date).AddDays(-2) } -MaxEvents 10 -ErrorAction SilentlyContinue |
         Select-Object TimeCreated, Id, Message
     ```
   - Check installed `.NET` runtimes if a `.NET` app crashes at startup:
     ```cmd
     dotnet --info
     ```

## Deep-Dive Investigation (L3)
1. **Browser Profile / Cookie Bloat (`HTTP 400 Bad Request - Request Header Or Cookie Too Long`):** Open DevTools (`F12` -> **Network** -> check `Preserve log`) to inspect repeating 302 redirects between `login.microsoftonline.com` and the SaaS/LOB app (`https://app.example.com`). Look for conflicting signed-in M365 profiles or stale `FedAuth`/`ESTSAUTH` cookies.
2. **Per-User AppData vs Machine-Wide Binary Corruption:** Compare behavior under a fresh Windows local/domain test user profile; if it runs there, the fault lies in `%LOCALAPPDATA%` / `%APPDATA%` user config, corrupted ClickOnce cache (`%LOCALAPPDATA%\Apps\2.0`), or broken Excel/PDF COM add-ins.
3. **macOS Crash Reports:** Check `~/Library/Logs/DiagnosticReports/` (`.ips` crash logs) for missing dynamic libraries or Gatekeeper quarantine attributes.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For browser SSO loops, clear site cookies and cache specifically for the SaaS app and `login.microsoftonline.com`, or create a dedicated clean Edge/Chrome work profile for `jsmith@example.com` (never wipe saved passwords/bookmarks without user consent).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For per-user LOB app crashes isolated to corrupted user cache, close the app and rename its `%LOCALAPPDATA%\<VendorApp>` cache folder to `.bak` before relaunching.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `Event ID 1000`/`1026` identifies a missing or corrupted `.NET Desktop Runtime` / `Visual C++ Redistributable`, run an elevated Repair on that runtime via **Installed Apps** or approved deployment tool.

## Verification & Post-Fix Checks
1. Close and relaunch the browser or LOB application as `jsmith@example.com` and complete login and core workflow without redirects or crashes.
2. Confirm no new `Event ID 1000` errors appear in Event Viewer after launch.

## Cross-Subject Escalation & Pivot Links
- **App/website fails DNS lookup, hits captive portal, or breaks over VPN split-tunnel:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Browser displays NET::ERR_CERT_DATE_INVALID or blocks untrusted proxy/internal TLS CA:** [sec-003 — TLS/SSL Certificate Expired, Missing Intermediate Chain, and Untrusted Root CA](../06_Security_Access/sec-003-tls-ssl-certificate-expired-and-untrusted-ca.md)
- **Browser M365 SSO loop impacts Outlook Modern Auth (AADSTS700082):** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](../02_M365_Email_Collab/m365-001-outlook-auth-loop.md)
- **Conditional Access Geo-Block outside Canada forces repeated SSO challenge redirects:** [id-007 — Geo-Blocking Outside Canada, Conditional Access Named Locations & Travel Access](../01_Identity_AD_Entra/id-007-geo-blocking-outside-canada-travel-access.md)

## Client Update Snippets (EN / FR)
- **EN:** We isolated and cleared the conflicting browser session / application cache causing the login loop on `PC-LAB-01`. Please sign in once more and confirm the application loads normally.
- **FR:** Nous avons isolé et nettoyé le conflit de session navigateur / cache applicatif qui causait l'erreur sur `PC-LAB-01`. Veuillez vous reconnecter et nous confirmer que l'application se charge normalement.
