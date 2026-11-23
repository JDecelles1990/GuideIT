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
  - 07_Servers_Infra/Get-VSSWriterHealth.ps1
  - 01_System/Get-DiskSpaceReport.ps1
  - 07_Servers_Infra/Get-ServerAutoServices.ps1
  - 01_System/Invoke-DeepSystemCleanup.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Did an **automated backup job (`Veeam` / `Windows Server Backup` / cloud agent) fail**, or is a user reporting **"Disk full" / frozen apps on the server (`SRV-FILE-01`)**?
2. Which specific drive letter is full (`C:` OS volume vs `D:` data/SQL volume)?
3. Are users currently still able to open files and save work normally, or have services/databases already stopped?
4. Has the server been rebooted recently, or were large ISOs/backups saved manually onto `C:`?

### Initial Scope & Classification
- Is a critical production volume (`C:` or `D:`) below 5% free space on `SRV-FILE-01`, causing service stalls or backup failure?
- Check the backup job log for exact VSS codes (`0x80042306` = shadow copy provider error; `0x8004231f` = insufficient storage for shadow copy; Event ID `8193` / `12289`).
- Confirm whether `SRV-FILE-01` is a VM (Hyper-V/VMware/Azure) with unmerged snapshots/checkpoints consuming datastore space.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Check Drive Free Space Visually (`File Explorer -> This PC` or RMM Dashboard):** Record exact `GB free / Total GB` on `C:`, `D:`, and any backup destination drives! (Remember `< 10%` free often triggers backup VSS `0x8004231f` failures even before `0 MB`!)
2. **Check Obvious Safe Clutter (Read-Only Glance):** Look in **`Recycle Bin`**, **`C:\Users\<admin>\Downloads`** (old installers/ISOs), and **`C:\Windows\Temp`** — **NEVER** delete anything under `C:\inetpub`, database folders, or `System Volume Information` without checking first!
3. **Check Windows Backup & VSS Services (`services.msc` GUI):** Confirm **`Volume Shadow Copy` (`VSS`)**, **`Cryptographic Services` (`CryptSvc`)**, and the backup agent service (`Veeam Installer Service` / `Datto`) aren't stuck in `Stopping` or `Stopped`.
4. **Capture Backup Console Error Code:** Screenshot the failed backup alert (`0x80042306`, `0x8004231f`, `Failed to freeze VSS writer`) for L2/L3 notes.

### L2 Technical Diagnostics
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

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact drive letters + `FreeGB` remaining, top 5 largest folders on the full volume, exact backup console error text, and `vssadmin list writers` screenshot showing any non-Stable writer.

## Deep-Dive Investigation (L3)
1. **Stuck VSS Writers (`Retryable Error` / `Waiting for completion`):** Identify which specific writer (`System Writer`, `SqlServerWriter`, `NTDS`, `Hyper-V VSS Writer`) failed and examine `COM+ Event System`, `Volume Shadow Copy`, and `Microsoft Software Shadow Copy Provider` service dependencies.
2. **Orphaned / Overfilled ShadowStorage (`0x8004231f`):** Check if `MaxSpace` for shadow storage is capped too low (e.g., 300 MB) or consuming an entire volume because previous snapshots were never purged.
3. **System Volume Information / IIS / CBS / WinSxS Bloat:** Check `C:\inetpub\logs\LogFiles`, `C:\Windows\Logs\CBS`, `C:\Windows\Temp`, and `C:\ProgramData` vendor logs before assuming OS partition expansion is required.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Safe Obvious Space Recovery)** Free safe temporary/log overhead first ONLY with approval (never delete unverified databases, `.vhdx` files, or `System Volume Information` manually!): empty server Recycle Bin if confirmed unneeded, remove verified old downloaded `.iso`/installer files, prune archived IIS logs older than 30 days, or run `DISM /Online /Cleanup-Image /StartComponentCleanup`.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Restart Stuck VSS Services)** Restart failing VSS services cleanly to recover writers stuck in non-stable states (avoid rebooting a production server mid-day unless approved):
   ```powershell
   Restart-Service -Name "CryptSvc", "VSS", "swprv" -Force
   ```
   *(If `System Writer` remains missing/failed and a maintenance window is required, schedule a clean server reboot.)*
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L3 Adjust VSS ShadowStorage Allocation)** Ensure target volume has >= 15% free space before resizing shadow storage:
   ```cmd
   vssadmin resize shadowstorage /for=C: /on=C: /maxsize=15%
   ```

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
