---
id: win-002
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: boot_bitlocker_bsod
title: BitLocker Recovery Key Prompt After Update and TPM Lockout Triage
tier: L2
keywords_en:
  - bitlocker recovery screen
  - asking for bitlocker key
  - bitlocker recovery prompt
  - tpm lockout windows
  - bitlocker after bios update
keywords_fr:
  - ecran bleu bitlocker
  - cle de recuperation bitlocker
  - bitlocker demande cle au demarrage
  - verrouillage tpm bitlocker
  - recuperation bitlocker apres mise a jour
error_codes:
  - "0x80310000"
  - TPM_LOCKOUT
tags:
  - bitlocker_recovery
  - tpm_lockout
os:
  - windows
environment:
  - intune
  - entra_id
  - hybrid_ad
  - local_endpoint
tools:
  - Intune Admin Center
  - Entra Admin Center
  - Active Directory
  - PowerShell
  - manage-bde
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - mdm-001
  - win-001
  - win-005
---

## Fast Triage (Under 2 Minutes)
- Read the exact **Recovery Key ID (first 8 characters)** displayed on the blue BitLocker Recovery screen on `PC-LAB-01` (do NOT confuse the Key ID with the 48-digit Recovery Key!).
- Confirm whether a **BIOS/UEFI firmware update**, **docking station**, **USB boot drive**, or **Secure Boot setting change** happened right before the reboot.
- Verify the caller's identity out-of-band before reading out any 48-digit BitLocker recovery password!

## Read-Only Diagnostics (L1-L2)
1. **Locate the 48-digit BitLocker Recovery Key by matching Key ID:**
   - **Entra ID / Intune:** Open **Entra Admin Center -> Devices -> All devices -> `PC-LAB-01` -> BitLocker keys** (or **Intune Admin Center -> Devices -> `PC-LAB-01` -> Recovery keys**).
   - **On-Prem Active Directory:** Open **ADUC -> `PC-LAB-01` Properties -> BitLocker Recovery** tab, or query via PowerShell:
     ```powershell
     Get-ADObject -Filter "objectClass -eq 'msFVE-RecoveryInformation'" -SearchBase (Get-ADComputer "PC-LAB-01").DistinguishedName -Properties "msFVE-RecoveryPassword", "whenCreated" |
         Select-Object Name, whenCreated, "msFVE-RecoveryPassword"
     ```
2. **Once booted into Windows on `PC-LAB-01`, inspect BitLocker & TPM health (read-only, elevated):**
   ```powershell
   Get-BitLockerVolume -MountPoint "C:" | Select-Object MountPoint, ProtectionStatus, LockStatus, EncryptionPercentage, KeyProtector
   Get-Tpm | Select-Object TpmPresent, TpmReady, TpmEnabled, TpmActivated, LockoutCount, LockoutMax
   ```
   ```cmd
   manage-bde -protectors -get C:
   ```

## Deep-Dive Investigation (L3)
1. **Repeated Recovery Prompt Every Reboot (`PCR7` Binding Change):** Run `msinfo32` (or `Confirm-SecureBootUEFI`) and inspect **PCR Validation Profile** via `manage-bde -protectors -get C:`. External Thunderbolt/USB-C docks with PXE/Option ROMs or disabled **Secure Boot** alter PCR7 measurements on every boot.
2. **TPM Dictionary Attack Lockout (`TPM_LOCKOUT`):** Check `Get-Tpm` `LockoutCount` and Event Log `System` (`TPM-WMI` / `Microsoft-Windows-BitLocker-Driver`) for `0x80310000` or failing TPM self-tests.
3. **Missing Key Escrow in Entra/Intune (`KeyProtector` lacks RecoveryPassword or not escrowed):** Check `Microsoft-Windows-BitLocker/BitLocker Management` Operational log for escrow failure events after initial encryption.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Read the verified 48-digit key to `jsmith@example.com` so `PC-LAB-01` boots into Windows; if stuck on `"Enter the recovery key"` due to `TPM_LOCKOUT`, try a full 10-second cold power-off or unplug attached docks/USB drives before re-entering the key.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Before future BIOS/firmware updates, suspend BitLocker protection for 1–2 reboots (keeps drive encrypted while resealing TPM PCRs cleanly on next reboot):
   ```powershell
   Suspend-BitLocker -MountPoint "C:" -RebootCount 2
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Once booted in Windows, ensure a valid Recovery Password is present and escrowed to Entra ID / AD (`00000000-0000-0000-0000-000000000000` placeholder Key ID):
   ```powershell
   $kp = (Get-BitLockerVolume -MountPoint "C:").KeyProtector | Where-Object KeyProtectorType -eq "RecoveryPassword" | Select-Object -First 1
   BackupToAAD-BitLockerKeyProtector -MountPoint "C:" -KeyProtectorId $kp.KeyProtectorId
   ```

## Verification & Post-Fix Checks
1. Reboot `PC-LAB-01` cleanly once (with normal docking setup attached) and verify Windows boots straight to the sign-in screen without prompting for BitLocker recovery.
2. Confirm **Entra ID / Intune** shows the active BitLocker Recovery Key ID and `Get-BitLockerVolume C:` reports `ProtectionStatus = On`.

## Cross-Subject Escalation & Pivot Links
- **BitLocker recovery key never escrowed to Entra/Intune because MDM sync failed:** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](../07_macOS_Mobile_MDM/mdm-001-intune-compliance-sync.md)
- **Windows Update or BIOS/UEFI firmware update changed TPM PCR measurements:** [win-001 — Windows Update Failure and Component Store Corruption](./win-001-windows-update-corruption.md)
- **Windows 11 readiness assessment flags TPM 2.0 disabled or incompatible state:** [win-005 — Intune Windows 10 to Windows 11 Migration, Feature Updates, and Safeguard Holds](./win-005-intune-windows-11-migration-and-safeguard-holds.md)

## Client Update Snippets (EN / FR)
- **EN:** We verified your identity, retrieved the matching BitLocker recovery key for `PC-LAB-01`, and confirmed TPM protection resealed cleanly after reboot. Please confirm the workstation signs in normally without asking for the recovery key again.
- **FR:** Après vérification de votre identité, nous avons fourni la clé de récupération BitLocker pour `PC-LAB-01` et vérifié la resynchronisation TPM au redémarrage. Pouvez-vous confirmer que le poste démarre maintenant normalement sans redemander la clé ?
