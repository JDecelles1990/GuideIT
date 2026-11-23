---
id: mdm-009
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: intune_autopilot_mdm
title: Mobile (iPhone / Android) Outlook & Teams App Not Syncing or Blocked by App Protection
tier: L1
keywords_en:
  - iphone outlook not syncing email
  - android teams mobile not working
  - intune app protection policy mobile
  - get access to this resource company portal mobile
  - outlook mobile asking for password
keywords_fr:
  - outlook iphone ne synchronise plus
  - teams telephone bloque entreprise
  - portail entreprise mobile intune requis
  - protection applications intune telephone
  - courriel telephone portable ne recoit pas
error_codes:
  - MAM_APP_PROTECT
  - AADSTS530003
tags:
  - mobile_outlook_sync
  - intune_app_protection
os:
  - ios
  - android
environment:
  - m365
  - entra_id
  - intune
tools:
  - Microsoft Intune Admin Center
  - Microsoft Authenticator / Company Portal App
  - Outlook Mobile / Teams Mobile
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - mdm-001
  - id-003
  - m365-001
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you using the **official Microsoft Outlook / Microsoft Teams app** from the App Store / Play Store, or Apple's built-in Mail app (blocked on many Conditional Access tenants!)?
2. What exact message pops up on the phone (`"Sign in required"`, `"Your organization protects data in this app — install Company Portal / Authenticator"`, `"Update your OS"`, or just **no new emails arriving**)?
3. Is this a **personal BYOD phone** (App Protection / MAM only, using **Microsoft Authenticator** on iOS or **Company Portal** on Android!) or a **company-managed enrolled phone** (`[mdm-001]`)?
4. Did you recently **change your password**, turn on **Low Power Mode / Background App Refresh Off**, or upgrade iOS/Android?

### Initial Scope & Classification
- Almost all mobile email/Teams blocks are resolved cleanly at **L1** by: (1) switching from Apple Mail to **Outlook Mobile**, (2) installing **Microsoft Authenticator (iOS)** / **Company Portal (Android)** as the **broker app** (note Android requires Company Portal installed — **without signing into full device enrollment** — for MAM!), or (3) resetting the account inside Outlook Mobile (`Reset Account`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Verify Broker App & OS Minimum Version on Phone:**
   - **iPhone / iPad (`iOS`):** Must have **Microsoft Authenticator** installed from App Store (acts as broker for MAM App Protection!) AND OS updated to supported version (`Settings -> General -> Software Update`).
   - **Android:** Must have **Intune Company Portal** installed from Play Store (Wait: for BYOD **App Protection**, user just **installs** Company Portal and leaves it there — Authenticator / Outlook then prompts cleanly without enrolling the personal phone!). Verify Work Profile isn't **Paused** (greyed-out briefcase icons in Android drawer!).
2. **Confirm Official App vs Native Mail:** Conditional Access `"Require approved client app / App protection policy"` blocks Apple Mail and Samsung Email (`AADSTS530003`) -> require **Outlook for iOS/Android**.
3. **Check Phone Notification & Background Sync Settings:** Verify Cellular Data / Wi-Fi is active, **Low Power Mode** isn't throttling push notifications, and **Background App Refresh + Notifications** are enabled for Outlook/Teams!

### L2 Technical Diagnostics
1. **Check Entra Sign-in Logs & Intune App Protection Status (`jsmith@example.com`, read-only):**
   - In **Entra Admin Center -> Users -> `jsmith@example.com` -> Sign-in logs**: check why `Outlook Mobile` / `Teams Mobile` failed (`AADSTS530003` = missing App Protection broker, `Device Non-Compliant` -> `[mdm-001]`, or Jailbroken/Rooted detection!).
   - In **Intune Admin Center -> Apps -> Monitor -> App protection status**: search `jsmith@example.com` to confirm last check-in timestamp, app version, and OS compliance flags.
2. **Check ActiveSync / Mobile Device Quarantine in Exchange Admin Center:** In **EAC -> Mobile -> Mobile devices**, ensure old devices didn't hit the **10-device Exchange partnership limit** or sit in **Quarantined**!

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Phone model & exact iOS/Android version, whether BYOD MAM vs MDM enrolled, screenshot of exact banner (`AADSTS` code), and Entra Sign-in Log status.

## Deep-Dive Investigation (L3)
1. **Microsoft Edge / Broker Keychain Loop on iOS:** Corrupted iOS keychain token across Microsoft apps (`Outlook`, `Teams`, `Authenticator`, `OneDrive`) triggers infinite loops until **ALL Microsoft apps are signed out**, **Authenticator broker cache cleared**, or Microsoft app permissions refreshed cleanly.
2. **Defender for Endpoint Mobile Threat / Root Detection (`MAM_APP_PROTECT`):** Intune MAM blocks corporate mail automatically if Developer Options / USB Debugging (Wait: check policy!), jailbreak, or missing device Screen Lock PIN is detected!

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Warn the user before clicking **Remove Account** in Outlook/Teams Mobile if they store personal accounts there too; corporate M365 emails stay 100% safe on Microsoft's servers! Also **NEVER** wipe an entire BYOD personal phone in Intune when only corporate app data (`Selective Wipe` -> Retire/Wipe app data only!) needs clearing!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 App Protection Broker & Outlook Reset)**
   - Ensure **iOS Screen Lock / Passcode + OS Update** are current, install **Microsoft Authenticator** (iOS) or **Intune Company Portal** (Android), and unpause Android Work Profile if paused.
   - Inside **Outlook Mobile -> Settings (`Gear`) -> `jsmith@example.com` -> `Reset Account`** (first choice — preserves settings) or **`Delete Account`** -> force-close Outlook -> reopen & sign in cleanly (`[id-003]` MFA if needed).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Clear Stuck Mobile Conditional Access / Exchange Quarantine)** Allow approved devices in EAC if quarantined, remove decommissioned mobile partnerships if at 10-device cap, or issue an Intune **App selective wipe** ONLY for stuck MAM policy registration before having the user sign back in cleanly.

## Verification & Post-Fix Checks
1. Open **Outlook Mobile** and pull down to refresh Inbox: confirm new messages send/receive cleanly.
2. Open **Teams Mobile**: confirm chats load and test a push notification.
3. Verify **Entra Sign-in Logs** & **Intune App Protection status** report healthy compliant check-in.

## Cross-Subject Escalation & Pivot Links
- **Device IS MDM-enrolled (Company Portal shows "Not Compliant" / missing profile):** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](./mdm-001-intune-compliance-sync.md)
- **User got a brand new iPhone/Android and Authenticator MFA prompts went to the old phone:** [id-003 — Entra ID MFA New Phone, Lost Authenticator, and Temporary Access Pass Recovery](../01_Identity_AD_Entra/id-003-entra-mfa-new-phone-and-tap-recovery.md)
- **Account shows password prompt loop across BOTH mobile and desktop Outlook:** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](../02_M365_Email_Collab/m365-001-outlook-auth-loop.md)

## Client Update Snippets (EN / FR)
- **EN:** We verified the Intune App Protection / broker requirements on your phone, refreshed your Outlook / Teams mobile account sign-in, and confirmed mail synchronization resumed cleanly. Could you pull down to refresh Outlook on your phone and confirm new messages arrive?
- **FR:** Nous avons vérifié l'application courtier de protection Intune (Authenticator / Portail d'entreprise) sur votre téléphone, réinitialisé la session mobile Outlook / Teams et rétabli la synchronisation. Pouvez-vous actualiser Outlook sur votre mobile et confirmer la réception des courriels ?
