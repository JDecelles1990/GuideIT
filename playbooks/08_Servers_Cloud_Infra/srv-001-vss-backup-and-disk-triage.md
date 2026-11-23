---
id: srv-001
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: windows_server_sql
title: Windows Server Disk Space Exhaustion and VSS Shadow Copy Backup Failure
tier: L3
keywords_en:
  - backup failed
  - shadow copy error
  - server disk full
  - vss writer failed
  - low disk space server
keywords_fr:
  - sauvegarde échouée
  - sauvegarde echouee
  - disque serveur plein
  - espace disque saturé
  - erreur vss
error_codes:
  - "8193"
  - "12289"
  - "0x80042306"
  - "0x8004231f"
tags:
  - vss_writer_failure
  - server_disk_full
os:
  - windows
environment:
  - cloud_infra
  - on_prem_ad
  - hybrid_ad
tools:
  - PowerShell
  - vssadmin
  - Event Viewer
  - Disk Management
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - win-001
  - srv-016
  - srv-013
linked_scripts:
  - 01_System/Get-DiskSpaceReport.ps1
  - 01_System/Invoke-DeepSystemCleanup.ps1
---

## Fast Triage (Under 2 Minutes)
- Is a critical production volume (`C:` or `D:`) below 5% free space on `SRV-FILE-01`, causing service stalls or backup failure?
- Check the backup job log for exact VSS codes (`0x80042306` = shadow copy provider error; `0x8004231f` = insufficient storage for shadow copy; Event ID `8193` / `12289`).
- Confirm whether `SRV-FILE-01` is a VM (Hyper-V/VMware/Azure) with unmerged snapshots/checkpoints consuming datastore space.

## Read-Only Diagnostics (L1-L2)
1. Check volume free space, VSS writer health, and shadow storage allocation on `SRV-FILE-01` (read-only, elevated):
   ```powershell
   Get-Volume | Where-Object DriveLetter | Select-Object DriveLetter, FileSystemLabel,
       @{N='SizeGB';E={[math]::Round($_.Size/1GB,2)}},
       @{N='FreeGB';E={[math]::Round($_.SizeRemaining/1GB,2)}}
   ```
   ```cmd
   vssadmin list writers
   vssadmin list shadowstorage
   vssadmin list shadows
   ```
2. Identify the largest top-level directories without touching production data (read-only):
   ```powershell
   Get-ChildItem -Path "C:\" -Directory -Force -ErrorAction SilentlyContinue | ForEach-Object {
       $size = (Get-ChildItem $_.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
       [PSCustomObject]@{ Folder = $_.FullName; SizeGB = [math]::Round($size / 1GB, 2) }
   } | Sort-Object SizeGB -Descending | Select-Object -First 10
   ```
3. Inspect `Application` and `System` Event Logs for VSS errors (`8193`, `12289`, `12293`) and disk warnings (`2013`):
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 8193, 12289, 12293; StartTime = (Get-Date).AddDays(-2) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, ProviderName, Message
   ```

## Deep-Dive Investigation (L3)
1. **Stuck VSS Writers (`Retryable Error` / `Waiting for completion`):** Identify which specific writer (`System Writer`, `SqlServerWriter`, `NTDS`, `Hyper-V VSS Writer`) failed and examine `COM+ Event System`, `Volume Shadow Copy`, and `Microsoft Software Shadow Copy Provider` service dependencies.
2. **Orphaned / Overfilled ShadowStorage (`0x8004231f`):** Check if `MaxSpace` for shadow storage is capped too low (e.g., 300 MB) or consuming an entire volume because previous snapshots were never purged.
3. **System Volume Information / IIS / CBS / WinSxS Bloat:** Check `C:\inetpub\logs\LogFiles`, `C:\Windows\Logs\CBS`, `C:\Windows\Temp`, and `C:\ProgramData` vendor logs before assuming OS partition expansion is required.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Free safe temporary/log overhead first (never delete unverified databases, `.vhdx` files, or `System Volume Information` manually!). Examples: prune archived IIS logs older than 30 days or run `DISM /Online /Cleanup-Image /StartComponentCleanup`.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Adjust VSS shadow storage maximum allocation (ensure target volume has >= 15% free space):
   ```cmd
   vssadmin resize shadowstorage /for=C: /on=C: /maxsize=15%
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Restart failing VSS services to recover writers stuck in non-stable states (avoid rebooting a production server mid-day unless approved):
   ```powershell
   Restart-Service -Name "CryptSvc", "VSS", "swprv" -Force
   ```
   *(If `System Writer` remains missing/failed and a maintenance window is required, schedule a clean server reboot.)*

## Verification & Post-Fix Checks
1. Confirm `vssadmin list writers` shows **`State: [1] Stable`** and **`Last error: No error`** for every writer.
2. Confirm critical disk volumes have healthy free capacity and re-run an on-demand incremental backup job to verify green completion.

## Cross-Subject Escalation & Pivot Links
- **Windows Update WinSxS/CBS cache exhausted C: drive on Windows Server:** [win-001 — Windows Update Failure and Component Store Corruption](../03_Windows_Endpoints/win-001-windows-update-corruption.md)
- **Unbacked-up SQL Server Transaction Log (.ldf) or old .bak dumps filled data volume:** [srv-016 — SQL Server Login Failed (18456), Transaction Log Full (9002) & Deadlocks](./srv-016-sql-server-login-18456-log-full-9002-and-blocking.md)
- **Disk full occurs on an Azure Windows VM causing boot or agent failure:** [srv-013 — Azure VM Boot Failures, RDP/SSH Unreachable, NSG & Serial Console Triage](./srv-013-azure-vm-boot-rdp-ssh-and-serial-console.md)

## Client Update Snippets (EN / FR)
- **EN:** We reclaimed disk space on `SRV-FILE-01`, stabilized the Windows VSS backup writers, and verified that the backup job now completes cleanly.
- **FR:** Nous avons libéré de l'espace disque sur `SRV-FILE-01`, stabilisé les rédacteurs VSS Windows et validé que la tâche de sauvegarde s'exécute maintenant sans erreur.
