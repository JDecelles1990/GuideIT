---
id: mdm-004
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: macos_basics_apps_shares
title: Beginner macOS Gatekeeper App Blocked and Privacy (TCC) Permissions Guide
tier: L1
keywords_en:
  - macos app blocked developer
  - developer cannot be verified mac
  - mac teams screen sharing blocked
  - mac privacy security allow app
  - mac microphone permission denied
keywords_fr:
  - application bloquee developpeur non verifie mac
  - macos partage ecran teams bloque
  - confidentialite securite mac autoriser
  - mac micro camera refuse
  - gatekeeper macos bloque
error_codes:
  - GATEKEEPER_BLOCK
  - TCC_DENIED
tags:
  - macos_gatekeeper_blocked
  - macos_tcc_permissions
os:
  - macos
environment:
  - local_endpoint
  - intune
tools:
  - System Settings
  - Terminal
  - Intune Admin Center
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - mdm-001
  - mdm-003
  - sec-002
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is a newly downloaded **app refusing to open (`"Apple cannot check it for malicious software"` / `GATEKEEPER_BLOCK`)**, OR is **Teams / Zoom / Remote Support unable to share your screen, hear mic, or control mouse (`TCC_DENIED`)**?
2. Did you download the app from an **official trusted software vendor** (never bypass security for random internet downloads!), and did you drag it into **`Applications`** (rather than running directly from Downloads or `.dmg`)?
3. When we look at **Privacy & Security**, are the toggles grayed out with a lock icon / **"Managed by organization"** banner?

### Initial Scope & Classification
- Check whether **Gatekeeper (`Open Anyway`)** or **macOS Privacy Permissions (`Microphone` / `Screen Recording` / `Accessibility`)** are blocking the workflow.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Beginner GUI Steps)
1. **Check Where the App Lives (`Finder -> Applications`):** Confirm `jsmith@example.com` isn't double-clicking the app straight inside the **`Downloads`** folder or a mounted **`.dmg` installer** — macOS permissions break if apps aren't moved into **`Applications`**!
2. **Inspect Privacy & Security Settings (` -> System Settings -> Privacy & Security`):**
   - If blocked by Gatekeeper: scroll to bottom under **Security** to see if an **`Open Anyway`** button appeared for the target app.
   - If Teams / Zoom / RMM fails: inspect **Microphone**, **Camera**, **Screen & System Audio Recording**, and **Accessibility** toggles!

### L2 Technical Diagnostics
1. **Inspect Gatekeeper Status & Quarantine Attribute in Terminal (`⌘ + Space` -> `Terminal`, read-only):**
   ```bash
   spctl --status
   xattr -l "/Applications/TargetApp.app" 2>/dev/null || true
   codesign -dv --verbose=2 "/Applications/TargetApp.app" 2>&1 | head -n 15
   ```
   *(Look for `com.apple.quarantine` — macOS tags downloaded `.dmg`/`.app` files with quarantine until approved.)*

## Deep-Dive Investigation (L3)
1. **Intune PPPC / TCC Profile Override:** Standard users on managed Macs cannot toggle **Screen Recording** or **Accessibility** unless an Intune **Privacy Preferences Policy Control (PPPC)** profile either grants `AllowStandardUserToSetSystemService` (for Screen Recording!) or pre-approves the app's Bundle ID + Code Requirement.
2. **App Run Directly from `.dmg` or Downloads Folder:** Beginners often double-click an app inside the mounted `.dmg` installer or `Downloads` instead of dragging it into `/Applications` — TCC permissions break or reset on reboot until moved into **`/Applications`**!

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Approve Verified App via GUI (Safest):**
   - Ensure the `.app` was dragged into **`Applications`** (not running from Downloads/DMG).
   - Attempt to open the app once -> dismiss popup (`Done`) -> open **` -> System Settings -> Privacy & Security`** -> scroll down -> click **`Open Anyway`** -> enter Mac password/Touch ID -> click **`Open`**.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Grant Microphone / Screen Sharing / Accessibility Permissions:**
   - Open **` -> System Settings -> Privacy & Security`** -> open **Microphone**, **Camera**, **Screen & System Audio Recording**, and (for remote tools) **Accessibility** -> flip the toggle **ON** for the trusted app -> click **`Quit & Reopen`** when macOS prompts!
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Terminal Quarantine Removal (ONLY for verified, signed internal/LOB apps when GUI `Open Anyway` is absent):**
   ```bash
   xattr -dr com.apple.quarantine "/Applications/VerifiedApp.app"
   ```
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **TCC permission toggle is stuck or missing**, reset ONLY that specific permission category (example: `ScreenCapture` for Microsoft Teams — user will be re-prompted cleanly next launch):
   ```bash
   tccutil reset ScreenCapture com.microsoft.teams2
   ```

## Verification & Post-Fix Checks
1. Completely quit (`⌘ + Q`) and reopen the target app (`Microsoft Teams`, `Zoom`, or RMM agent).
2. Test sharing a screen, speaking into the mic, or clicking remotely to verify macOS allows the action with zero security blocks.

## Cross-Subject Escalation & Pivot Links
- **TCC Privacy Preferences Policy Control (PPPC) or Gatekeeper rules are locked via Intune MDM:** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](./mdm-001-intune-compliance-sync.md)
- **Beginner Activity Monitor, Finder, and System Settings navigation steps on macOS:** [mdm-003 — Beginner macOS Troubleshooting Guide — Navigation, Force Quit, and Slow Mac](./mdm-003-macos-beginner-navigation-force-quit-and-slow-mac.md)
- **Compare Windows Defender ASR / SmartScreen application blocking workflows:** [sec-002 — Microsoft Defender ASR Rule or Antivirus Blocking Legitimate LOB App or Macro](../06_Security_Access/sec-002-defender-asr-block-and-false-positive.md)

## Client Update Snippets (EN / FR)
- **EN:** We approved the verified application in macOS Privacy & Security settings and enabled the required Microphone / Screen Recording permissions. Please restart the app and confirm screen sharing and audio work normally.
- **FR:** Nous avons autorisé l'application vérifiée dans Réglages Système -> Confidentialité et sécurité sur votre Mac et activé les accès Micro / Enregistrement d'écran requis. Pouvez-vous relancer l'application et confirmer que tout fonctionne ?
