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
  - win-014
linked_scripts:
  - 01_System/Get-SystemCrashHistory.ps1
  - 04_Devices/Get-DeviceDrivers.ps1
  - 04_Devices/Get-ProblemDevices.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Can you **still log into Windows normally** right now, or is `PC-LAB-01` stuck in a boot loop / BitLocker screen (`[win-002]`)?
2. What exact **Stop Code** appeared on the blue screen (`CRITICAL_PROCESS_DIED`, `DRIVER_IRQL_NOT_LESS_OR_EQUAL`, `WHEA_UNCORRECTABLE_ERROR`) and did it mention a `.sys` file? *(Ask user to snap a quick phone photo!)*
3. What were you doing right when it crashed (plugging in a **USB-C dock / external monitor**, joining a **Teams video call**, waking from sleep, or installing **Windows Updates**)?
4. Is the laptop running unusually **hot / loud fans** or showing battery issues (`[win-009]`)?

### Initial Scope & Classification
- Capture the exact stop code + trigger timing: you do **NOT** need WinDbg at L1 to solve 70% of BSODs caused by overheating vents, loose USB-C docks (`[prt-003]`), pending Windows Updates/OEM drivers, or full `C:` drives (`[win-011]`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Unplug External Docks / USB Devices to Isolate Hardware Peripherals:** Disconnect non-essential USB hubs, USB-C docks, and extra monitors briefly (`[prt-003]`). If crashes stop, the dock firmware or USB/DisplayLink driver is the prime suspect!
2. **Open Reliability Monitor (Easiest Visual Crash Timeline — No CLI!):**
   - Press `Win + R` -> type **`perfmon /rel`** -> click any red **`X` (`Windows was not properly shut down` / `Shut down unexpectedly`)** -> click **View technical details**! Look at **Windows Updates** or **Driver installations** shown on the same day!
3. **Inspect OEM Health & Thermal State:** Check laptop air vents for blockage/heat, run quick hardware test if **Dell SupportAssist / Lenovo Vantage / HP Diagnostics** is installed, and verify `C:` drive has >= 15 GB free.
4. **Verify BitLocker Recovery Key BEFORE Any BIOS/Driver Fix (`[win-002]`):** Confirm `PC-LAB-01`'s 48-digit BitLocker Recovery Key is safely escrowed in Entra/Intune/AD before scheduling BIOS/firmware updates!

### L2 Technical Diagnostics
1. **Check System Event Log for BugCheck (`Event ID 1001`) and Unexpected Shutdown (`Event ID 41`) plus Minidump files (read-only):**
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 41, 1001; StartTime = (Get-Date).AddDays(-7) } -MaxEvents 15 |
       Select-Object TimeCreated, Id, ProviderName, Message | Format-List
   Get-ChildItem "$env:SystemRoot\Minidump" -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object Name, Length, LastWriteTime
   ```
2. **List Recently Installed Drivers / PnP Problem Devices & Disk SMART State (read-only):**
   ```powershell
   Get-CimInstance Win32_PnPSignedDriver |
       Where-Object { $_.DriverDate -and $_.DriverDate -gt (Get-Date).AddDays(-30) } |
       Select-Object DeviceName, DriverVersion, DriverDate, Manufacturer | Format-Table -AutoSize
   Get-PhysicalDisk | Select-Object FriendlyName, MediaType, HealthStatus, OperationalStatus
   ```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Phone photo / Stop Code text, **`perfmon /rel`** technical details screenshot, whether it happens docked vs undocked, and zipped `C:\Windows\Minidump\*.dmp` path (do NOT upload memory dumps containing RAM secrets to public websites!).

## Deep-Dive Investigation (L3)
1. **Analyze Minidump (`C:\Windows\Minidump\*.dmp`) in WinDbg:**
   - Open the newest `.dmp` in **WinDbg** (`windbgx`) and run `!analyze -v` to isolate `BUGCHECK_STR`, `MODULE_NAME`, and `IMAGE_NAME` (e.g., `igdkmdn64.sys`, `rtwlane.sys`, `ntfs.sys`, or EDR kernel filter).
2. **Hardware vs. Software Isolation:**
   - **`WHEA_UNCORRECTABLE_ERROR` (`0x124`):** Strong hardware signal (NVMe SSD thermal/controller fault, RAM, CPU voltage). Check SSD SMART status (`Get-PhysicalDisk | Get-StorageReliabilityCounter`) and run manufacturer UEFI diagnostics + `mdsched.exe`.
   - **`CRITICAL_PROCESS_DIED` / Boot Loop:** Check disk corruption (`chkdsk C: /scan`) and component store integrity (`[win-001]`).
3. **Kernel Power 41 Without `Event ID 1001` BugCheck:** Indicates sudden power loss, faulty battery/AC adapter, overheating shutdown, or dock power delivery drop rather than a Windows kernel BSOD.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Driver / Peripheral Update or Rollback)** If crashes happen strictly with a dock/peripheral or right after an OEM update, apply pending verified **Dell Command Update / Lenovo Vantage / HP Image Assistant** BIOS & Dock/Video drivers (verify BitLocker key escrowed first -> `[win-002]`), OR roll back the single recently updated driver in **Device Manager -> Properties -> Driver -> Roll Back Driver**.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Safe Mode Boot & Faulty KB Uninstall)** If `PC-LAB-01` cannot boot into Windows normally, boot into **WinRE -> Troubleshoot -> Advanced options -> Startup Settings -> Safe Mode (4)** (or uninstall latest faulty Quality Update from WinRE) and confirm BitLocker recovery key readiness (`[win-002]`) first!
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 OS Component Integrity Repair)** Repair Windows OS files after isolating driver/storage health (`[win-001]`):
   ```cmd
   DISM /Online /Cleanup-Image /RestoreHealth
   sfc /scannow
   ```

## Verification & Post-Fix Checks
1. Confirm `perfmon /rel` and `Event ID 41 / 1001` show zero new crashes across 48 hours of normal workload (including sleep/wake and dock attach/detach).
2. Verify `Get-PhysicalDisk` reports `HealthStatus = Healthy` and all devices in Device Manager show clean status.

## Cross-Subject Escalation & Pivot Links
- **BSOD causes a boot loop (`INACCESSIBLE_BOOT_DEVICE` / Automatic Repair) that won't reach Windows:** [win-014 — Windows Won't Boot Up, Automatic Repair Loop, No Bootable Device, and WinRE / BCD Recovery](./win-014-windows-wont-boot-automatic-repair-loop-and-bcd.md)
- **Thermal throttling, memory exhaustion (2004), or NVMe resets (129/153) precede BSOD:** [win-006 — Windows High CPU, 100% Disk Usage, and Memory Leak Triage (Event 129 / 153 / 2004)](./win-006-windows-high-cpu-100-disk-and-memory-leak.md)
- **USB-C / Thunderbolt dock firmware or DisplayLink driver triggers bugcheck:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](../05_Printers_Devices/prt-003-usbc-dock-monitors-not-detected.md)
- **Faulty cumulative driver/kernel update requires DISM health repair or KB uninstall:** [win-001 — Windows Update Failure and Component Store Corruption](./win-001-windows-update-corruption.md)


## Useful Links & External Tools
- **[Windows Release Health & Known Issues](https://learn.microsoft.com/en-us/windows/release-health/)** — Check whether a recent Windows cumulative update triggered known BSOD stop codes.
## Client Update Snippets (EN / FR)
- **EN:** We analyzed the Windows crash dump on `PC-LAB-01`, identified the faulting driver / system component, and applied the verified update and OS integrity check. Please monitor the workstation today and let us know immediately if any reboot or blue screen recurs.
- **FR:** Nous avons analysé le vidage mémoire du plantage sur `PC-LAB-01`, identifié le pilote / composant en cause et appliqué la mise à jour ainsi que la vérification système. Veuillez utiliser le poste aujourd'hui et nous aviser sans délai si un écran bleu réapparaît.
