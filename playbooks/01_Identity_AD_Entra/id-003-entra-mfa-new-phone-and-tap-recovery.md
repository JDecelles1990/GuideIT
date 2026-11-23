---
id: id-003
domain: 01_Identity_AD_Entra
subject: "Identity / AD & Entra ID"
subcategory: lockout_mfa_recovery
title: Entra ID MFA New Phone, Lost Authenticator, and Temporary Access Pass Recovery
tier: L1
keywords_en:
  - new phone mfa
  - lost authenticator
  - mfa not receiving code
  - microsoft authenticator reset
  - mfa loop new device
keywords_fr:
  - nouveau telephone mfa
  - reinitialiser mfa
  - authenticator ne fonctionne plus
  - code mfa non recu
  - perdu telephone authentification
error_codes:
  - AADSTS50074
  - AADSTS500121
tags:
  - mfa_new_phone
  - authenticator_reset
os:
  - cross_platform
  - ios
  - android
environment:
  - entra_id
  - m365
tools:
  - Entra Admin Center
  - Microsoft Graph PowerShell
  - Entra Sign-in Logs
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - id-001
  - sec-001
  - mdm-001
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Did you **get a new phone**, wipe/reset your phone, delete **Microsoft Authenticator**, or stop receiving push notifications?
2. On the Microsoft sign-in prompt, can you click **"I can't use my Microsoft Authenticator app right now"** or **"Sign in another way"** to see if a backup **SMS / Call / FIDO2 key** still works?
3. Before resetting MFA for `jsmith@example.com`, complete **Strict Identity Verification** per MSP policy (callback on verified corporate/HR phone number, manager approval, or live video ID check — **NEVER** reset MFA solely from an unverified email request!).

### Initial Scope & Classification
- Check if any **Authentication Strength** Conditional Access policy requires phishing-resistant MFA (Passkey / FIDO2) vs Authenticator app before issuing a Temporary Access Pass (TAP).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Check Backup Methods & Phone Notifications First:** Ask `jsmith@example.com` to test **"Sign in another way"** (SMS/voice/email/second device). If using Authenticator push, verify the mobile phone has **Automatic date & time ON** (wrong time breaks 6-digit TOTP codes!), **Notifications allowed**, **Low Power / Battery Optimization off** for Authenticator, and open Authenticator directly -> **pull down to refresh**!
2. **View Registered MFA Methods in Entra GUI ([Microsoft Entra Admin Center](https://entra.microsoft.com/) -> Users -> `jsmith@example.com` -> Authentication methods):** Check which phone models are listed and delete zero entries before verifying which phone is physically in front of the user!

### L2 Technical Diagnostics
1. Inspect the user's currently registered authentication methods in **Entra Admin Center -> Users -> `jsmith@example.com` -> Authentication methods** (or via Microsoft Graph PowerShell, read-only):
   ```powershell
   Connect-MgGraph -Scopes "UserAuthenticationMethod.Read.All", "AuditLog.Read.All"
   Get-MgUserAuthenticationMethod -UserId "jsmith@example.com" | Select-Object Id, OdataType
   ```
2. Check **Entra Sign-in Logs** for `jsmith@example.com` to confirm whether failures show `AADSTS50074` (Strong auth required), `AADSTS500121` (MFA validation failed/expired), or **Number Matching** timeout.
3. Verify the mobile device's system clock is set to **Automatic date & time** (skewed device clocks break 6-digit TOTP codes!) and **Do Not Disturb** / battery optimization is not suppressing Authenticator push notifications.

## Deep-Dive Investigation (L3)
1. **Registration Campaign / Security Info Location Block:** Check **Protection -> Conditional Access** for policies restricting `Register security information` to trusted office IP ranges (`Named Locations`). If `jsmith@example.com` is remote and blocked from re-registering MFA off-network, they need a **Temporary Access Pass (TAP)**!
2. **Stale PhoneAppNotification Entries:** Users with 3+ legacy phone entries sometimes receive push prompts on an old decommissioned device instead of the new phone; inspect individual method IDs and timestamps before cleanup.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** In **Entra Admin Center -> Users -> `jsmith@example.com` -> Authentication methods**, delete ONLY stale/lost Authenticator device entries and click **`Require re-register multifactor authentication`** (if the user still has an active backup method or is on a trusted location).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For remote users with zero working MFA methods (or blocked by Conditional Access registration location rules), issue a single-use, short-lived **Temporary Access Pass (TAP)** (e.g., 60 minutes, `IsUsableOnce = $true`) and deliver it securely over a verified voice call:
   ```powershell
   Connect-MgGraph -Scopes "UserAuthenticationMethod.ReadWrite.All"
   New-MgUserAuthenticationTemporaryAccessPassMethod `
       -UserId "jsmith@example.com" `
       -LifetimeInMinutes 60 `
       -IsUsableOnce:$true
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Walk `jsmith@example.com` through signing into [My Security Info](https://mysignins.microsoft.com/security-info) to pair the new Microsoft Authenticator app (or Passkey) and confirm Cloud Backup is enabled for future phone upgrades.

## Verification & Post-Fix Checks
1. Confirm `Get-MgUserAuthenticationMethod -UserId "jsmith@example.com"` lists the newly registered Authenticator / phone method.
2. Have `jsmith@example.com` sign out and sign into M365 web / Outlook approving a fresh MFA **Number Matching** prompt cleanly.

## Cross-Subject Escalation & Pivot Links
- **Repeated wrong MFA or password attempts triggered Entra Smart Lockout (AADSTS50053):** [id-001 — Account Lockout Investigation](./id-001-account-lockout.md)
- **Suspicious MFA device registration change or session token theft alert detected:** [sec-001 — Suspected Business Email Compromise and Session Token Theft](../06_Security_Access/sec-001-bec-token-compromise.md)
- **Conditional Access blocks sign-in even after MFA succeeds due to non-compliant device state:** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](../07_macOS_Mobile_MDM/mdm-001-intune-compliance-sync.md)

## Useful Links & External Tools
- **[Microsoft My Sign-Ins & Security Info](https://mysignins.microsoft.com/security-info)** — Self-service portal for users to pair Microsoft Authenticator, passkeys, or phone methods using a Temporary Access Pass (TAP).
- **[Microsoft Entra Admin Center](https://entra.microsoft.com/)** — Issue a one-time Temporary Access Pass (TAP) or require MFA re-registration under Users -> Authentication methods.
- **[Microsoft Entra AADSTS Error Code Lookup](https://login.microsoftonline.com/error)** — Decode AADSTS50074 / AADSTS50076 MFA challenge errors.

## Client Update Snippets (EN / FR)
- **EN:** Following identity verification, we reset your old MFA device registration and helped pair Microsoft Authenticator on your new phone. Please confirm you can now sign in and approve prompts normally.
- **FR:** Après vérification de votre identité, nous avons réinitialisé l'ancien appareil MFA et configuré Microsoft Authenticator sur votre nouveau téléphone. Pouvez-vous confirmer que la connexion et la validation MFA fonctionnent bien ?
