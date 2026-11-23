---
id: id-001
domain: 01_Identity_AD_Entra
subject: "Identity / AD & Entra ID"
subcategory: lockout_mfa_recovery
title: Account Lockout Investigation
tier: L2
keywords_en:
  - locked out
  - account locked
  - bad password
  - keeps locking
  - active directory lockout
keywords_fr:
  - compte verrouillé
  - compte verrouille
  - verrouillé
  - mot de passe refusé
  - verrouillage en boucle
error_codes:
  - "4740"
  - "4625"
  - "0xC0000234"
  - AADSTS50053
tags:
  - account_lockout
  - bad_password
os:
  - windows
environment:
  - hybrid_ad
  - on_prem_ad
  - entra_id
tools:
  - Event Viewer
  - PowerShell
  - Active Directory Users and Computers
  - Entra Sign-in Logs
risk_level: low
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - m365-001
  - sec-001
  - id-005
  - net-004
linked_scripts:
  - 06_AD_Identity/Get-AccountLockoutEvents.ps1
  - 05_Security_Defender/Get-LocalAccountStatus.ps1
  - 01_System/Get-RecentEventErrors.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is the lockout happening across **every app (Windows login + Outlook + M365 Web)** or ONLY on one workstation (`PC-LAB-01`)?
2. Did you **recently change your password** within the last 24 hours on a phone, tablet, Outlook, or secondary PC (`[m365-001]`)?
3. Are other coworkers also locked out simultaneously (if YES -> immediate password-spray warning `[sec-001]`)?
4. Do you have any mapped network drives (`net use`), stored Windows credentials, or unattended reports/scripts using your login?

### Initial Scope & Classification
- Verify whether only one device (`CallerComputer`) is locking `jsmith@example.com` or multiple accounts are locking simultaneously (`[sec-001]`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Check ADUC / Entra Admin Center Account Status (GUI):** Confirm `jsmith@example.com` shows **Locked out** (vs Password Expired -> `[id-009]` vs Disabled). Wait 60 seconds before unlocking blindly if you haven't found what device is sending bad passwords, otherwise it will re-lock in seconds!
2. **Ask About Phones, Browser Saved Passwords & Wi-Fi:** Check if the user has corporate email in **iOS/Android Apple Mail/Outlook** or corporate **Wi-Fi (`802.1X` using AD credentials)** holding their old password!
3. **Check Windows Credential Manager (`control /name Microsoft.CredentialManager` GUI on `PC-LAB-01`):** Open **Windows Credentials** tab and look for old `MicrosoftOffice16`, `Teams`, `VPN`, or file server `SRV-FILE-01` entries!

### L2 Technical Diagnostics
1. Query the PDC Emulator for `Event ID 4740` to identify the `Caller Computer Name` triggering the lockout:
   ```powershell
   $pdc = (Get-ADDomain).PDCEmulator
   Get-WinEvent -ComputerName $pdc -FilterHashtable @{
       LogName   = 'Security'
       Id        = 4740
       StartTime = (Get-Date).AddHours(-4)
   } | Select-Object TimeCreated,
       @{N='User';E={$_.Properties[0].Value}},
       @{N='CallerComputer';E={$_.Properties[1].Value}} |
       Format-Table -AutoSize
   ```
2. Check current AD lockout status and bad password timestamp (read-only):
   ```powershell
   Get-ADUser -Identity "jsmith" -Properties LockedOut, BadPwdCount, LastBadPasswordAttempt, PasswordLastSet |
       Select-Object SamAccountName, LockedOut, BadPwdCount, LastBadPasswordAttempt, PasswordLastSet
   ```
3. On the reported `CallerComputer` (`PC-LAB-01`), inspect cached credentials and scheduled tasks (read-only):
   ```cmd
   cmdkey /list
   ```
   ```powershell
   Get-ScheduledTask | Where-Object { $_.Principal.UserId -like "*jsmith*" } | Select-Object TaskName, TaskPath, State
   ```

## Deep-Dive Investigation (L3)
1. **If `Caller Computer Name` is blank, `NULL`, or an ADFS/Entra Seamless SSO/NPS server:**
   - Inspect `Event ID 4625` on the PDC Emulator or RADIUS/NPS host (`0xC0000234` = account locked; `0xC000006A` = bad password) and correlate source IP/workstation.
   - Review **Entra ID Sign-in Logs** for `jsmith@example.com` filtering for `AADSTS50053` (Smart Lockout) or legacy auth (`IMAP`, `POP3`, `SMTP`, `ActiveSync`), and note external source IPs (`198.51.100.10` placeholder).
2. **Verify hybrid device join & PRT state on `PC-LAB-01`:**
   ```cmd
   dsregcmd /status
   nltest /dsgetdc:domain.local
   ```
3. Inspect mapped network drives (`net use`), Windows Services (`Get-CimInstance Win32_Service | Select-Object Name, StartName`), and stale mobile mail profiles using basic auth.
4. If external spray activity is detected across accounts, pivot immediately to `[sec-001]`.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** After removing stale cached credentials or updating the mobile password, unlock the Active Directory account on the domain controller:
   ```powershell
   Unlock-ADAccount -Identity "jsmith" -Server (Get-ADDomain).PDCEmulator
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Remove stale Windows Credential Manager entries on the user's workstation (`PC-LAB-01`):
   ```cmd
   cmdkey /delete:<TargetNameFromCmdkeyList>
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If a workstation scheduled task or service runs under the user's old password, update its credential or convert it to a managed service account (gMSA).

## Verification & Post-Fix Checks
1. Confirm `LockedOut` stays `False` and `BadPwdCount` does not increment over the next 15–30 minutes:
   ```powershell
   Get-ADUser -Identity "jsmith" -Properties LockedOut, BadPwdCount, LastBadPasswordAttempt
   ```
2. Have `jsmith@example.com` lock and unlock Windows (`PC-LAB-01`) and verify Outlook/M365 sign-in succeeds cleanly.

## Cross-Subject Escalation & Pivot Links
- **Outlook repeatedly prompts for credentials or modern auth stalls after a password change:** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](../02_M365_Email_Collab/m365-001-outlook-auth-loop.md)
- **Lockouts come from foreign/anonymous IPs, NULL caller host, or credential-stuffing spray:** [sec-001 — Suspected Business Email Compromise and Session Token Theft](../06_Security_Access/sec-001-bec-token-compromise.md)
- **Workstation Kerberos secure channel (5722) fails alongside domain logon attempts:** [id-005 — Windows Domain Trust Relationship Failed (Event ID 5722 / 3210 / 0xC000018B)](./id-005-windows-domain-trust-relationship-failed.md)
- **Cached SMB credentials in Windows Credential Manager lock out AD on drive reconnect:** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)


## Useful Links & External Tools
- **[Microsoft Self-Service Password Reset (SSPR)](https://passwordreset.microsoftonline.com/)** — Allow Entra/hybrid users to unlock their own account or reset a forgotten password after identity verification.
- **[Microsoft My Sign-Ins & Security Info](https://mysignins.microsoft.com/security-info)** — Have users verify or update registered Authenticator, phone, and SSPR methods.
- **[Microsoft Entra Admin Center](https://entra.microsoft.com/)** — Inspect Sign-in logs (AADSTS50053 Smart Lockout) and source IPs.
- **[Have I Been Pwned](https://haveibeenpwned.com/)** — Check whether the user's email appeared in external credential breaches during repeated lockout investigations.
## Client Update Snippets (EN / FR)
- **EN:** We identified the source device (`PC-LAB-01`) sending outdated cached credentials, cleared the stale entry, and unlocked your account. Please sign back in and let us know if any prompt reappears.
- **FR:** Nous avons identifié l'appareil source (`PC-LAB-01`) qui envoyait d'anciens identifiants en cache, nettoyé l'entrée obsolète et déverrouillé votre compte. Veuillez vous reconnecter et nous confirmer si tout reste stable.
