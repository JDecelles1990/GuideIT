---
id: win-003
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: boot_bitlocker_bsod
title: Windows BSOD Crash Dump Analysis, Unexpected Reboot (Event 41), and Driver Triage
tier: L3
keywords_en:
  - blue screen
  - bsod
  - pc keeps rebooting
  - kernel power 41
  - windows crash dump
keywords_fr:
  - ecran bleu
  - plantage windows ecran bleu
  - redemarrage inattendu
  - ecran bleu bsod
  - crash windows pilote
error_codes:
  - "41"
  - "1001"
  - CRITICAL_PROCESS_DIED
  - DRIVER_IRQL_NOT_LESS_OR_EQUAL
tags:
  - bsod_crash
  - minidump_analysis
os:
  - windows
environment:
  - local_endpoint
  - hybrid_ad
tools:
  - Event Viewer
  - Reliability Monitor
  - PowerShell
  - WinDbg
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - win-006
  - prt-003
  - win-001
---

## Fast Triage (Under 2 Minutes)
- Capture the exact stop code (`CRITICAL_PROCESS_DIED`, `DRIVER_IRQL_NOT_LESS_OR_EQUAL`, `WHEA_UNCORRECTABLE_ERROR`) and any `.sys` driver filename shown on the blue screen on `PC-LAB-01`.
- Did the BSOD begin right after installing a Windows Update, dock/GPU/Wi-Fi driver, VPN/EDR agent update, or hardware/RAM change?
- Can `PC-LAB-01` still boot into Windows normally, or is it stuck in a boot loop requiring **WinRE / Safe Mode**?

## Read-Only Diagnostics (L1-L2)
1. **Check System Event Log for BugCheck (`Event ID 1001`) and Unexpected Shutdown (`Event ID 41`) plus Minidump files (read-only):**
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 41, 1001; StartTime = (Get-Date).AddDays(-7) } -MaxEvents 15 |
       Select-Object TimeCreated, Id, ProviderName, Message | Format-List
   Get-ChildItem "$env:SystemRoot\Minidump" -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object Name, Length, LastWriteTime
   ```
2. **Inspect Reliability Monitor & Recent Driver/Update Installs:**
   - Launch `perfmon /rel` to view critical crashes correlated with exact update or driver install timestamps.
   - List recently installed drivers / PnP problem devices (read-only):
     ```powershell
     Get-CimInstance Win32_PnPSignedDriver |
         Where-Object { $_.DriverDate -and $_.DriverDate -gt (Get-Date).AddDays(-30) } |
         Select-Object DeviceName, DriverVersion, DriverDate, Manufacturer | Format-Table -AutoSize
     ```

## Deep-Dive Investigation (L3)
1. **Analyze Minidump (`C:\Windows\Minidump\*.dmp`) in WinDbg:**
   - Open the newest `.dmp` in **WinDbg** (`windbgx`) and run `!analyze -v` to isolate `BUGCHECK_STR`, `MODULE_NAME`, and `IMAGE_NAME` (e.g., `igdkmdn64.sys`, `rtwlane.sys`, `ntfs.sys`, or EDR kernel filter).
2. **Hardware vs. Software Isolation:**
   - **`WHEA_UNCORRECTABLE_ERROR` (`0x124`):** Strong hardware signal (NVMe SSD thermal/controller fault, RAM, CPU voltage). Check SSD SMART status (`Get-PhysicalDisk | Get-StorageReliabilityCounter`) and run manufacturer UEFI diagnostics + `mdsched.exe`.
   - **`CRITICAL_PROCESS_DIED` / Boot Loop:** Check disk corruption (`chkdsk C: /scan`) and component store integrity (`[win-001]`).
3. **Kernel Power 41 Without `Event ID 1001` BugCheck:** Indicates sudden power loss, faulty battery/AC adapter, overheating shutdown, or dock power delivery drop rather than a Windows kernel BSOD.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If a specific newly updated driver (`.sys`) caused the BSOD, roll back or update via vendor official package (Intel/Dell/Lenovo/HP Command Update) or **Device Manager -> Properties -> Driver -> Roll Back Driver**.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `PC-LAB-01` cannot boot into Windows normally, boot into **WinRE -> Troubleshoot -> Advanced options -> Startup Settings -> Safe Mode (4)** (or uninstall latest faulty Quality Update from WinRE) and confirm BitLocker recovery key readiness (`[win-002]`) first!
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Repair Windows OS files after isolating driver/storage health (`[win-001]`):
   ```cmd
   DISM /Online /Cleanup-Image /RestoreHealth
   sfc /scannow
   ```

## Verification & Post-Fix Checks
1. Confirm `perfmon /rel` and `Event ID 41 / 1001` show zero new crashes across 48 hours of normal workload (including sleep/wake and dock attach/detach).
2. Verify `Get-PhysicalDisk` reports `HealthStatus = Healthy` and all devices in Device Manager show clean status.

## Cross-Subject Escalation & Pivot Links
- **Thermal throttling, memory exhaustion (2004), or NVMe resets (129/153) precede BSOD:** [win-006 — Windows High CPU, 100% Disk Usage, and Memory Leak Triage (Event 129 / 153 / 2004)](./win-006-windows-high-cpu-100-disk-and-memory-leak.md)
- **USB-C / Thunderbolt dock firmware or DisplayLink driver triggers bugcheck:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](../05_Printers_Devices/prt-003-usbc-dock-monitors-not-detected.md)
- **Faulty cumulative driver/kernel update requires DISM health repair or KB uninstall:** [win-001 — Windows Update Failure and Component Store Corruption](./win-001-windows-update-corruption.md)

## Client Update Snippets (EN / FR)
- **EN:** We analyzed the Windows crash dump on `PC-LAB-01`, identified the faulting driver / system component, and applied the verified update and OS integrity check. Please monitor the workstation today and let us know immediately if any reboot or blue screen recurs.
- **FR:** Nous avons analysé le vidage mémoire du plantage sur `PC-LAB-01`, identifié le pilote / composant en cause et appliqué la mise à jour ainsi que la vérification système. Veuillez utiliser le poste aujourd'hui et nous aviser sans délai si un écran bleu réapparaît.
