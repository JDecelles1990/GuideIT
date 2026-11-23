---
id: id-010
domain: 01_Identity_AD_Entra
subject: "Identity / AD & Entra ID"
subcategory: lockout_mfa_recovery
title: Windows Hello for Business / PIN Not Working and Sign-In Options Missing
tier: L1
keywords_en:
  - windows hello pin not working
  - something went wrong your pin isn't available
  - pin option missing sign in
  - reset windows hello pin
  - fingerprint face recognition not working windows
keywords_fr:
  - code pin windows hello ne fonctionne pas
  - code pin non disponible 0x80090016
  - reinitialiser code pin windows
  - reconnaissance faciale empreinte windows bloquee
  - options de connexion disparues windows
error_codes:
  - "0x80090016"
  - "0x8009002D"
  - PIN_UNAVAILABLE
tags:
  - windows_hello_pin
  - ngc_pin_reset
os:
  - windows
environment:
  - entra_id
  - intune
  - hybrid_ad
  - local_endpoint
tools:
  - Windows Settings (Accounts -> Sign-in options)
  - PowerShell
  - dsregcmd
  - Registry / Ngc Folder
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - id-003
  - id-009
  - win-002
linked_scripts:
  - 03_M365/Get-EntraRegistrationStatus.ps1
  - 05_Security_Defender/Get-LocalAccountStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. What exact message appears when entering the PIN (`"Something went wrong and your PIN isn't available"` / `0x80090016`, `"Your credentials could not be verified"`, or **"This option is currently unavailable"**)?
2. Can you still click **`Sign-in options`** below the PIN box and sign in using your **Password** (or key icon), or are all alternatives missing?
3. Did this start right after a **BIOS/UEFI update**, **TPM reset**, **motherboard repair**, or **BitLocker prompt** (`[win-002]`)?

### Initial Scope & Classification
- Windows Hello PIN keys are cryptographically bound to the laptop's **TPM chip** (`Ngc` folder). BIOS updates or TPM resets frequently break existing `Ngc` keys (`0x80090016` / `0x8009002D`), while Intune/GPO policies control whether PIN sign-in is enabled.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Get the user back to work immediately via Password Sign-In:** On the lock screen, click **`Sign-in options`** (under the PIN field or `"I forgot my PIN"`) -> click the **Key / Password icon** -> sign in with their regular corporate password (`[id-009]`).
2. **Test `"I forgot my PIN"` self-service reset:** Once signed into Windows with internet/VPN connected, open **Settings -> Accounts -> Sign-in options -> PIN (Windows Hello) -> I forgot my PIN** (or **Remove -> Set up**), then re-authenticate with password + MFA (`[id-003]`).
3. **Check whether an organization policy disabled PIN:** Under **Settings -> Accounts -> Sign-in options**, check if a red banner says `"Some of these settings are hidden or managed by your organization"`.

### L2 Technical Diagnostics
1. **Check TPM Health, Entra `Ngc` Key State, and Hello Policy (read-only):**
   ```powershell
   Get-Tpm | Select-Object TpmPresent, TpmReady, TpmEnabled, TpmActivated, LockoutCount
   dsregcmd /status | Select-String -Pattern "NgcSet|WamDefaultSet|AzureAdJoined|WorkplaceJoined|KeySignTest"
   Get-Service NGC, NgcCtnrSvc -ErrorAction SilentlyContinue | Select-Object Name, Status, StartType
   ```
   - `0x80090016` (`Keyset does not exist`) / `0x8009002D`: TPM cleared, motherboard swapped, or corrupted `C:\Windows\ServiceProfiles\LocalService\AppData\Local\Microsoft\Ngc` container!
   - `KeySignTest: FAILED`: TPM attestation/key signing broken (`[win-002]`).
2. **Check Windows Hello for Business Operational Event Log (read-only):**
   ```powershell
   Get-WinEvent -LogName "Microsoft-Windows-User Device Registration/Admin" -MaxEvents 10 -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, LevelDisplayName, Message
   ```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact error code (`0x80090016` / `0x8009002D`), whether **Password** sign-in works, `Get-Tpm` output, and whether BIOS was updated recently.

## Deep-Dive Investigation (L3)
1. **Corrupted `Ngc` Container Preventing PIN Removal/Reset:** When **Settings -> I forgot my PIN** spins or fails silently, Windows cannot overwrite locked system ACL files inside `C:\Windows\ServiceProfiles\LocalService\AppData\Local\Microsoft\Ngc`.
2. **Intune / GPO WHfB Conflict:** Verify `UsePassportForWork` / `PassportForWork` CSP settings in **Intune -> Devices -> Windows -> Configuration** vs on-prem AD `Computer Configuration -> Administrative Templates -> Windows Components -> Windows Hello for Business` (if Hybrid Cloud Kerberos Trust wasn't configured cleanly, WHfB PIN may fail SMB/file server access!).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Verify the user can sign in with their **Password** (`Sign-in options`) BEFORE clearing `Ngc` or toggling Hello settings! Clearing `Ngc` removes ALL users' local Windows Hello PIN/biometrics on that single PC cleanly without touching user files or M365 data.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Quick Fix)** Have `jsmith@example.com` sign in via **Password** -> **Settings -> Accounts -> Sign-in options -> PIN (Windows Hello) -> I forgot my PIN** -> approve MFA prompt and set a new PIN.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Corrupted `Ngc` Container Reset)** ONLY if **I forgot my PIN** fails and **TPM is Ready (`TpmReady = True`)**: take ownership of `Ngc` cleanly and rename/clear it on `PC-LAB-01` (requires local admin + reboot):
   ```cmd
   REM Run in elevated CMD ONLY after confirming password login works on PC-LAB-01
   takeown /f C:\Windows\ServiceProfiles\LocalService\AppData\Local\Microsoft\Ngc /r /d y
   icacls C:\Windows\ServiceProfiles\LocalService\AppData\Local\Microsoft\Ngc /grant administrators:F /t
   ren C:\Windows\ServiceProfiles\LocalService\AppData\Local\Microsoft\Ngc Ngc.old
   ```
   Reboot `PC-LAB-01`, sign in with **Password**, then re-enroll **Windows Hello PIN / Fingerprint / Face** in **Settings -> Accounts -> Sign-in options**.

## Verification & Post-Fix Checks
1. Press **`Win + L`** to lock `PC-LAB-01` and unlock cleanly with the newly configured **Windows Hello PIN / biometrics**.
2. Confirm `dsregcmd /status` shows `NgcSet : YES` and no new errors in `User Device Registration/Admin`.

## Cross-Subject Escalation & Pivot Links
- **BIOS update / TPM lockout triggered both BitLocker recovery screen and PIN keyset error (0x80090016):** [win-002 — BitLocker Recovery Key Prompt After Update and TPM Lockout Triage](../03_Windows_Endpoints/win-002-bitlocker-recovery-screen-and-tpm.md)
- **User forgot their underlying password needed for Sign-in options -> Password:** [id-009 — Password Reset, SSPR Failure, and Cached Windows Credentials Out of Sync](./id-009-password-reset-sspr-and-cached-credentials-sync.md)
- **PIN reset requires MFA approval while user also replaced their mobile Authenticator:** [id-003 — Entra ID MFA New Phone, Lost Authenticator, and Temporary Access Pass Recovery](./id-003-entra-mfa-new-phone-and-tap-recovery.md)


## Useful Links & External Tools
- **[Microsoft My Sign-Ins & Security Info](https://mysignins.microsoft.com/security-info)** — Let the user manage registered Windows Hello / Passkey / Authenticator sign-in methods.
- **[Microsoft Entra Admin Center](https://entra.microsoft.com/)** — Check device registration and Windows Hello for Business sign-in logs.
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Verify Windows Hello for Business policy and device compliance status.
## Client Update Snippets (EN / FR)
- **EN:** We cleared the corrupted Windows Hello PIN container tied to your laptop's security chip on `PC-LAB-01` and guided you through re-enrolling a fresh PIN. Could you test locking (`Win + L`) and unlocking your PC with your new PIN?
- **FR:** Nous avons réinitialisé le conteneur corrompu du code PIN Windows Hello sur `PC-LAB-01` et reconfiguré un nouveau code PIN. Pouvez-vous tester le verrouillage (`Win + L`) et le déverrouillage avec votre nouveau PIN ?
