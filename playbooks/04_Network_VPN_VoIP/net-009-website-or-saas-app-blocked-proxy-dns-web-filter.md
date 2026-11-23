---
id: net-009
domain: 04_Network_VPN_VoIP
subject: "Network, VPN & VoIP"
subcategory: ethernet_proxy_filtering
title: Website or SaaS App Blocked (Web Filter, PAC Proxy, Hosts File, or SSL Inspection)
tier: L2
keywords_en:
  - website blocked work network
  - saas app won't load proxy error
  - web filter content block fortiguard umbrella
  - pac proxy configuration error
  - hosts file blocking site
keywords_fr:
  - site web bloque reseau entreprise
  - erreur proxy pac navigateur
  - filtre web bloque application saas
  - site inaccessible fichier hosts
  - inspection ssl bloque site web
error_codes:
  - ERR_CONNECTION_RESET
  - ERR_PROXY_CONNECTION_FAILED
  - ERR_NAME_NOT_RESOLVED
  - HTTP_403_WEB_FILTER
  - SSL_INSPECTION_BLOCK
tags:
  - website_blocked_filter
  - proxy_pac_misconfig
  - split_dns_ssl_inspection
os:
  - windows
  - macos
  - cross_platform
environment:
  - network
  - saas
  - local_endpoint
tools:
  - PowerShell
  - Browser DevTools (Network Tab)
  - Web Filter / SASE Admin Portal
  - nslookup / curl
risk_level: low
requires_admin: false
last_verified: 2026-11-23
related_ids:
  - net-001
  - net-006
  - sec-003
  - app-004
  - app-001
linked_scripts:
  - 02_Network/Get-WebProxyAndTLSDiagnostics.ps1
  - 02_Network/Test-PortConnectivity.ps1
  - 02_Network/Get-NetworkSnapshot.ps1
  - 03_M365/Clear-BrowserCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Does this happen on **ONLY ONE specific website / SaaS portal**, or on **multiple websites**?
2. What exact screen or browser error appears: a **branded corporate block page** (FortiGuard, Cisco Umbrella, Zscaler, Defender Web Content Filtering, Sophos), **`ERR_PROXY_CONNECTION_FAILED`**, **`ERR_CONNECTION_RESET`**, **`ERR_NAME_NOT_RESOLVED`**, or a **`Your connection is not private`** SSL warning (`sec-003`)?
3. Does the exact same URL load properly on a **phone over cellular / mobile hotspot (off-VPN)**, AND does it fail only on **office LAN / VPN / SASE agent**?
4. Do coworkers on the same office network see the identical block?

### Initial Scope & Classification
- **Works on mobile hotspot, blocked on LAN/VPN with block page:** Expected corporate **DNS Web Filter / Firewall / Defender SmartScreen / Conditional Access** block — follow approved category/URL allowlist workflow after verifying site safety via [URLScan.io](https://urlscan.io/).
- **`ERR_PROXY_CONNECTION_FAILED` across ALL sites:** Stale `ProxyEnable = 1` / offline `127.0.0.1:<port>` loopback proxy left behind by an uninstalled VPN/ad-blocker, or unreachable `.pac` PAC script URL.
- **`127.0.0.1` / `0.0.0.0` or unexpected internal IP returned locally vs public `1.1.1.1`:** Split-brain DNS override, DNS sinkhole (Umbrella/Defender Web Filtering), or stale entry in `hosts`.
- **Site loads blank/403 ONLY when SSL Deep Inspection intercepts TLS:** Corporate proxy CA re-signing TLS breaks pinned desktop apps or browsers lacking the Root CA (`sec-003` / `app-004`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Isolate Browser, Incognito & Hotspot)
1. **Test an Incognito / InPrivate Window (`Ctrl+Shift+N`) + Different Browser:** Rules out corrupt cookies, ad-block extensions, or stale cached redirects (`[app-001]` / `Clear-BrowserCache`).
2. **Inspect Proxy Toggle in Windows Settings (`Settings -> Network & internet -> Proxy`):** Check whether **Use setup script (PAC)** or **Use a proxy server** (`Manual`) is unexpectedly toggled **ON** (e.g., pointing to `127.0.0.1` or an old decommissioned proxy IP!).
3. **Check Site Safety Before Whitelisting:** Never allowlist an unknown client URL on a corporate firewall without first detonating it safely in **[URLScan.io](https://urlscan.io/)** (Private/Unlisted scan) and checking **[Downdetector](https://downdetector.com/)** to confirm the vendor itself isn't down!

### L2 Technical Diagnostics
1. **Run Proxy, Hosts File, Split-DNS & TLS Inspection Diagnostics on `PC-LAB-01` (read-only):**
   ```powershell
   # Inspect WinINET proxy & PAC URL settings
   Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings" |
       Select-Object ProxyEnable, ProxyServer, AutoConfigURL, ProxyOverride

   # Inspect WinHTTP system proxy (used by Windows services, Office, & background agents)
   netsh winhttp show proxy

   # Check local hosts file for hardcoded overrides
   Get-Content "$env:SystemRoot\System32\drivers\etc\hosts" |
       Where-Object { $_ -and -not $_.Trim().StartsWith('#') }

   # Compare local corporate DNS vs public DNS (1.1.1.1) for sinkhole/split-DNS differences
   Resolve-DnsName -Name "app.example.com" -Type A -ErrorAction SilentlyContinue
   Resolve-DnsName -Name "app.example.com" -Server "1.1.1.1" -Type A -DnsOnly -ErrorAction SilentlyContinue
   ```
   *(You can also run `02_Network/Get-WebProxyAndTLSDiagnostics.ps1` directly from PowerShellStore — pass `TargetHost` for the exact domain and it will compare local vs public DNS and inspect the live TLS certificate Issuer for Zscaler/FortiGate/Sophos SSL Inspection!)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact URL requested, screenshot of exact browser error / block page, result of mobile hotspot comparison, output of `Get-WebProxyAndTLSDiagnostics.ps1` (proxy, DNS comparison, and TLS Issuer), and business justification / ticket approval from manager.

## Deep-Dive Investigation (L3)
1. **Browser HAR / DevTools Network Trace (`F12 -> Network`):** Inspect whether the HTTP `403`/`502`/`503` response header originates from the **destination SaaS WAF** (e.g., Cloudflare/Akamai blocking shared VPN egress IP or geo-IP outside Canada) vs the **corporate firewall / SASE** (`Via:`, `X-Squid-Error`, `FortiGuard`).
2. **Corporate Firewall / SASE Policy & SSL Deep Inspection Bypass:** If `Get-WebProxyAndTLSDiagnostics.ps1` shows the TLS Issuer is an internal firewall CA (`Fortinet`, `Zscaler`, `Sophos`, `Palo Alto`) and the SaaS/desktop app uses certificate pinning (`SSH/Git/Accounting API/Banking`), add a targeted **SSL Inspection Exemption (No-Inspect / Splice)** for that specific FQDN/wildcard rather than disabling inspection globally.
3. **DNS Propagation Check:** Verify via **[DNS Checker](https://dnschecker.org/)** whether a newly launched client portal or SaaS CNAME simply hasn't propagated to the internal AD DNS forwarders yet.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Verify security approval and scan unknown URLs with [URLScan.io](https://urlscan.io/) BEFORE requesting firewall/DNS filter exceptions. Never delete needed corporate PAC/proxy settings on managed SASE devices without confirming policy intent.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Browser Cache & Extension Isolation)**
   - Clear stale site cache/redirect loops with `03_M365/Clear-BrowserCache.ps1` or test with ad-blocker / privacy browser extensions temporarily disabled for the trusted corporate portal.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Clear Orphaned Rogue Loopback Proxy — Confirm Before Changing!)**
   ```powershell
   # ONLY run after confirming no active corporate proxy/Zscaler/Umbrella should be set
   $inetKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
   Set-ItemProperty -Path $inetKey -Name ProxyEnable -Value 0
   Remove-ItemProperty -Path $inetKey -Name ProxyServer -ErrorAction SilentlyContinue
   # Flush DNS resolver cache afterward
   ipconfig /flushdns
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Scoped Web-Filter Allowlist / SSL Exemption)**
   - If blocked by **Microsoft Defender Web Content Filtering** or corporate Firewall/DNS Filter (Umbrella/FortiGate), verify ticket approval, create a scoped **FQDN URL Indicator / Web Filter Override** in **[Microsoft Defender Portal](https://security.microsoft.com/)** or the firewall admin console, and sync policy on `PC-LAB-01`.

## Verification & Post-Fix Checks
1. Re-run `02_Network/Get-WebProxyAndTLSDiagnostics.ps1` for the target hostname and verify local DNS, TCP 443, and TLS certificate validation pass cleanly.
2. Have `jsmith@example.com` reload the website or SaaS app in a normal browser tab (`Ctrl+F5`) and confirm end-to-end sign-in works without errors.

## Cross-Subject Escalation & Pivot Links
- **ALL internet and DNS resolution fails (not just one site):** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](./net-001-dns-apipa-vpn-triage.md)
- **Site fails ONLY while connected to corporate VPN client:** [net-006 — Remote Client VPN Cannot Connect (FortiClient, GlobalProtect, AnyConnect, Windows VPN)](./net-006-client-vpn-wont-connect-forticlient-anyconnect-globalprotect.md)
- **Browser shows certificate/Root CA trust error (`NET::ERR_CERT_AUTHORITY_INVALID`):** [sec-003 — TLS/SSL Certificate Expired, Missing Intermediate Chain, and Untrusted Root CA](../06_Security_Access/sec-003-tls-ssl-certificate-expired-and-untrusted-ca.md)
- **Developer CLI tools (`git`, `npm`, `pip`) fail SSL check behind proxy:** [app-004 — Developer Git/NPM/PIP SSL Proxy Certificate Errors & PowerShell ExecutionPolicy](../09_Apps_LOB/app-004-dev-git-ssl-proxy-cert-and-powershell-policy.md)
- **Browser SSO login stuck in infinite redirect loop on the target SaaS app:** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](../09_Apps_LOB/app-001-browser-sso-and-lob-crash.md)

## Useful Links & External Tools
- **[URLScan.io](https://urlscan.io/)** — Safely detonate and inspect a user-reported website or redirect chain in Private/Unlisted mode before allowlisting it.
- **[DNS Checker (Global Propagation)](https://dnschecker.org/)** — Verify whether global public DNS matches internal AD/ISP resolvers when diagnosing split-brain DNS or new domain cutovers.
- **[Qualys SSL Labs Server Test](https://www.ssllabs.com/ssltest/)** — Verify if a third-party SaaS site itself has an expired certificate or broken intermediate TLS chain.
- **[Microsoft Defender Portal](https://security.microsoft.com/)** — Review Defender SmartScreen URL indicators, Web Content Filtering blocks, and Defender for Endpoint policy exemptions.
- **[Downdetector](https://downdetector.com/)** — Rule out a widespread third-party vendor or CDN outage before changing corporate firewall policies.

## Client Update Snippets (EN / FR)
- **EN:** We investigated why the website/application was blocked on `PC-LAB-01`, identified the proxy/web-filter rule (or DNS/SSL interception mismatch), verified the domain safely, and restored access. Could you please refresh the page (`Ctrl+F5`) and confirm it loads normally on your side?
- **FR:** Nous avons analysé le blocage du site/application sur `PC-LAB-01`, corrigé la configuration proxy/DNS ou l'exception de filtrage web après vérification de sécurité, et rétabli l'accès. Pouvez-vous actualiser la page (`Ctrl+F5`) et nous confirmer que tout charge normalement ?
