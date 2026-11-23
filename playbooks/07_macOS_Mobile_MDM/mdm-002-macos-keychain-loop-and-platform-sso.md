---
id: mdm-002
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: macos_basics_apps_shares
title: macOS Login Keychain Password Loop and Platform SSO / FileVault Desync
tier: L2
keywords_en:
  - mac keychain password prompt
  - login keychain keeps popping up
  - mac password changed keychain loop
  - platform sso desync macos
  - wants to use the login keychain
keywords_fr:
  - trousseau d'acces mac
  - mac demande mot de passe trousseau
  - boucle mot de passe trousseau macos
  - synchronisation mot de passe mac
  - erreur keychain mac
error_codes:
  - ERRSEC_AUTH_FAILED
tags:
  - macos_keychain_loop
  - platform_sso_desync
os:
  - macos
environment:
  - intune
  - entra_id
  - local_endpoint
tools:
  - Terminal
  - Keychain Access
  - Company Portal
  - Intune Admin Center
risk_level: medium
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - id-001
  - mdm-001
  - mdm-007
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Did you **recently change your Mac login password / Entra / AD password**, after which popups appeared for **`"talagent wants to use the login keychain"`**, **`"Microsoft Teams"`**, or **`"Local Items"`**?
2. **Crucial L1 Question:** Do you still **know/remember your PREVIOUS Mac password**? *(If YES, we can update the keychain password cleanly without erasing saved Wi-Fi/Safari/app passwords!)*
3. If you click Cancel 3–4 times, does the Mac still let you open Chrome/Outlook, or do prompts keep coming back?

### Initial Scope & Classification
- Distinguish **known old password** (`security set-keychain-password` / Keychain Access -> Edit -> Change Password) vs **unknown old password** (`Reset Default Keychains` safely after archiving old `.keychain-db`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — GUI Keychain Access Check)
1. **Verify Old Password & Open `Keychain Access` (`⌘ + Space` -> type `Keychain Access` -> Enter):**
   - Look in the left sidebar of **Keychain Access**: is the **`login`** padlock icon closed/locked while `Local Items` is unlocked?
   - Ask `jsmith@example.com` if they remember their previous password (note if you know it, **Edit -> Change Password for Keychain "login"...** solves it in 30 seconds!).
   - Verify Mac internet/VPN (`Platform SSO` / `Entra`) works cleanly.

### L2 Technical Diagnostics
1. **Inspect active macOS keychains, lock state, and Platform SSO status in Terminal (read-only):**
   ```bash
   security list-keychains
   security show-keychain-info ~/Library/Keychains/login.keychain-db 2>&1 || true
   app-sso platform -s 2>/dev/null || true
   ```
2. **Check FileVault & Secure Token status (important before resetting local passwords!):**
   ```bash
   fdesetup status
   sysadminctl -secureTokenStatus "$USER" 2>&1
   ```
3. **Check `Local Items` / iCloud Keychain vs `login.keychain-db`:** Inspect **Keychain Access.app** to see which keychain is locked (`login` vs `Local Items` vs `Microsoft_Intermediate_Certificates`).

## Deep-Dive Investigation (L3)
1. **Password Desync (`ERRSEC_AUTH_FAILED`):** When a Mac password changes via Recovery, FileVault reset, or out-of-band MDM/AD sync without running `login.keychain-db` re-encryption, macOS cannot auto-unlock `login.keychain-db` at sign-in and prompts endlessly.
2. **Platform SSO Token/Keychain Mismatch:** Run `log show --predicate 'subsystem == "com.apple.AppSSO"' --last 1h --style compact` to inspect Entra Platform SSO registration or SmartCard/Secure Enclave key sync errors.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Preferred (Preserves Saved Passwords/Certs — User Knows Old Password):**
   - Open **Keychain Access.app -> Edit -> Change Password for Keychain "login"...** (or via Terminal), enter the **old** Mac password as Current Password, and enter the **current** Mac login password as New Password:
     ```bash
     security set-keychain-password ~/Library/Keychains/login.keychain-db
     ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **If User Forgot Old Password (Creates Clean Keychain — Safely Archives Old File):**
   - Close all apps (Outlook, Teams, Safari/Chrome), back up the old keychain folder first (never `rm -rf`!), or use **Keychain Access -> Settings -> Reset Default Keychains**:
     ```bash
     mv ~/Library/Keychains/login.keychain-db ~/Desktop/login.keychain-db.bak
     ```
     Then **log out and log back in** (or reboot) so macOS creates a fresh `login.keychain-db` synced to the current password.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Re-sign into **Company Portal** / **Microsoft Office** (`[m365-001]` / `[mdm-001]`) if Workplace Join / Entra PRT certificates resided in the old keychain.

## Verification & Post-Fix Checks
1. Reboot the Mac, sign in once as `jsmith@example.com`, and verify **Keychain Access.app** shows the **`login`** keychain unlocked with zero popup prompts.
2. Open Outlook/Teams/Safari and confirm SSO signs in without repeating keychain dialogs.

## Cross-Subject Escalation & Pivot Links
- **Account lockout on AD/Entra prevents macOS Platform SSO / Kerberos SSO unlock:** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)
- **Broken Intune Company Portal token prevents SSO extension and compliance check:** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](./mdm-001-intune-compliance-sync.md)
- **Desynced macOS Keychain credentials fail SMB network share mounts in Finder:** [mdm-007 — Beginner macOS Finder SMB Network Share, DNS Flush, and Office Mac Licensing](./mdm-007-macos-finder-smb-share-and-office-licensing.md)

## Client Update Snippets (EN / FR)
- **EN:** We resynchronized the macOS `login` keychain password with your current account password and cleared the repeated prompts. Please restart or sign back into your Mac once and confirm everything works cleanly.
- **FR:** Nous avons resynchronisé le mot de passe du trousseau d'accès macOS (`login`) avec votre mot de passe actuel et éliminé les fenêtres répétitives. Pouvez-vous redémarrer votre Mac et confirmer que tout fonctionne normalement ?
