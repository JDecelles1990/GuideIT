---
id: win-011
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: boot_bitlocker_bsod
title: Windows Workstation Low Disk Space (C: Drive Full) Safe Cleanup
tier: L1
keywords_en:
  - c drive full windows
  - low disk space warning windows
  - not enough space on c drive
  - onedrive filling hard drive
  - safe disk cleanup windows
keywords_fr:
  - disque c plein windows
  - espace disque faible windows
  - plus d'espace disque c
  - nettoyer disque c windows
  - liberer espace disque windows
error_codes:
  - "0x80070070"
  - LOW_DISK_SPACE
tags:
  - windows_c_drive_full
  - workstation_disk_cleanup
os:
  - windows
environment:
  - local_endpoint
tools:
  - Windows Storage Settings
  - PowerShell
  - OneDrive Files On-Demand
risk_level: low
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - win-001
  - win-006
  - m365-005
  - srv-001
linked_scripts:
  - 01_System/Get-DiskSpaceReport.ps1
  - 01_System/Invoke-DeepSystemCleanup.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. How much free space remains on `C:` (less than `1 GB` can freeze Outlook, Windows Update `0x80070070`, and login profiles!), and does **This PC** show a red bar?
2. Did you recently download large `.zip`/video/ISO files, click **"Always keep on this device"** on big SharePoint/OneDrive folders, or leave another **former employee's Windows user profile** (`C:\Users\*`) on this shared PC?
3. Are you trying to clear space to install an urgent **Windows 11 / Feature Update** or save an active document?

### Initial Scope & Classification
- Distinguish **OneDrive/Outlook `.ost` user bloat** (solved per-user via *Files On-Demand* -> *Free up space* and Downloads/Recycle Bin) from **system-wide bloat** (`C:\Windows\Temp`, `SoftwareDistribution\Download`, `Windows.old`, old unused `C:\Users` profiles, crash dumps). Notice **workstation** cleanup belongs here (`win-011`), while **Windows Server VSS / data drives** escalate to `[srv-001]`!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Inspect Visual Breakdown in Windows Settings (Zero Commands!):** Open **Settings -> System -> Storage** -> view categories (**Installed apps**, **Temporary files**, **Other / User folders**) -> click **Show more categories**!
2. **Check Recycle Bin & Downloads:** Many `"C: drive full"` tickets have 40+ GB sitting in the user's **Recycle Bin** or **`Downloads`** folder (`.msi` installers, `.zip` archives, duplicate exports)! Ask user before emptying!
3. **Check OneDrive Local Cache Bloat:** Right-click the user's OneDrive folder in File Explorer -> **Properties -> Size on disk** (vs *Size*). If a green solid checkmark folder sits at 80 GB locally, **OneDrive Files On-Demand -> Free up space** reclaims it in 5 seconds without deleting anything from cloud!

### L2 Technical Diagnostics
1. **Locate Largest User Folders, System Caches, and `.ost`/`.dmp` Files (read-only — or run `psstore://01_System/Get-DiskSpaceReport.ps1`):**
   ```powershell
   Get-PSDrive C | Select-Object Name, @{N='UsedGB';E={[math]::Round($_.Used/1GB,2)}}, @{N='FreeGB';E={[math]::Round($_.Free/1GB,2)}}
   Get-ChildItem "C:\Users" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
       $bytes = (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
       [PSCustomObject]@{ Profile = $_.Name; SizeGB = [math]::Round($bytes / 1GB, 2) }
   } | Sort-Object SizeGB -Descending
   ```
   ```powershell
   # Check top space hogs in Windows Temp, SoftwareDistribution, Outlook OST, and Crash Dumps
   @(
       "$env:SystemRoot\Temp",
       "$env:SystemRoot\SoftwareDistribution\Download",
       "$env:SystemRoot\Minidump",
       "$env:LOCALAPPDATA\Microsoft\Outlook"
   ) | ForEach-Object {
       if (Test-Path $_) {
           $sz = (Get-ChildItem $_ -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
           [PSCustomObject]@{ Path = $_; SizeGB = [math]::Round($sz / 1GB, 2) }
       }
   }
   ```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact `FreeGB` on `C:`, top 3 largest folders (`C:\Users\*`, `Windows`, `ProgramData`), and whether `C:` is physically small (`128 GB` SSD needing upgrade).

## Deep-Dive Investigation (L3)
1. **Runaway Vendor Log / `C:\Windows\Logs\CBS` Bloat (`cab_*` Files):** A stuck Windows `CBS.log` rotation (>2 GB fills `Windows\Temp` with hundreds of `cab_*` files) fills `C:` repeatedly until `TrustedInstaller` is stopped, `CBS` logs cleared safely, and component store cleaned (`[win-001]`).
2. **Hidden VSS System Restore Shadow Storage:** Run `vssadmin list shadowstorage` (`[srv-001]`) if folder sums don't match used `C:` space — orphaned System Restore snapshots can hold 30–60 GB invisible to File Explorer!

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER blindly delete user files (`Desktop`, `Documents`, `Downloads`) or old user profiles (`C:\Users\*`) without confirming backup/OneDrive sync and user/manager approval!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Zero-Data-Loss Cloud Reclamation)** In File Explorer on OneDrive/SharePoint folders showing solid green checkmarks (`Always keep on this device`), right-click -> **Free up space** (converts files back to cloud-only placeholders while keeping 100% safely in OneDrive/SharePoint!).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Safe GUI Temporary Files Cleanup)** Ask user permission to empty **Recycle Bin**, review large old installers in `Downloads`, and run **Settings -> System -> Storage -> Temporary files** (check `Temporary Windows installation files / Windows.old`, `Delivery Optimization Files`, `Temporary Internet Files`, `Recycle Bin`).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Component Store & System Temp Cleanup — or run `psstore://01_System/Invoke-DeepSystemCleanup.ps1`)**
   ```cmd
   REM Safely cleans superseded WinSxS update components without breaking rollback ability unless /ResetBase is used
   DISM /Online /Cleanup-Image /StartComponentCleanup
   cleanmgr.exe /verylowdisk
   ```

## Verification & Post-Fix Checks
1. Confirm `Get-PSDrive C` shows healthy free capacity (at least **`15–25 GB` free**, >15% of volume) and Windows warning banner cleared.
2. Re-test previously blocked task (e.g., Windows Update `[win-001]`, Outlook launch, OneDrive sync `[m365-005]`).

## Cross-Subject Escalation & Pivot Links
- **Cleared C: space unblocks stalled Windows Update / DISM component cleanup:** [win-001 — Windows Update Failure and Component Store Corruption](./win-001-windows-update-corruption.md)
- **Full C: drive caused Outlook/Teams or OS disk queue saturation:** [win-006 — Windows High CPU, 100% Disk Usage, and Memory Leak Triage (Event 129 / 153 / 2004)](./win-006-windows-high-cpu-100-disk-and-memory-leak.md)
- **OneDrive sync bloat filled workstation SSD (use Files On-Demand Free Up Space):** [m365-005 — OneDrive Sync Stuck Processing Changes and SharePoint Path Limit Errors](../02_M365_Email_Collab/m365-005-onedrive-sync-stuck-and-sharepoint-path-limit.md)
- **Same low disk space / VSS crisis occurs on a Windows Server volume:** [srv-001 — Windows Server Disk Space Exhaustion and VSS Shadow Copy Backup Failure](../08_Servers_Cloud_Infra/srv-001-vss-backup-and-disk-triage.md)

## Client Update Snippets (EN / FR)
- **EN:** We identified the largest temporary system caches / synced file bloat filling drive `C:` on `PC-LAB-01`, safely reclaimed space using Storage Cleanup and OneDrive Files On-Demand without losing data, and verified healthy free space. Could you test saving files and confirm everything works cleanly?
- **FR:** Nous avons identifié les fichiers temporaires système / caches volumineux qui saturaient le disque `C:` sur `PC-LAB-01`, libéré l'espace de façon sécuritaire sans perte de données et vérifié la disponibilité disque. Pouvez-vous tester l'enregistrement de vos fichiers et confirmer que l'alerte a disparu ?
