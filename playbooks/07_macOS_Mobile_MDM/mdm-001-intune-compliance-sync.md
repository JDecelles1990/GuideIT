---
id: mdm-001
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: intune_autopilot_mdm
title: macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure
tier: L2
keywords_en:
  - intune non-compliant
  - company portal error
  - mac not syncing
  - iphone email blocked
  - mdm profile expired
keywords_fr:
  - intune non conforme
  - mac ne synchronise pas
  - portail d'entreprise
  - appareil non conforme
  - blocage acces conditionnel mobile
error_codes:
  - AADSTS53000
  - AADSTS53003
tags:
  - intune_compliance
  - mdm_sync
os:
  - macos
  - ios
environment:
  - intune
  - entra_id
  - m365
tools:
  - Intune Admin Center
  - Company Portal
  - Terminal
  - Console.app
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - mdm-008
  - m365-001
  - win-002
  - net-002
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Which platform is blocked (**Mac laptop**, **iPhone/iPad**, or **Windows** -> check `[mdm-008]`/`[mdm-009]` too), and what exact banner appears (`"Your device isn't compliant"` / `AADSTS53000`)?
2. Click inside **Company Portal -> Devices**: which exact red X compliance item failed (**Restart required**, **OS update out-of-date**, **Passcode/FileVault off**, or **`Hasn't checked in`**)?
3. Is **THIS affecting just 1 user**, OR are **ALL Apple iOS/macOS devices suddenly non-compliant** today (check **Apple MDM Push Certificate** expiry immediately!)?

### Initial Scope & Classification
- Check **Intune Admin Center -> Devices -> `Device` -> Device compliance** to see the exact failing setting (`OS minimum version`, `Encryption/FileVault`, `Grace period`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Company Portal App & Intune Web GUI)
1. **Have the User Open `Company Portal` -> `Devices` -> Select This Device -> Click `Check status`:**
   - Company Portal highlights the exact failing requirement in plain English (e.g., *"Encrypt your device storage"*, *"Update macOS/iOS to 15.x"*, or *"Set a passcode"*)! Have the user satisfy any OS update / Restart / Lock-screen prompt right there and click **`Check status`** again (allow 5–10 minutes for Entra Conditional Access sync!).
2. **Check Intune Portal GUI ([Microsoft Intune Admin Center](https://intune.microsoft.com/)):**
   - Open **Devices -> All devices -> `<Device Name>` -> Device compliance** and check **Last check-in** + failing Policy row!
   - If many Apple devices stopped syncing simultaneously, check **Tenant administration -> Connectors and tokens -> Apple MDM Push certificate** expiration date (`Active` vs `Expired`)!

### L2 Technical Diagnostics
1. **On macOS**, inspect MDM enrollment, installed configuration profiles, and FileVault disk encryption status (read-only):
   ```bash
   profiles status -type enrollment
   profiles list
   fdesetup status
   sw_vers
   ```
2. **On macOS**, inspect Intune MDM agent / Company Portal logs over the last 2 hours (read-only):
   ```bash
   log show --predicate 'subsystem == "com.microsoft.intune.mac" OR process == "IntuneMdmAgent"' --last 2h --style compact
   ```
3. **On iOS / iPadOS**:
   - Open **Settings -> General -> VPN & Device Management** and confirm the `Management Profile` is present and verified.
   - Open **Company Portal -> Devices** and check the last check-in timestamp and compliance checklist (e.g., iOS version below minimum baseline or missing passcode).

## Deep-Dive Investigation (L3)
1. **Entra Device ID Mismatch (`AADSTS53000`):** Verify the Entra Device ID in `Company Portal` / Keychain (`Microsoft.Identity.Client` / `Platform SSO` or `IntuneMDM` identity) matches the active compliant record in **Entra ID -> Devices** (duplicate stale device records often cause Conditional Access evaluation failures).
2. **APNs Push Connectivity:** Confirm macOS/iOS can reach Apple Push Notification servers (`TCP 5223` / `443`) without SSL inspection breaking APNs certificate pinning.
3. **FileVault Recovery Key Escrow Failure:** If FileVault was enabled manually before MDM enrollment, Intune may report non-compliance until personal recovery key rotation escrows a key to Intune.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Trigger an immediate MDM policy & compliance check-in:
   - **macOS / iOS:** Open **Company Portal -> Devices -> Select device -> Check status / Check access**.
   - **Intune Admin Center:** Open the device record and click **Sync**.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If macOS MDM profile communication is broken while enrollment remains valid, renew enrollment profiles (requires local admin):
   ```bash
   sudo profiles renew -type enrollment
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If the device has a corrupted duplicate Entra/Intune registration or orphaned MDM profile (`ABM/ADE` or user-enrolled), retire/wipe stale duplicate records in Intune/Entra (avoid remote full-wipe unless explicitly authorized!) and re-enroll via Company Portal or Automated Device Enrollment.
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **Apple MDM Push certificate** is expired, renew it in Intune using the exact original Apple ID (never generate a new certificate with a different Apple ID, which orphans all enrolled Apple devices).

## Verification & Post-Fix Checks
1. Confirm **Intune Admin Center** shows `Compliance: Compliant` and an updated `Last check-in` timestamp.
2. Have `jsmith@example.com` sign into Outlook/Teams/Web M365 and verify Conditional Access passes without `AADSTS53000`.

## Cross-Subject Escalation & Pivot Links
- **Endpoint failed initial Intune MDM enrollment or Windows Autopilot ESP provisioning:** [mdm-008 — Intune New Device Enrollment, Windows Autopilot OOBE, and ESP Failures](./mdm-008-intune-new-device-enrollment-and-autopilot.md)
- **Conditional Access blocks Outlook/M365 sign-in until Intune Company Portal marks device Compliant:** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](../02_M365_Email_Collab/m365-001-outlook-auth-loop.md)
- **Windows compliance fails because BitLocker encryption policy/key escrow did not apply:** [win-002 — BitLocker Recovery Key Prompt After Update and TPM Lockout Triage](../03_Windows_Endpoints/win-002-bitlocker-recovery-screen-and-tpm.md)
- **macOS/iOS/Windows fails corporate Wi-Fi until Intune SCEP certificate deploys:** [net-002 — Wi-Fi Random Disconnects, Connected Without Internet, and 802.1X Auth Triage](../04_Network_VPN_VoIP/net-002-wifi-drops-and-8021x-auth.md)

## Useful Links & External Tools
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Inspect device compliance policies, last check-in time, and trigger remote Sync.
- **[Microsoft Entra Admin Center](https://entra.microsoft.com/)** — Review Conditional Access sign-in logs for device-compliance blocks.
- **[M365 Maps (Microsoft Licensing Matrix)](https://m365maps.com/)** — Confirm the user's M365 SKU includes Intune Plan 1 and Entra ID P1.

## Client Update Snippets (EN / FR)
- **EN:** We synchronized your device with Intune and resolved the compliance check blocking Microsoft 365 access. Please wait 5 minutes and test signing into Outlook or Teams again.
- **FR:** Nous avons synchronisé votre appareil avec Intune et corrigé l'état de conformité qui bloquait l'accès à Microsoft 365. Veuillez patienter 5 minutes puis tester de nouveau la connexion à Outlook ou Teams.
