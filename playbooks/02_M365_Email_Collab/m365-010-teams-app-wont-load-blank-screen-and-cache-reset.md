---
id: m365-010
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: docs_onedrive_teams
title: Microsoft Teams App Won't Load, Stuck Signing In, or Blank Screen (Cache & Web Fallback)
tier: L1
keywords_en:
  - teams won't load
  - teams blank white screen
  - teams stuck loading
  - clear teams cache
  - new teams app crashed
keywords_fr:
  - teams ne se charge pas
  - ecran blanc microsoft teams
  - teams bloque au demarrage
  - vider cache microsoft teams
  - teams erreur connexion caa2000b
error_codes:
  - CAA2000B
  - "80090016"
  - TEAMS_BLANK_SCREEN
tags:
  - teams_wont_load
  - teams_cache_reset
os:
  - windows
  - macos
environment:
  - m365
  - entra_id
  - local_endpoint
tools:
  - Microsoft Teams (ms-teams.exe)
  - PowerShell
  - Microsoft Teams Web
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - m365-001
  - m365-007
  - net-003
  - app-001
linked_scripts:
  - 03_M365/Get-TeamsDiagnostics.ps1
  - 03_M365/Get-EntraRegistrationStatus.ps1
  - 03_M365/Clear-TeamsCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Does Teams show a **blank white/purple screen**, an endless **"Loading Microsoft Teams..." spinner**, or an error code (`CAA2000B`, `80090016`, *"We ran into a problem — Reconnecting"*)?
2. Can you open **`https://teams.microsoft.com`** in Edge/Chrome **normally** right now? *(Always give the Web link immediately if the user has an urgent meeting starting in 2 minutes!)*
3. Did you recently **change your password**, switch between **Work & Guest organizations**, or run a Windows update?

### Initial Scope & Classification
- Almost all New Teams (`ms-teams.exe` MSIX / WebView2) launch/blank-screen issues are fixed by an L1 **Teams App Reset / Cache Clear** without needing L2/L3 escalation. Check Teams Web first so the user doesn't miss meetings!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Unblock urgent meetings via Teams Web:** Direct `jsmith@example.com` to `https://teams.microsoft.com` (Edge or Chrome). If Teams Web works -> the M365 license and network are healthy, and the issue is purely the desktop app cache/WebView2 on `PC-LAB-01`!
2. **Make sure Teams actually closed (`Quit` vs `X`):** Closing the window leaves Teams running in the system tray! Right-click the Teams tray icon -> **Quit** (or check Task Manager for `ms-teams.exe` / `msedgewebview2.exe`).
3. **Check M365 Status & License:** Confirm Microsoft Teams isn't suffering a global service incident (`https://status.cloud.microsoft/`) and the user's M365 license has **Microsoft Teams** enabled.

### L2 Technical Diagnostics
1. **Inspect New Teams MSIX Package, WebView2 Runtime, and Auth Broker State (`PC-LAB-01`, read-only):**
   ```powershell
   Get-AppxPackage -Name "MSTeams" | Select-Object Name, Version, Status
   Get-ChildItem "$env:LOCALAPPDATA\Packages\MSTeams_8wekyb3d8bbwe\LocalCache" -ErrorAction SilentlyContinue |
       Select-Object Name, LastWriteTime
   Get-AppxPackage -Name "Microsoft.AAD.BrokerPlugin" | Select-Object Name, Version, Status
   ```
   - `CAA2000B` / `80090016`: Web Account Manager (`Microsoft.AAD.BrokerPlugin`) or TPM keyset token failure (`[m365-001]`).

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm whether `https://teams.microsoft.com` works, whether New Teams cache reset / MSIX Repair was tested, and exact error code (`CAA2000B` / `80090016`) + timestamp.

## Deep-Dive Investigation (L3)
1. **WebView2 Runtime Corruption / TLS Proxy Inspection:** If both New Teams and Office add-in panes render white screens, verify Microsoft Edge WebView2 Runtime (`Evergreen`) isn't corrupted or blocked from loopback/localhost by EDR/proxy policies (`[app-001]`).
2. **Stale Classic Teams Registry Keys:** Residual Office/Teams machine-wide installer policies (`HKCU\Software\Microsoft\Office\Teams`) or Conditional Access Token Protection policies failing on unregistered devices.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Confirm no active Teams call is running before quitting/resetting the Teams client. Clearing Teams cache keeps all chats, files, and meetings in the cloud (user only signs back in once).

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 GUI Reset — Zero PowerShell Needed!)** Close Teams completely (`Right-click taskbar -> Quit`), then open Windows **Settings -> Apps -> Installed apps -> Microsoft Teams -> Advanced options (`...`) -> Terminate -> Repair** (try Repair first; if still blank, click **Reset**!).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Cache Clear via PowerShell)** Clear **New Teams** (`MSTeams_8wekyb3d8bbwe`) and legacy Teams cache cleanly on `PC-LAB-01` (or run `psstore://03_M365/Clear-TeamsCache.ps1`):
   ```powershell
   Get-Process -Name "ms-teams","Teams" -ErrorAction SilentlyContinue | Stop-Process -Force
   $newTeamsCache = "$env:LOCALAPPDATA\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams"
   if (Test-Path $newTeamsCache) {
       Remove-Item -Path "$newTeamsCache\*" -Recurse -Force -ErrorAction SilentlyContinue
   }
   $classicCache = "$env:APPDATA\Microsoft\Teams"
   if (Test-Path $classicCache) {
       Remove-Item -Path "$classicCache\Cache\*","$classicCache\blob_storage\*","$classicCache\IndexedDB\*","$classicCache\Local Storage\*" -Recurse -Force -ErrorAction SilentlyContinue
   }
   ```
   - On **macOS**, quit Teams (`Cmd+Q`) and remove `~/Library/Group Containers/UBF8T346G9.com.microsoft.teams` / `~/Library/Containers/com.microsoft.teams2/Data/Library/Application Support/Microsoft/MSTeams`.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 `80090016` / `CAA2000B` WAM Token Reset)** Follow `[m365-001]` to refresh WAM/OneAuth caches and verify Windows **Settings -> Accounts -> Access work or school** connection is healthy.

## Verification & Post-Fix Checks
1. Relaunch **Microsoft Teams** on `PC-LAB-01`, sign in cleanly (`jsmith@example.com`), and verify Chats, Calendar, and Teams channels load within seconds.
2. Run a quick **Settings -> Devices -> Make a test call** (`[net-003]`) if audio/camera were also affected.

## Cross-Subject Escalation & Pivot Links
- **CAA2000B / WAM token loop persists across both Outlook and Teams:** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](./m365-001-outlook-auth-loop.md)
- **WebView2 / browser SSO loop affects both Teams Web and enterprise portals:** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](../09_Apps_LOB/app-001-browser-sso-and-lob-crash.md)
- **Teams opens yet external partner chat or guest tenant switching is blocked:** [m365-007 — Microsoft Teams External Federation & B2B Guest Access Blocked](./m365-007-teams-external-guest-access-and-federation.md)
- **Teams opens cleanly yet audio calls chop or drop:** [net-003 — Teams and VoIP Choppy Audio, High Jitter, and One-Way Sound Triage](../04_Network_VPN_VoIP/net-003-teams-voip-choppy-audio-and-jitter.md)

## Client Update Snippets (EN / FR)
- **EN:** We cleared the corrupted Microsoft Teams desktop cache and reset the local app state on `PC-LAB-01`. Could you relaunch Teams, sign back in, and confirm your chats and calendar load normally?
- **FR:** Nous avons vidé le cache corrompu de l'application Microsoft Teams et réinitialisé le client sur `PC-LAB-01`. Pouvez-vous relancer Teams, vous reconnecter et confirmer que vos conversations et votre calendrier s'affichent bien ?
