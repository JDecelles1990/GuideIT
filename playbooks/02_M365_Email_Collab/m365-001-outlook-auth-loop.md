---
id: m365-001
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: email_exchange_mailflow
title: Outlook Password Prompt Loop and Modern Auth Failure
tier: L2
keywords_en:
  - outlook keeps asking for password
  - outlook password prompt
  - outlook disconnected
  - modern auth broken
  - need password status bar
keywords_fr:
  - mot de passe en boucle
  - outlook demande mot de passe
  - courriel bloqué
  - outlook déconnecté
  - authentification moderne outlook
error_codes:
  - AADSTS50076
  - "0x80040115"
  - AADSTS700082
tags:
  - modern_auth_token
  - outlook_auth_loop
os:
  - windows
environment:
  - m365
  - entra_id
  - hybrid_ad
tools:
  - PowerShell
  - Microsoft Support and Recovery Assistant
  - dsregcmd
  - Registry Editor
risk_level: medium
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - id-001
  - net-001
  - sec-003
  - app-001
  - sec-001
linked_scripts:
  - 03_M365/Get-EntraRegistrationStatus.ps1
  - 03_M365/Get-OfficeActivationStatus.ps1
  - 03_M365/Get-MailDNSRecords.ps1
  - 03_M365/Clear-OutlookCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Can you sign into **Outlook on the Web ([Outlook on the Web](https://outlook.office.com/))** right now, or does your browser also reject your password/MFA (`[id-001]`)?
2. Did you **just change your Windows/M365 password**, switch phones for Microsoft Authenticator (`[id-003]`), or get a new laptop?
3. Look at the very bottom-right status bar of Classic Outlook: does it say **`Need Password`**, **`Trying to connect`**, or **`Disconnected`**?
4. Do Teams or OneDrive also show a yellow exclamation mark / sign-in prompt?

### Initial Scope & Classification
- Is this happening on one workstation (`PC-LAB-01`) or across multiple users in the tenant (`contoso.com`)? (Single PC + OWA works = corrupted local Windows Office/WAM token cache!)

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Unblock Email via Outlook Web ([Outlook on the Web](https://outlook.office.com/)) Immediately:** Verify password/MFA works in Edge/Chrome Incognito (`[id-001]` if locked!).
2. **Test Signing Out Inside Office + Inspect Credential Manager GUI:**
   - Open Outlook -> **File -> Office Account -> Sign out** (do NOT click Manage Account blindly without confirming!), quit Outlook (`Ctrl+Shift+Esc` -> verify `OUTLOOK.EXE` closed!), then check **Control Panel -> Credential Manager -> Windows Credentials** for old `MicrosoftOffice16_Data` / `ADAL` / `OneAuth` entries!
3. **Check `Work Offline` Toggle & Add-ins:** In Outlook **Send / Receive** tab, verify **Work Offline** isn't accidentally toggled blue! Try opening `outlook.exe /safe`.

### L2 Technical Diagnostics
1. Check Microsoft Entra / Hybrid join & Primary Refresh Token (PRT) health on `PC-LAB-01` (read-only):
   ```cmd
   dsregcmd /status
   ```
   Verify `AzureAdJoined` / `WorkplaceJoined` and `AzureAdPrt` status under SSO State.
2. Inspect Office Identity & Modern Auth registry settings (read-only):
   ```powershell
   Get-ItemProperty -Path "HKCU:\Software\Microsoft\Office\16.0\Common\Identity" -ErrorAction SilentlyContinue
   ```
   Confirm `EnableADAL` is not forced to `0` and `DisableADALatopWAMOverride` is not blocking WAM.
3. Verify connectivity to Exchange Online endpoints and check for stale Office credentials:
   ```powershell
   Test-NetConnection -ComputerName "outlook.office365.com" -Port 443 | Select-Object ComputerName, TcpTestSucceeded
   cmdkey /list | Select-String -Pattern "Office|Outlook|MicrosoftOffice16"
   ```

## Deep-Dive Investigation (L3)
1. Inspect Entra ID Sign-in Logs for `jsmith@example.com`:
   - `AADSTS50076`: Conditional Access requires MFA, but Outlook is attempting legacy auth or missing a WAM token.
   - `0x80040115`: Network/proxy/TLS interception or corrupted MAPI profile blocking Autodiscover/MAPI-over-HTTP.
2. Check Windows Web Account Manager (`Microsoft.AAD.BrokerPlugin`) package state and token cache folders (read-only):
   ```powershell
   Get-AppxPackage -Name "Microsoft.AAD.BrokerPlugin" | Select-Object Name, Version, Status
   Get-ChildItem "$env:LOCALAPPDATA\Microsoft\OneAuth" -ErrorAction SilentlyContinue | Select-Object Name, LastWriteTime
   ```
3. Verify local registry for `ExcludeExplicitO365Endpoint` or legacy Autodiscover overrides under `HKCU:\Software\Microsoft\Office\16.0\Outlook\AutoDiscover`.
4. Test Outlook in safe mode (`outlook.exe /safe`) to rule out COM add-in token interference.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Close all Office apps (`OUTLOOK.EXE`, `WINWORD.EXE`, `EXCEL.EXE`, `TEAMS.EXE`) and remove stale Office 16 credential cache entries via `cmdkey /delete:<TargetName>`.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Reset the local OneAuth / IdentityCache folders for the affected user profile (`jsmith@example.com`) so Outlook acquires a fresh Modern Auth token:
   ```powershell
   # Ensure Outlook and all Office apps are closed first
   Rename-Item -Path "$env:LOCALAPPDATA\Microsoft\OneAuth" -NewName "OneAuth.bak" -ErrorAction SilentlyContinue
   Rename-Item -Path "$env:LOCALAPPDATA\Microsoft\IdentityCache" -NewName "IdentityCache.bak" -ErrorAction SilentlyContinue
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `EnableADAL` was set to `0`, remove or set `EnableADAL` = `1` (`DWORD`) under `HKCU:\Software\Microsoft\Office\16.0\Common\Identity`.
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If the Outlook profile remains stuck with `0x80040115`, create a clean new Outlook Mail profile via **Control Panel -> Mail (Microsoft Outlook)** rather than overwriting the existing OST immediately.

## Verification & Post-Fix Checks
1. Launch Outlook, complete the MFA prompt once, and confirm the bottom-right status bar reads **`Connected to: Microsoft Exchange`**.
2. Send/receive a test message with `jsmith@example.com`, close and reopen Outlook, and verify no repeat prompt appears.

## Cross-Subject Escalation & Pivot Links
- **Repeated Outlook auth prompts come from a locked on-prem AD or Entra account:** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)
- **Autodiscover DNS lookup failure, broken VPN split-tunnel, or proxy timeout triggers 0x80040115:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Expired TLS certificate or untrusted proxy CA intercepts Outlook HTTPS Autodiscover calls:** [sec-003 — TLS/SSL Certificate Expired, Missing Intermediate Chain, and Untrusted Root CA](../06_Security_Access/sec-003-tls-ssl-certificate-expired-and-untrusted-ca.md)
- **Embedded WebView2/browser SSO cookie loop breaks Microsoft 365 modern authentication:** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](../09_Apps_LOB/app-001-browser-sso-and-lob-crash.md)
- **Unexpected MFA fatigue or unfamiliar session location points to token compromise:** [sec-001 — Suspected Business Email Compromise and Session Token Theft](../06_Security_Access/sec-001-bec-token-compromise.md)

## Useful Links & External Tools
- **[Microsoft My Account](https://myaccount.microsoft.com/)** — Verify active M365/Office license assignment and connected work devices.
- **[Microsoft My Sign-Ins & Security Info](https://mysignins.microsoft.com/security-info)** — Confirm the user's MFA methods are up to date before clearing cached tokens.
- **[Microsoft Remote Connectivity Analyzer](https://testconnectivity.microsoft.com/)** — Run Outlook Connectivity & Autodiscover tests when desktop auth loops persist.
- **[Microsoft 365 Service Health Status](https://status.cloud.microsoft/)** — Rule out active Entra ID or Exchange Online authentication incidents.
- **[Microsoft 365 Apps Admin Center](https://config.office.com/)** — Inspect Office Click-to-Run update channels, build inventory, and cloud policy overrides.

## Client Update Snippets (EN / FR)
- **EN:** We cleared the corrupted Office authentication token cache on `PC-LAB-01` and re-authenticated Outlook using Modern Auth. Please test sending and receiving emails and confirm no password prompt reappears.
- **FR:** Nous avons réinitialisé le cache de jetons d'authentification Office sur `PC-LAB-01` et reconnecté Outlook avec l'authentification moderne. Pouvez-vous tester l'envoi/réception de courriels et confirmer que la demande de mot de passe ne revient plus ?
