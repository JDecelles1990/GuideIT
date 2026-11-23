---
id: win-001
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: updates_win11_licensing
title: Windows Update Failure and Component Store Corruption
tier: L2
keywords_en:
  - windows update failed
  - update stuck
  - corrupted system files
  - windows slow after update
  - component store repair
keywords_fr:
  - mise à jour bloquée
  - mise a jour echouee
  - fichiers système corrompus
  - windows lent
  - erreur windows update
error_codes:
  - "0x80070005"
  - "0x800f081f"
  - "0x80240034"
tags:
  - windows_update
  - component_store
os:
  - windows
environment:
  - local_endpoint
  - hybrid_ad
  - intune
tools:
  - PowerShell
  - DISM
  - SFC
  - Event Viewer
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - srv-001
  - win-002
  - win-005
  - prt-001
---

## Fast Triage (Under 2 Minutes)
- Which specific KB or feature update failed, and what exact error code (`0x80070005`, `0x800f081f`, `0x80240034`) appears in **Settings -> Windows Update -> Update history**?
- Does `PC-LAB-01` have at least 15–20 GB of free space on `C:`?
- Is the device managed by Intune/WSUS/Group Policy, and is a third-party AV/EDR blocking update services?

## Read-Only Diagnostics (L1-L2)
1. Check free disk space, pending reboot indicators, and core Windows Update service status (read-only):
   ```powershell
   Get-PSDrive C | Select-Object Name, @{N='FreeGB';E={[math]::Round($_.Free/1GB,2)}}
   Get-Service wuauserv, bits, cryptsvc, trustedinstaller | Select-Object Name, Status, StartType
   ```
2. Run non-destructive component store & system file checks from an elevated prompt (read-only):
   ```cmd
   DISM /Online /Cleanup-Image /CheckHealth
   DISM /Online /Cleanup-Image /ScanHealth
   sfc /verifyonly
   ```
3. Generate a readable Windows Update log or inspect recent `Setup` / `WindowsUpdateClient` events:
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-WindowsUpdateClient'; StartTime = (Get-Date).AddDays(-3) } -MaxEvents 15 |
       Select-Object TimeCreated, Id, LevelDisplayName, Message
   ```

## Deep-Dive Investigation (L3)
1. Generate `WindowsUpdate.log` on the Desktop for exact failure stage analysis (`0x80070005` = Access Denied / ACL or EDR lock; `0x800f081f` = missing source payload in WinSxS; `0x80240034` = interrupted download / WSUS or proxy issue):
   ```powershell
   Get-WindowsUpdateLog -LogPath "$env:USERPROFILE\Desktop\WindowsUpdate.log"
   ```
2. Inspect `C:\Windows\Logs\CBS\CBS.log` and `C:\Windows\Logs\DISM\dism.log` for failing package names or `STATUS_ACCESS_DENIED` entries.
3. Verify WSUS/Update for Business registry policies under `HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate` (`WUServer`, `DoNotConnectToWindowsUpdateInternetLocations`) to confirm the endpoint isn't pointed at an unreachable internal WSUS server.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Repair the Windows Component Store and system files on `PC-LAB-01` (requires elevated prompt and may take 10–20 minutes):
   ```cmd
   DISM /Online /Cleanup-Image /RestoreHealth
   sfc /scannow
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `0x80240034` or stalled downloads persist, stop update services, rename `SoftwareDistribution` and `catroot2`, and restart services:
   ```powershell
   Stop-Service -Name wuauserv, bits, cryptsvc -Force
   Rename-Item -Path "$env:SystemRoot\SoftwareDistribution" -NewName "SoftwareDistribution.old"
   Rename-Item -Path "$env:SystemRoot\System32\catroot2" -NewName "catroot2.old"
   Start-Service -Name cryptsvc, bits, wuauserv
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Reboot the workstation if pending file-rename operations exist, then re-trigger the update scan.

## Verification & Post-Fix Checks
1. Run `DISM /Online /Cleanup-Image /CheckHealth` and confirm `"No component store corruption detected"`.
2. Re-run **Check for updates** in Windows Settings and verify the failing KB installs with status `Installed`.

## Cross-Subject Escalation & Pivot Links
- **Windows Update (0x8024402c) fails due to corporate proxy, DNS, or VPN split-tunnel:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Insufficient free disk space or VSS/component store bloat stalls cumulative patching:** [srv-001 — Windows Server Disk Space Exhaustion and VSS Shadow Copy Backup Failure](../08_Servers_Cloud_Infra/srv-001-vss-backup-and-disk-triage.md)
- **Cumulative BIOS/OS update triggered BitLocker recovery key screen on reboot:** [win-002 — BitLocker Recovery Key Prompt After Update and TPM Lockout Triage](./win-002-bitlocker-recovery-screen-and-tpm.md)
- **Broken Windows Update Servicing Stack blocks Intune Windows 11 Feature Update:** [win-005 — Intune Windows 10 to Windows 11 Migration, Feature Updates, and Safeguard Holds](./win-005-intune-windows-11-migration-and-safeguard-holds.md)
- **Recent Windows security KB triggers RPC network printer error 0x0000011b:** [prt-001 — Print Spooler Stuck, Offline Printer, and RPC Print Error 0x0000011b](../05_Printers_Devices/prt-001-spooler-and-0x0000011b.md)

## Client Update Snippets (EN / FR)
- **EN:** We repaired corrupted Windows system update components on `PC-LAB-01` and cleared the stalled update cache. Windows Update is now installing cleanly; a reboot may be required to finalize installation.
- **FR:** Nous avons réparé les composants Windows Update corrompus sur `PC-LAB-01` et réinitialisé le cache des mises à jour. Les mises à jour s'installent maintenant correctement ; un redémarrage peut être requis pour finaliser l'installation.
