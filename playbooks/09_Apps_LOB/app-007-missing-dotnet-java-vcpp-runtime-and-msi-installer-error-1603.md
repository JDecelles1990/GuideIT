---
id: app-007
domain: 09_Apps_LOB
subject: "Applications & LOB"
subcategory: accounting_lob_runtimes
title: Missing .NET / Java / VC++ Runtime, MSI Error 1603, and Winget / Store Install Failures
tier: L2
keywords_en:
  - missing vcruntime140.dll lob app
  - dotnet desktop runtime missing
  - java runtime missing lob app
  - error 1603 msi log
  - winget microsoft store install failed
keywords_fr:
  - vcruntime140 manquant erreur dll
  - runtime dotnet manquant application
  - erreur installation msi 1603
  - java manquant application metier
  - echec installation winget store
error_codes:
  - MSI_1603
  - "0x80070643"
  - "0x80073CF3"
  - "1618"
  - VCRUNTIME140_MISSING
  - DOTNET_RUNTIME_MISSING
tags:
  - missing_dotnet_vcpp_java
  - msi_installer_1603
  - winget_store_install_fail
os:
  - windows
environment:
  - local_endpoint
  - intune
  - hybrid_ad
tools:
  - PowerShell
  - Winget
  - Event Viewer (Application / MsiInstaller)
  - Microsoft Program Install Troubleshooter
risk_level: medium
requires_admin: true
last_verified: 2026-11-23
related_ids:
  - sec-005
  - win-001
  - app-001
  - app-006
  - sec-002
linked_scripts:
  - 01_System/Get-RuntimesAndMSIHealth.ps1
  - 01_System/Get-PendingRebootStatus.ps1
  - 01_System/Get-RecentEventErrors.ps1
  - 01_System/Get-DiskSpaceReport.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. What **exact dialog or error code** popped up?
   - Missing runtime DLL/framework: *"The code execution cannot proceed because `VCRUNTIME140.dll` / `MSVCP140.dll` was not found"*, *"You must install .NET Desktop Runtime (x86/x64) to run this application"*, or *"Java Runtime Environment required"* (`VCRUNTIME140_MISSING` / `DOTNET_RUNTIME_MISSING`)
   - Failed MSI / Intune / RMM install: **`MSI Error 1603`**, **`1618`** (another install in progress), **`0x80070643`** (fatal installer error), or Store/Winget **`0x80073CF3`**
2. Does the prompt say **specifically `x86` (32-bit) or `x64` (64-bit)** for `.NET` / `Visual C++`? *(Installing x64 alone does NOT satisfy a 32-bit LOB accounting/ERP app!)*
3. Is `PC-LAB-01` waiting on a **pending Windows Reboot (`[win-001]`)**, low on `C:\` disk space, or did the user run an un-elevated installer (`[sec-005]`)?

### Initial Scope & Classification
- **Missing `VCRUNTIME140*.dll` / `MSVCP140.dll` (`VCRUNTIME140_MISSING`):** Missing or corrupted **Microsoft Visual C++ 2015–2022 Redistributable** (nearly always need BOTH **x86** and **x64** on Windows!).
- **Missing `.NET Desktop Runtime 6/8` (`DOTNET_RUNTIME_MISSING`):** Application requires **Windows Desktop Runtime** (not just base ASP.NET / Console `.NET Runtime`!) matching its exact major version & bitness.
- **MSI Error `1603` / `1618` / `0x80070643`:** Generic Windows Installer fatal return — top 5 real causes are **Pending Reboot lock**, **`Another installation is already in progress (1618)`**, **Old broken version failing uninstall**, **Missing `C:\` space or Temp folder ACL**, or **Defender/AV locking extracted MSI temp DLL (`sec-002`)**. Always read the verbose `/L*V` MSI log for **`Return value 3`**!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Installed Apps, Architecture & Disk Space)
1. **Check Exact Architecture & Version Requested in Error Prompt:**
   - Capture screenshot of the exact runtime popup (e.g., `.NET Desktop Runtime 8.0.x (x86)` vs `(x64)`). Remember: **32-bit ERP/accounting/scanner apps on 64-bit Windows require the `x86` runtime!**
2. **Check Pending Reboot & Free `C:\` Space First:**
   - Open Task Manager (`Details` tab) to verify no stale `msiexec.exe` is hung (`1618`), check **Start -> Power** for *"Update and restart"*, and ensure **>= 5 GB** free on `C:\`.
3. **Rule Out Standard-User UAC Permission Block (`[sec-005]`):** If the user lacks admin rights and the app is approved in Company Portal / RMM, follow `[sec-005]` rather than bypassing UAC.

### L2 Technical Diagnostics
1. **Audit Installed .NET, VC++ Redistributables, Java, `msiserver` Locks & MsiInstaller Event Log on `PC-LAB-01` (read-only):**
   ```powershell
   # Check .NET Desktop Runtimes & .NET Framework 4.x release
   Get-ChildItem "$env:ProgramFiles\dotnet\shared\Microsoft.WindowsDesktop.App" -ErrorAction SilentlyContinue | Select-Object Name
   (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full" -ErrorAction SilentlyContinue).Release

   # List installed Visual C++ Redistributables (both x64 and WOW6432Node x86)
   Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
                    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
       Where-Object { $_.DisplayName -like "Microsoft Visual C++*Redistributable*" } |
       Select-Object DisplayName, DisplayVersion | Sort-Object DisplayName

   # Check MSI InProgress lock & recent MsiInstaller failure events in last 72h
   Test-Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\InProgress"
   Get-WinEvent -FilterHashtable @{ LogName = 'Application'; ProviderName = 'MsiInstaller'; StartTime = (Get-Date).AddHours(-72) } -ErrorAction SilentlyContinue |
       Where-Object { $_.Id -in @(1033, 1034, 11708) -or $_.Level -le 2 } |
       Select-Object TimeCreated, Id, Message -First 10
   ```
   *(Run the linked `01_System/Get-RuntimesAndMSIHealth.ps1`, `01_System/Get-PendingRebootStatus.ps1`, `01_System/Get-RecentEventErrors.ps1`, and `01_System/Get-DiskSpaceReport.ps1` scripts directly from PowerShellStore!)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact error dialog screenshot, app name & architecture (`x86` vs `x64`), output of `Get-RuntimesAndMSIHealth.ps1`, pending reboot status, and excerpt around **`Return value 3`** from verbose MSI log (`C:\Windows\Temp\AppInstall.log`).

## Deep-Dive Investigation (L3)
1. **Capture Verbose MSI Installer Log (`msiexec /L*V`) & Search `Return value 3`:**
   - Error `1603` means nothing by itself — run with verbose logging and jump 20–40 lines **above** the **FIRST occurrence of `Return value 3`** (or `Error 1722` / `Error 1920` / `0x80070643`) to pinpoint whether a custom action, stopped service, driver signature, or missing prerequisite failed!
   ```powershell
   # Generate verbose MSI diagnostic log when reproducing Error 1603 (requires Admin)
   msiexec /i "C:\Temp\VendorApp.msi" /L*V "C:\Windows\Temp\VendorApp_MSI.log"
   # Parse lines around Return value 3 (read-only log scan)
   Select-String -Path "C:\Windows\Temp\VendorApp_MSI.log" -Pattern "Return value 3|Error 1[0-9]{3}|0x8007" -Context 15,2
   ```
2. **Corrupted Uninstall Registry Entry (`Error 1714` / `1603` During Upgrade):** If an older version's `.msi` cached copy under `C:\Windows\Installer` was wiped, upgrades fail `1603` trying to uninstall the old product code until cleared via Microsoft's **Program Install and Uninstall Troubleshooter** (`MicrosoftProgram_Install_and_Uninstall.meta.diagcab`).
3. **Winget / Microsoft Store Appx Failure (`0x80073CF3`):** Outdated **App Installer / Winget (`winget source update`)**, stale Microsoft Visual C++ UWP framework dependency, or Store blocked by firewall/proxy (`[net-009]`).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Verify vendor download provenance (download runtimes ONLY from official Microsoft/Adoptium/Oracle vendor URLs or verified `winget` Microsoft manifests), and confirm reboot timing with the user before clearing Pending Reboot / `1618` locks!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Install Verified Official Visual C++ 2015–2022 or .NET Desktop Runtimes)**
   - Install **BOTH `x86` and `x64`** [Microsoft Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) or the exact [Microsoft .NET Desktop Runtime](https://dotnet.microsoft.com/en-us/download/dotnet) version (`6.0`/`8.0` LTS) via elevated `winget`:
   ```powershell
   # Official Microsoft Winget IDs for Visual C++ 2015-2022 (both architectures) & .NET 8 Desktop Runtime
   winget install --id Microsoft.VCRedist.2015+.x64 --silent --accept-package-agreements --accept-source-agreements
   winget install --id Microsoft.VCRedist.2015+.x86 --silent --accept-package-agreements --accept-source-agreements
   # Example for .NET 8 Desktop Runtime (add --architecture x86 if a 32-bit app asks for x86!)
   winget install --id Microsoft.DotNet.DesktopRuntime.8 --silent --accept-package-agreements --accept-source-agreements
   ```
   - For corrupted existing VC++ Redistributables throwing `0x80070643`, run **Repair** in `Settings -> Apps -> Installed apps` before installing fresh.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Clear Stuck MSI `1618` Lock & Pending Reboot)**
   - If `Get-PendingRebootStatus.ps1` reports `RebootPending = True`, coordinate a full Windows **Restart** (not Shut down with Fast Startup!) FIRST — do not blindly delete `PendingFileRenameOperations` from mid-update Windows patches!
   - If `msiserver` is stuck mid-session with no real install running (`1618`), stop orphaned `msiexec.exe` processes ONLY after checking no RMM/Intune deployment is active, then restart `msiserver` and re-run installer as Administrator.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Repair Winget Source & Re-Register Store Dependency `0x80073CF3`)**
   ```powershell
   # Refresh Winget package sources (run as Administrator / current user)
   winget source reset --force
   winget source update
   ```

## Verification & Post-Fix Checks
1. Re-run `01_System/Get-RuntimesAndMSIHealth.ps1` confirming the required `.NET Desktop Runtime`, `Visual C++ x86/x64 Redistributable`, or `Java` entry now shows **Installed**, and `WindowsInstaller` shows no active lock or pending reboot.
2. Have `jsmith@example.com` launch the LOB / accounting application (or complete the MSI installation) cleanly with zero missing-DLL or `1603` errors.

## Cross-Subject Escalation & Pivot Links
- **User lacks admin rights / needs Intune Company Portal or UAC approval:** [sec-005 — User Cannot Install Approved Software, UAC Admin Prompt, and Local Admin Audit](../06_Security_Access/sec-005-software-install-uac-admin-prompt-and-local-admin-audit.md)
- **Pending Windows Update / Component Store corruption blocking installs (`0x80070005`):** [win-001 — Windows Update Failure and Component Store Corruption](../03_Windows_Endpoints/win-001-windows-update-corruption.md)
- **Installer extracted payload quarantined/blocked by Defender ASR:** [sec-002 — Microsoft Defender ASR Rule or Antivirus Blocking Legitimate LOB App or Macro](../06_Security_Access/sec-002-defender-asr-block-and-false-positive.md)
- **Accounting app (`QuickBooks`/`Sage 50`/`Acomba`) installs fine but fails Multi-User Mode:** [app-006 — Accounting & LOB Multi-User Errors (QuickBooks H202, Sage 50 Connection Manager, Acomba)](./app-006-accounting-lob-multi-user-mode-quickbooks-h202-sage50-acomba.md)
- **LOB web/client SSO redirects fail after app launch:** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](./app-001-browser-sso-and-lob-crash.md)

## Useful Links & External Tools
- **[Microsoft Visual C++ Redistributable Downloads](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)** — Official x86 and x64 Visual C++ 2015–2022 Redistributable downloads (`vc_redist.x86.exe` / `vc_redist.x64.exe`).
- **[Microsoft .NET Desktop Runtime Downloads](https://dotnet.microsoft.com/en-us/download/dotnet)** — Official `.NET 6 / .NET 8 LTS` Windows Desktop Runtime (x86/x64/ARM64) downloads.
- **[Windows Release Health & Known Issues](https://learn.microsoft.com/en-us/windows/release-health/)** — Verify known Windows Installer (`msiserver`) or Windows Store (`0x80073CF3`) update regressions.
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Review failed Win32 app IME deployment exit codes (`1603`, `1618`, `0x80070643`) and prerequisite dependency rules.

## Client Update Snippets (EN / FR)
- **EN:** We installed the missing Microsoft runtime prerequisites (.NET Desktop / Visual C++ Redistributable) and cleared the Windows Installer lock on `PC-LAB-01`, and the application now installs and launches cleanly. Could you please open the program on your side and confirm everything works properly?
- **FR:** Nous avons installé les prérequis système manquants (.NET Desktop / Visual C++ Redistributable) et réglé le blocage d'installation Windows Installer sur `PC-LAB-01`. Pouvez-vous lancer l'application de votre côté et nous confirmer que tout fonctionne correctement ?
