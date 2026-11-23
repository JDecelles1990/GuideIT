---
id: win-006
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: boot_bitlocker_bsod
title: Windows High CPU, 100% Disk Usage, and Memory Leak Triage (Event 129 / 153 / 2004)
tier: L2
keywords_en:
  - windows 100 disk usage
  - windows high cpu memory leak
  - pc extremely slow tiworker
  - event 129 storahci disk reset
  - resource exhaustion detector 2004
keywords_fr:
  - disque 100 pourcent windows
  - fuite memoire cpu eleve windows
  - pc tres lent processeur sature
  - erreur disque 129 153 windows
  - saturation memoire windows 2004
error_codes:
  - "129"
  - "153"
  - "2004"
tags:
  - windows_high_cpu_disk
  - windows_memory_leak
os:
  - windows
environment:
  - local_endpoint
  - hybrid_ad
tools:
  - Task Manager
  - Resource Monitor
  - PowerShell
  - Event Viewer
  - RAMMap
risk_level: medium
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - win-003
  - sec-002
  - win-001
linked_scripts:
  - 01_System/Get-HighResourceProcesses.ps1
  - 01_System/Get-DiskSpaceReport.ps1
  - 01_System/Get-RecentEventErrors.ps1
---

## Fast Triage (Under 2 Minutes)
- Open **Task Manager (`Ctrl + Shift + Esc`) -> Performance** tab on `PC-LAB-01` to see WHICH bottleneck is pegged at 95–100%: **CPU**, **Memory** (check **Committed** & **Non-paged pool**!), or **Disk 0 (`Active time` 100% with high Average response time >50 ms)**!
- Check **Uptime** in Task Manager -> Performance -> CPU: Windows **Fast Startup** prevents shutdowns from clearing kernel memory leaks — check if uptime is 20+ days!
- Confirm whether a scheduled Windows Update (`TiWorker.exe` / `TrustedInstaller`), Defender scan (`MsMpEng.exe`), or Teams/Chrome/Outlook bloat is active.

## Read-Only Diagnostics (L1-L2)
1. **Capture System Uptime, Top CPU/Memory Processes, and Disk Health (read-only):**
   ```powershell
   (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | Select-Object Days, Hours, Minutes
   Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 ProcessName, Id, CPU, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}}
   Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 ProcessName, Id, @{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}}
   Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus
   ```
2. **Check `System` Event Log for Storage Reset/Retry (`Event ID 129`, `153`) & Memory Exhaustion (`Event ID 2004`, read-only):**
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 129, 153, 2004; StartTime = (Get-Date).AddDays(-5) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, ProviderName, Message
   ```
   *(Repeated **`129`**/`153` on SSD/NVMe points to failing SSD, stale Intel RST/NVMe driver, or PCIe/AHCI Link Power Management (`LPM`) stalls!)*
3. **Sample Live Disk Queue & CPU Counters (read-only):**
   ```powershell
   Get-Counter '\LogicalDisk(C:)\% Disk Time', '\LogicalDisk(C:)\Avg. Disk Queue Length', '\Memory\Pool Nonpaged Bytes'
   ```

## Deep-Dive Investigation (L3)
1. **Kernel Driver Memory Leak (`Pool Nonpaged Bytes > 1–2 GB`):** Run **Sysinternals `poolmon` / `RAMMap`** when Task Manager RAM is at 98% yet process `WorkingSet` sums look small — common culprits are old network/VPN/printer filter drivers (`ndis`, `rdbss`, or third-party security agents).
2. **`WmiPrvSE.exe` or `SearchIndexer.exe` Loop:** Inspect `Microsoft-Windows-WMI-Activity/Operational` for looping RMM/monitoring WMI queries (`Event ID 5858`), or rebuild a corrupted Windows Search index (`Control Panel -> Indexing Options -> Advanced -> Rebuild`).
3. **Power Plan / Thermal Throttling:** Verify CPU isn't locked at `0.40 GHz` / `0.79 GHz` due to an under-wattage USB-C charger (`[prt-003]`), swollen battery, or stuck `BD PROCHOT` thermal flag.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Perform a real **Restart** (`Start -> Power -> Restart`, NOT Shut down which uses Fast Startup hibernation) to clear high uptime and kernel leaks after saving open user work.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **Event ID 129 / 153** occurs on healthy NVMe/SATA SSD: update OEM **SSD Firmware + Storage/Chipset Driver** and check **Power Options -> PCI Express -> Link State Power Management** (`Off` when plugged in). If `Get-PhysicalDisk` shows `Warning` / `Unhealthy`, back up user data immediately (`[m365-005]`) and replace the drive!
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Close/disable unnecessary Startup Apps (**Task Manager -> Startup apps**), apply pending browser/Office updates, and schedule heavy Defender scans outside peak work hours.

## Verification & Post-Fix Checks
1. Confirm Task Manager shows CPU idle `< 15%`, Disk active time `< 10%` (`Avg. response time < 5 ms`), and Memory utilization healthy after reboot.
2. Confirm `System` Event Log records zero new `Event ID 129 / 153 / 2004` warnings under workload.

## Cross-Subject Escalation & Pivot Links
- **Repeated disk timeouts (129/153) or pool exhaustion escalate to BSOD bugcheck:** [win-003 — Windows BSOD Crash Dump Analysis, Unexpected Reboot (Event 41), and Driver Triage](./win-003-bsod-crash-dump-and-driver-triage.md)
- **Microsoft Defender real-time AV/ASR scanning pins CPU/disk on LOB databases:** [sec-002 — Microsoft Defender ASR Rule or Antivirus Blocking Legitimate LOB App or Macro](../06_Security_Access/sec-002-defender-asr-block-and-false-positive.md)
- **Stuck TrustedInstaller (TiWorker.exe) update cycle saturates CPU and disk I/O:** [win-001 — Windows Update Failure and Component Store Corruption](./win-001-windows-update-corruption.md)

## Client Update Snippets (EN / FR)
- **EN:** We traced the high CPU / disk / memory bottleneck on `PC-LAB-01`, cleaned up the runaway startup/driver workload, and verified responsive system performance after a clean reboot. Could you test your applications now and confirm the slowdown is resolved?
- **FR:** Nous avons identifié la cause de la saturation processeur / disque / mémoire sur `PC-LAB-01`, corrigé le processus / pilote en cause et vérifié la fluidité après un redémarrage complet. Pouvez-vous tester vos logiciels et confirmer que la lenteur est réglée ?
