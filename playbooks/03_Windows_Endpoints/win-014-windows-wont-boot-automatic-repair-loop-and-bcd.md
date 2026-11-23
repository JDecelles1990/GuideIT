---
id: win-014
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: boot_bitlocker_bsod
title: Windows Won't Boot Up, Automatic Repair Loop, No Bootable Device, and WinRE / BCD Recovery
tier: L2
keywords_en:
  - pc won't boot up
  - pc won't boot
  - windows won't boot
  - windows won't start
  - automatic repair loop
  - no bootable device found
  - inaccessible boot device
  - boot loop windows
keywords_fr:
  - pc ne demarre pas
  - windows ne demarre pas
  - boucle reparation automatique
  - aucun peripherique amorcable
  - windows ne veut plus demarrer
  - reparation automatique boucle infinie
error_codes:
  - 0xc000000f
  - 0xc000000e
  - 0xc0000225
  - INACCESSIBLE_BOOT_DEVICE
  - 3F0
  - NO_BOOTABLE_DEVICE
tags:
  - windows_wont_boot
  - automatic_repair_loop
  - bcd_winre_recovery
os:
  - windows
environment:
  - local_endpoint
  - hybrid_ad
  - intune
tools:
  - Windows Recovery Environment (WinRE)
  - BIOS / UEFI Setup
  - bcdedit / bcdboot
  - diskpart
  - PowerShell
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - win-002
  - win-003
  - win-001
  - win-012
  - win-013
  - mdm-008
linked_scripts:
  - 01_System/Get-SystemCrashHistory.ps1
  - 01_System/Get-HardwareInventory.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Does `PC-LAB-01` power on and show the **manufacturer logo (Dell / HP / Lenovo)** before failing, OR is the PC completely dead (`[win-012]`) / solid black with zero logo (`[win-013]`)?
2. What exact message or code appears on screen: **`Preparing Automatic Repair` / `"Your PC did not start correctly"` loop**, **`No Bootable Device / Boot Device Not Found (3F0)`**, **`INACCESSIBLE_BOOT_DEVICE`**, **`Recovery: 0xc000000f / 0xc0000225`**, or a blue **BitLocker recovery key screen** (`[win-002]`)?
3. Are any **USB flash drives, external hard drives, SD cards, or USB-C docks** plugged in right now, and did Windows or a BIOS update run yesterday?
4. Do you have **local files not synced to OneDrive** (Desktop/Documents/Downloads) that must be preserved before running any repair?

### Initial Scope & Classification
- Distinguish:
  1. **USB Boot Trap / External Media:** Laptop trying to boot off a plugged-in USB drive/dock!
  2. **BIOS Storage Mode / Firmware Change (`INACCESSIBLE_BOOT_DEVICE`):** `AHCI` vs `RAID On (Intel VMD)` flipped after BIOS update/CMOS reset.
  3. **Bad Update / Corrupt Boot Config (`0xc000000f` / Automatic Repair loop):** Recoverable cleanly from **WinRE** GUI or `bcdboot`.
  4. **Physically Missing or Failed SSD (`No Bootable Device / 3F0`):** Disk absent in BIOS or failing OEM Pre-Boot Hardware Diagnostics.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Safe Non-Destructive Checks Before WinRE CLI)
1. **Unplug ALL External USB Storage & Docks Immediately (Fixes ~20% of Cases!):**
   - Disconnect USB thumb drives, external HDDs, SD cards, phones, and USB-C docks (`[prt-003]`), keeping only OEM AC power, and reboot `PC-LAB-01`. Many BIOS boot orders stall or show `No Bootable Device` on non-bootable USB storage!
2. **Pull the 48-Digit BitLocker Recovery Key First (`[win-002]`):**
   - Before entering **WinRE Command Prompt** or opening **BIOS Setup**, look up `PC-LAB-01`'s **48-digit BitLocker Recovery Key** in **Entra ID -> Devices**, **Intune -> Devices**, or **ADUC** so you never get locked out of an encrypted OS partition!
3. **Inspect BIOS/UEFI Storage Detection & Controller Mode (Read-Only):**
   - Power on and tap **`F2`** (Dell/ASUS), **`F10`** (HP), **`F1` / `Enter`** (Lenovo), or **`Del`** to enter BIOS Setup:
     - Under **System Information / Storage**: verify the **M.2 NVMe / SATA SSD serial & capacity** appear (`None` or missing = unseated or failed SSD hardware!).
     - Under **Storage / SATA Operation**: note whether mode is **`RAID On` / `Intel VMD`** vs **`AHCI`** — if a BIOS update/battery drain reset BIOS defaults and flipped this setting, Windows throws `INACCESSIBLE_BOOT_DEVICE` on every boot!
     - Confirm **Boot Mode = `UEFI`** with **`Windows Boot Manager`** first in Boot Sequence.
4. **Run Built-In OEM Pre-Boot Hardware Diagnostics (Read-Only):**
   - Tap **`F12`** (Dell/Lenovo) or **`F2`** (HP) at startup -> launch **Diagnostics / System Diagnostics -> Quick Test (Storage + Memory)** to rule out a dying NVMe SSD before spending time on Windows BCD repair!

### L2 Technical Diagnostics (WinRE Command Prompt — Read-Only Inspection)
1. **Open Windows Recovery Environment (`WinRE`):**
   - On the `"Automatic Repair couldn't repair your PC"` screen, choose **Advanced options -> Troubleshoot -> Advanced options -> Command Prompt** (or interrupt Windows boot 3 consecutive times at the spinning circle to trigger WinRE).
   - If prompted for the BitLocker Recovery Key (`[win-002]`), enter the verified 48-digit key.
2. **Inspect Disk Partitions, Drive Letters, BitLocker State & `SrtTrail.txt` Boot Failure Log (read-only):**
   *(Note: Inside WinRE, the Windows OS volume is often assigned `D:` or `E:` temporarily — verify in `list vol` first!)*
   ```cmd
   diskpart
   list disk
   list vol
   exit
   manage-bde -status
   ```
   ```cmd
   :: Replace C: below with the actual OS drive letter containing \Windows shown in `list vol`
   bcdedit /enum all
   type C:\Windows\System32\LogFiles\Srt\SrtTrail.txt
   ```
   - Look at the **Root cause found** line at the bottom of `SrtTrail.txt` (often pinpoints exact bad driver `.sys`, missing boot file, or registry hive error!).

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm all USB/docks removed, exact screen text/code (`0xc000000f`, `3F0`, `INACCESSIBLE_BOOT_DEVICE`), BIOS SSD detection + `AHCI`/`RAID` setting, OEM Pre-Boot Storage Diagnostic pass/fail result, and escrowed BitLocker key verification.

## Deep-Dive Investigation (L3)
1. **UEFI EFI System Partition (`FAT32`, ~100–260 MB) vs Corrupted BCD (`0xc000000f` / `0xc0000225`):** Never run legacy BIOS `bootrec /fixmbr` on modern UEFI/GPT disks (`bootrec /fixboot` also often fails with `Access is denied` on Win10/11 UEFI); inspect the EFI partition layout (`FAT32`, `System`) and repair cleanly with **`bcdboot C:\Windows /s S: /f UEFI`**.
2. **Failed Patch Tuesday Pending Update Package:** When `SrtTrail.txt` points to a boot failure immediately after Windows Update (`[win-001]`), inspect `$WinRE` pending transactions and `C:\Windows\Logs\CBS\CBS.log`, then revert pending actions with offline `DISM`.
3. **NVMe Read-Only Media Failure / Corrupt Registry Hive:** If `diskpart -> list disk` shows `0 B` free/size, `No Media`, or OEM diagnostics fail SMART (`Short DST Failed`), stop all writes immediately, back up any recoverable user data over read-only/live USB if unencrypted or unlocked via BitLocker, and replace the SSD.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Verify the **48-digit BitLocker Recovery Key (`[win-002]`)** is recorded and check if critical local files are synced before resetting Windows or changing BIOS settings! Never execute legacy `bootrec /fixmbr` on UEFI/GPT disks or destructive `diskpart clean`!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 WinRE GUI Recovery — Zero CLI Needed)** From **Troubleshoot -> Advanced options**:
   - First run **Startup Repair** (automated fix of common EFI/BCD flags).
   - If the loop started right after Windows Updates, run **Uninstall Updates -> Uninstall latest quality update** (then **latest feature update** if needed).
   - Try **Startup Settings -> Restart -> Press `4` (Enable Safe Mode)** (if Safe Mode boots, uninstall the newest faulty app/driver or inspect `[win-003]` crash history!).
   - Run **System Restore** if a clean pre-issue restore point exists.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Restore BIOS Storage Controller Mode)** ONLY if `INACCESSIBLE_BOOT_DEVICE` began immediately after a BIOS update or CMOS reset, reboot into BIOS Setup, switch **SATA/NVMe Operation** back (`AHCI` <-> `RAID On / Intel VMD`) matching the factory configuration, save, and enter the escrowed BitLocker Recovery Key (`[win-002]`) if prompted once.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Offline Pending Update Revert & UEFI BCD Rebuild in WinRE CLI)** After backing up user data if needed and confirming the Windows volume (`C:`) and unlocking BitLocker if `Locked`:
   ```cmd
   :: Optional unlock if manage-bde -status shows Locked (use verified 48-digit key)
   manage-bde -unlock C: -RecoveryPassword 000000-000000-000000-000000-000000-000000-000000-000000

   :: Assign drive letter S: to the ~100-260 MB FAT32 System (EFI) volume identified in `list vol`
   diskpart
   select vol <EFI_VOLUME_NUMBER>
   assign letter=S
   exit

   :: Revert hung Windows Update transactions and rebuild UEFI boot files safely
   dism /Image:C:\ /Cleanup-Image /RevertPendingActions
   bcdboot C:\Windows /s S: /f UEFI
   sfc /scannow /offbootdir=C:\ /offwindir=C:\Windows
   ```
4. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Hardware SSD Replacement or Autopilot Reimage)** If OEM diagnostics report an SSD hardware failure (`3F0` / `DST Fail`), replace the SSD under warranty and provision cleanly via **Windows Autopilot / Intune (`[mdm-008]`)**. If hardware passes cleanly yet OS hives remain damaged, back up unsynced data from `C:\Users\<user>` cleanly and run **Reset this PC (Cloud download)** / fresh Autopilot wipe.

## Verification & Post-Fix Checks
1. Reboot `PC-LAB-01` completely and confirm Windows reaches the sign-in screen cleanly across two consecutive restarts without re-entering Automatic Repair.
2. Once signed into Windows, run **`psstore://01_System/Get-SystemCrashHistory.ps1`** and **`sfc /scannow`** / **`DISM /Online /Cleanup-Image /ScanHealth`** (`[win-001]`), and confirm OneDrive sync (`[m365-005]`) and BitLocker protection status (`[win-002]`) are healthy.

## Cross-Subject Escalation & Pivot Links
- **Booting pauses at blue BitLocker recovery password screen:** [win-002 — BitLocker Recovery Key Prompt After Update and TPM Lockout Triage](./win-002-bitlocker-recovery-screen-and-tpm.md)
- **Windows BSOD crashes mid-boot (`CRITICAL_PROCESS_DIED` / driver crashes):** [win-003 — Windows BSOD Crash Dump Analysis, Unexpected Reboot (Event 41), and Driver Triage](./win-003-bsod-crash-dump-and-driver-triage.md)
- **PC shows zero LEDs, zero fans, and zero power at all:** [win-012 — Dead PC, Won't Turn On, and No Power Hardware Triage (Desktop & Laptop)](./win-012-pc-wont-turn-on-dead-pc-no-power-triage.md)
- **PC powers on (fans/LEDs on) but stays pitch black with zero manufacturer logo:** [win-013 — PC Turns On With Black Screen, No Display, or Fails POST (Beep / LED Blink Codes)](./win-013-pc-power-on-black-screen-no-post-display-triage.md)
- **Fresh SSD replacement or OS reset requires Intune Autopilot enrollment:** [mdm-008 — Intune New Device Enrollment, Windows Autopilot OOBE, and ESP Failures](../07_macOS_Mobile_MDM/mdm-008-intune-new-device-enrollment-and-autopilot.md)

## Client Update Snippets (EN / FR)
- **EN:** We resolved the Windows startup / Automatic Repair failure on `PC-LAB-01` after isolating external USB storage, checking hardware drive diagnostics, and restoring the UEFI boot / update state cleanly. Could you sign in and confirm your desktop and synced OneDrive files load normally?
- **FR:** Nous avons résolu le blocage de démarrage / boucle de réparation automatique sur `PC-LAB-01` après avoir isolé les périphériques USB, vérifié l'état matériel du disque et restauré le démarrage UEFI / les mises à jour. Pouvez-vous ouvrir votre session et confirmer que votre bureau et vos fichiers OneDrive chargent normalement ?
