---
id: win-005
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: updates_win11_licensing
title: Intune Windows 10 to Windows 11 Migration, Feature Updates, and Safeguard Holds
tier: L2
keywords_en:
  - intune windows 11 upgrade
  - windows 11 migration failed
  - feature update stuck intune
  - safeguard hold windows 11
  - mbr2gpt uefi conversion
keywords_fr:
  - migration windows 11 intune
  - mise a niveau windows 11 echouee
  - mise a jour des fonctionnalites bloquee
  - blocage compatibilite windows 11
  - convertir mbr en gpt uefi
error_codes:
  - "0xC1900101"
  - "0xC1900200"
  - "0xC1900208"
  - "0x8007001F"
  - "0x800F0922"
  - "0x8024001E"
tags:
  - intune_win11_migration
  - win11_upgrade_hold
os:
  - windows
environment:
  - intune
  - entra_id
  - hybrid_ad
  - local_endpoint
tools:
  - Intune Admin Center
  - PowerShell
  - SetupDiag
  - mbr2gpt
  - Registry Editor
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - mdm-008
  - win-001
  - win-002
  - win-008
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is Windows 11 upgrade failing with a specific error (`0xC1900101`, `0xC1900200`, `0xC1900208` Safeguard Hold, `0x8007001F`, `0x800F0922`), OR is it simply **never offered** under Windows Update / Intune?
2. Is `PC-LAB-01` plugged into **AC power**, staying awake long enough during lunch/evening, and showing at least **25–30 GB free space on `C:`** (`[win-011]`)?
3. How old is the hardware (approx. pre-2018 Intel 7th Gen or older CPUs fail Windows 11 CPU/TPM 2.0 checks!), and is **BitLocker key escrowed (`[win-002]`)**?

### Initial Scope & Classification
- Check **Intune Admin Center -> Reports -> Windows updates -> Windows 11 readiness report** (`Capable`, `Not capable`, or `Safeguard Hold`) and confirm `Update Ring` vs `Feature Update` deferrals don't conflict.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Intune Portal & Endpoint GUI)
1. **Check Intune Readiness Report & PC Health Check:** Look up `PC-LAB-01` in Intune Windows 11 Readiness Report (or run **Windows PC Health Check app** on `PC-LAB-01`!) to spot red `TPM 2.0`, `Secure Boot`, `Free Disk Space (< 64 GB / 25 GB)`, or `Unsupported CPU` immediately!
2. **Check `C:` Free Disk Space & Connected Peripherals:** Ensure >= 30 GB free on `C:` and unplug extra USB drives/SD cards that often trigger `0xC1900101` setup rollbacks!

### L2 Technical Diagnostics
1. **Verify Windows 11 Hardware Readiness on `PC-LAB-01` (read-only, elevated):**
   ```powershell
   $tpm = Get-Tpm
   $partStyle = (Get-Disk | Where-Object IsBoot).PartitionStyle
   $freeGB = [math]::Round((Get-PSDrive C).Free / 1GB, 2)
   [PSCustomObject]@{
       CPU           = (Get-CimInstance Win32_Processor).Name
       RAM_GB        = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
       Free_C_GB     = $freeGB
       BootDiskStyle = $partStyle
       SecureBoot    = (Confirm-SecureBootUEFI)
       TpmReady      = $tpm.TpmReady
       TpmSpec       = (Get-CimInstance -Namespace root\cimv2\security\microsofttpm -ClassName Win32_Tpm).SpecVersion
   }
   ```
   *(Requirement: `BootDiskStyle = GPT`, `SecureBoot = True`, `TpmSpec >= 2.0`, `Free_C_GB >= 25`, `RAM >= 4 GB`.)*
2. **Validate Legacy MBR -> GPT Readiness without Modifying Disk (`mbr2gpt /validate`):**
   ```cmd
   mbr2gpt /validate /allowFullOS
   ```
3. **Inspect Windows 11 Upgrade Failure Logs & Telemetry Policies (read-only):**
   - Check `C:\$WINDOWS.~BT\Sources\Panther\setuperr.log` and `C:\$WINDOWS.~BT\Sources\Rollback\setupact.log` (or run Microsoft **SetupDiag**).
   - Verify **Telemetry (`AllowTelemetry`)** is at least **Basic (1)** / **Required** — Intune Feature Update policies require Windows diagnostic telemetry and the **Connected User Experiences and Telemetry (`DiagTrack`)** service!
     ```powershell
     Get-Service DiagTrack, wuauserv | Select-Object Name, Status, StartType
     Get-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" -ErrorAction SilentlyContinue | Select-Object AllowTelemetry
     Get-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate" -ErrorAction SilentlyContinue | Select-Object TargetReleaseVersion, TargetReleaseVersionInfo, ProductVersion
     ```

## Deep-Dive Investigation (L3)
1. **Conflicting `TargetReleaseVersion` GPO / Registry (`0x8024001E`):** Hybrid-joined endpoints often retain an on-prem GPO pinning `TargetReleaseVersionInfo = 22H2` (`Windows 10`), overriding Intune's Feature Update to Windows 11!
2. **Driver Rollback (`0xC1900101` / `0x8007001F`):** Run `SetupDiag.exe` on `PC-LAB-01` to extract the exact blocking `.sys` driver (common culprits: outdated Conexant/Realtek audio, Intel RST, older VPN clients, or third-party encryption drivers).
3. **Safeguard Hold (`0xC1900208`):** Inspect `HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\TargetVersionUpgradeExperienceIndicators\NI23H2` (`GStatus` / `RedReason` / `SdbVer`) or Intune **Windows Update for Business reports** (`SafeguardHoldId`) to identify the exact blocked app/driver rather than bypassing safeguards blindly!
4. **Full EFI System Partition (`0x800F0922`):** HP/Dell factory 100 MB EFI partitions filled with BIOS capsule/font files fail during Win11 setup until unused OEM font files or stale firmware binaries are cleaned safely.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `PC-LAB-01` boots Legacy BIOS + MBR (`mbr2gpt /validate /allowFullOS` passed!) and BitLocker is active: suspend BitLocker first (`[win-002]`), convert MBR to GPT cleanly, then switch BIOS to **UEFI + Secure Boot + TPM 2.0** on reboot:
   ```powershell
   Suspend-BitLocker -MountPoint "C:" -RebootCount 2
   ```
   ```cmd
   mbr2gpt /convert /allowFullOS
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Update OEM BIOS/drivers (Dell Command Update / Lenovo Vantage / HP Image Assistant) and any flagged security/VPN agent causing `0xC1900101` / `0xC1900208` safeguard holds.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Remove conflicting on-prem WSUS / `TargetReleaseVersion` GPOs, ensure Intune **Update Ring** sets `Feature update deferral period = 0`, and assign the targeted **Feature updates for Windows 10 and later** policy (`Windows 11, version 23H2/24H2`) to the device security group.
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Ensure `DiagTrack` service is enabled and running and `C:` has >= 30 GB free space (`[win-001]`), then trigger an Intune policy sync.

## Verification & Post-Fix Checks
1. Confirm `winver` / `(Get-ComputerInfo).OsName` on `PC-LAB-01` reports **Windows 11** at the target feature release and `Get-BitLockerVolume C:` is `On`.
2. Confirm **Intune Admin Center -> Devices -> `PC-LAB-01`** reports the updated OS build and **Compliant** status.

## Cross-Subject Escalation & Pivot Links
- **Endpoint has incomplete Intune MDM enrollment or Autopilot state:** [mdm-008 — Intune New Device Enrollment, Windows Autopilot OOBE, and ESP Failures](../07_macOS_Mobile_MDM/mdm-008-intune-new-device-enrollment-and-autopilot.md)
- **Corrupted SoftwareDistribution or CBS component store stalls Feature Update:** [win-001 — Windows Update Failure and Component Store Corruption](./win-001-windows-update-corruption.md)
- **TPM 2.0 / BitLocker / Secure Boot state triggers Windows 11 safeguard hold:** [win-002 — BitLocker Recovery Key Prompt After Update and TPM Lockout Triage](./win-002-bitlocker-recovery-screen-and-tpm.md)
- **OS edition upgrade drops or blocks Windows Subscription/KMS activation:** [win-008 — Windows Activation, KMS/ADBA, and Entra Subscription Licensing Errors](./win-008-windows-activation-and-licensing-errors.md)

## Useful Links & External Tools
- **[Windows 11 Supported Processors & Hardware Specs](https://learn.microsoft.com/en-us/windows-hardware/design/minimum/windows-processor-requirements)** — Verify whether older Windows 10 Intel/AMD CPUs are officially supported before targeting Intune Feature Updates.
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Review Windows 11 Readiness reports, Safeguard Hold IDs, and Update Ring deferrals.
- **[M365 Maps (Microsoft Licensing Matrix)](https://m365maps.com/)** — Confirm client licensing entitlements for Intune & Windows 11 Enterprise upgrades.

## Client Update Snippets (EN / FR)
- **EN:** We verified Windows 11 hardware compatibility, cleared the upgrade blocker on `PC-LAB-01`, and queued the Intune Windows 11 feature update. Please keep your workstation plugged into AC power and allow the scheduled reboot to complete the migration.
- **FR:** Nous avons validé la compatibilité matérielle Windows 11, levé le blocage sur `PC-LAB-01` et relancé la mise à niveau Intune. Veuillez laisser le poste branché sur secteur et autoriser le redémarrage prévu pour finaliser la migration vers Windows 11.
