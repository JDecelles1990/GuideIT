---
id: id-009
domain: 01_Identity_AD_Entra
subject: "Identity / AD & Entra ID"
subcategory: lockout_mfa_recovery
title: Password Reset, SSPR Failure, and Cached Windows Credentials Out of Sync
tier: L1
keywords_en:
  - password reset
  - forgot password sspr
  - new password not working windows
  - cached password out of sync vpn
  - user password expired
keywords_fr:
  - reinitialisation mot de passe
  - mot de passe oublie sspr
  - nouveau mot de passe fonctionne pas windows
  - mot de passe en cache desynchronise
  - mot de passe expire windows
error_codes:
  - AADSTS50126
  - "0xC000006A"
  - SSPR_NOT_REGISTERED
tags:
  - password_reset_sspr
  - cached_credentials_sync
os:
  - windows
  - cross_platform
environment:
  - hybrid_ad
  - on_prem_ad
  - entra_id
tools:
  - Active Directory Users and Computers
  - Entra Admin Center
  - PowerShell
  - Credential Manager
risk_level: low
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - id-001
  - id-003
  - id-008
  - net-006
linked_scripts:
  - 05_Security_Defender/Get-LocalAccountStatus.ps1
  - 03_M365/Get-EntraRegistrationStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Did you **just change or reset your password**, and now the **new password works on Outlook Web / M365** (`portal.office.com`) while your **Windows laptop lock screen (`PC-LAB-01`)** still expects the **old password**? *(Very common for remote hybrid-joined laptops off VPN!)*
2. Are you locked out completely (`[id-001]`), did Self-Service Password Reset (**SSPR**) reject your verification method (`SSPR_NOT_REGISTERED`), or did your password expire?
3. Verify the caller's identity strictly per MSP policy (**callback to verified phone / manager / video check**) BEFORE issuing any temporary password!

### Initial Scope & Classification
- Distinguish **SSPR / Password Expired** vs **Hybrid Remote Cached Logon Desync** (Windows needs line-of-sight to a Domain Controller — usually via VPN or office Wi-Fi — once to cache a newly reset AD password!).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Test where the new password works vs fails:** Have `jsmith@example.com` test `https://portal.office.com` in a clean browser Private/Incognito window to confirm whether Entra/M365 already accepts the new password.
2. **Check Keyboard Layout (`FR` vs `EN` / `Caps Lock` / `Num Lock`) on Windows Lock Screen:** Especially on bilingual MSP setups (French Canadian vs US English keyboards), symbols (`@`, `/`, `?`) type differently before login! Click the bottom-right keyboard language indicator (`ENG` / `FRA`) and click the password **eye icon** to verify typed characters visually.
3. **Inspect Account Status in Entra / ADUC (GUI):** Confirm account is **Enabled**, not **Expired** (`Account expires`), and not **Locked out** (`[id-001]`).

### L2 Technical Diagnostics
1. **Check AD Account Password Age, Expiration, and Lockout State (`DC01.domain.local`, read-only):**
   ```powershell
   Get-ADUser -Identity "jsmith" -Properties Enabled, LockedOut, PasswordLastSet, PasswordExpired, msDS-UserPasswordExpiryTimeComputed |
       Select-Object SamAccountName, Enabled, LockedOut, PasswordLastSet, PasswordExpired
   ```
2. **Check Hybrid Join & Line-of-Sight to DC (`PC-LAB-01`, read-only):**
   ```powershell
   dsregcmd /status | Select-String -Pattern "AzureAdJoined|DomainJoined|AzureAdPrt"
   nltest /dsgetdc:domain.local
   ```
   *(If `DomainJoined = YES` and user is remote, `PC-LAB-01` cannot reach `DC01.domain.local` at the Windows lock screen until the user signs in with the **OLD cached password**, connects VPN (`[net-006]`), and locks/unlocks Windows (`Win + L`) once to sync the new credential!)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm identity verification method completed, whether `portal.office.com` accepts the password, `PasswordLastSet` timestamp, and whether client is Cloud-Only vs Hybrid AD + Entra Connect (`[id-008]`).

## Deep-Dive Investigation (L3)
1. **Password Writeback / PHS Latency (`SSPR_NOT_REGISTERED` / Desync):** If user changed password via Entra SSPR and on-prem AD failed to update (or vice versa -> `0xC000006A` on-prem vs cloud), inspect Entra Connect **Password Writeback** and **Password Hash Sync (PHS)** logs (`[id-008]`).
2. **Cached Logons Count Policy:** Verify GPO `Interactive logon: Number of previous logons to cache` isn't `0` for traveling laptops.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Never reuse passwords, never email plaintext temporary passwords in the same channel as the username, and always verify caller identity first!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Sync Trick for Remote Laptops After Reset)** When AD was reset while the user was working from home:
   - Have `jsmith@example.com` unlock Windows using their **previous cached password** -> connect to corporate **VPN (`[net-006]`)** -> wait 30 seconds -> press **`Win + L`** to Lock screen -> unlock with the **NEW password**! Windows immediately updates its cached domain verifier!
   - *(Alternatively, test VPN sign-in first if pre-logon VPN is enabled.)*
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Admin Reset + Unlock)** In **ADUC** (or **Entra Admin Center** for cloud-only users) — **only reset in AD if Hybrid AD**, NOT directly in Entra unless SSPR writeback is verified:
   ```powershell
   # On DC (Hybrid/On-Prem) after setting verified temporary password SecureString:
   Set-ADAccountPassword -Identity "jsmith" -Reset -NewPassword $secPwd
   Set-ADUser -Identity "jsmith" -ChangePasswordAtLogon $true
   Unlock-ADAccount -Identity "jsmith"
   ```
   *(Have the user update Office/mobile mail/Credential Manager prompts promptly so stale creds don't lock the account -> `[id-001]`!)*

## Verification & Post-Fix Checks
1. Confirm `jsmith@example.com` sets their own private complex password + registers backup SSPR methods at `https://aka.ms/mysecurityinfo` (`[id-003]`).
2. Verify both **Windows lock/unlock (`Win + L`)** and **`https://portal.office.com`** sign-in succeed cleanly without lockouts.

## Cross-Subject Escalation & Pivot Links
- **Old cached password on phone/Outlook locks out AD account after reset:** [id-001 — Account Lockout Investigation](./id-001-account-lockout.md)
- **User also lost MFA phone / needs Temporary Access Pass for SSPR recovery:** [id-003 — Entra ID MFA New Phone, Lost Authenticator, and Temporary Access Pass Recovery](./id-003-entra-mfa-new-phone-and-tap-recovery.md)
- **Cloud M365 and on-prem AD passwords remain permanently out of sync (PHS / Writeback):** [id-008 — Microsoft Entra Connect Sync Errors, Duplicate Attributes & PHS Stalls](./id-008-entra-connect-sync-errors-and-duplicate-attributes.md)
- **Remote user cannot connect VPN after password reset to sync Windows login:** [net-006 — Remote Client VPN Cannot Connect (FortiClient, GlobalProtect, AnyConnect, Windows VPN)](../04_Network_VPN_VoIP/net-006-client-vpn-wont-connect-forticlient-anyconnect-globalprotect.md)

## Client Update Snippets (EN / FR)
- **EN:** After verifying your identity, we completed your password reset and synced your workstation credentials over VPN so both Windows and Microsoft 365 accept your new password. Please confirm you can lock and unlock Windows normally and access your email.
- **FR:** Après vérification de votre identité, nous avons complété la réinitialisation du mot de passe et resynchronisé vos identifiants sur votre poste via le VPN afin que Windows et Microsoft 365 acceptent le nouveau mot de passe. Pouvez-vous tester le verrouillage/déverrouillage Windows et votre messagerie ?
