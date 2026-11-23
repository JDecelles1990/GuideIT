---
id: mdm-006
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: macos_disk_recovery
title: Beginner macOS Recovery Mode, Boot Failure, and Disk Utility First Aid Guide
tier: L2
keywords_en:
  - mac recovery mode won't boot
  - mac flashing question mark folder
  - mac prohibited symbol boot
  - disk utility first aid mac
  - reinstall macos without erasing data
keywords_fr:
  - mode recuperation mac ne demarre pas
  - dossier point interrogation clignotant mac
  - symbole interdit demarrage mac
  - sos utilitaire de disque mac
  - reinstaller macos sans effacer donnees
error_codes:
  - QUESTION_MARK_FOLDER
  - PROHIBITED_SYMBOL
tags:
  - macos_recovery_boot
  - macos_disk_first_aid
os:
  - macos
environment:
  - local_endpoint
  - intune
tools:
  - macOS Recovery
  - Disk Utility
  - Terminal
  - diskutil
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - mdm-005
  - mdm-002
  - mdm-003
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. What **exact icon or screen** appears when turning on the Mac: **Flashing `?` Folder (`QUESTION_MARK_FOLDER`)**, **Circle with Slash `⊘` (`PROHIBITED_SYMBOL`)**, **Padlock icon**, or **Apple logo stuck loading forever**?
2. Is this Mac an **Apple Silicon (`M1 / M2 / M3 / M4` — ~2020+)** or older **Intel Mac**? *(Hold **Power button** for Silicon vs Hold **`⌘ + R`** for Intel!)*
3. Did a **macOS software update**, sudden battery shutdown, or low storage (`[mdm-005]`) happen right before it failed to boot?
4. Do we have **OneDrive / Time Machine backups** and the **FileVault Recovery Key (`intune.microsoft.com`)** handy?

### Initial Scope & Classification
- Capture the boot screen symbol + Apple chip type (`Silicon` vs `Intel`) first so you hold the right recovery key combination.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Safe Recovery Boot & Key Lookup)
1. **Boot Into macOS Recovery & Look Up FileVault Key in Intune GUI:**
   - **Apple Silicon:** Shut down -> hold **Power button** ~10 sec -> `Options` -> `Continue`. **Intel:** Power on -> immediately hold **`⌘ + R`**.
   - If asked for FileVault unlock and the user's password fails, click **`Forgot all passwords?`** -> fetch the **FileVault Personal Recovery Key** in **Intune Admin Center -> Devices -> `Device` -> Recovery keys**! (If it asks for **MDM Recovery Lock**, check **Intune -> Devices -> `Device` -> Hardware/Monitor**!)
2. **Ensure AC Power & Wi-Fi:** Keep MacBook plugged into charger and check Wi-Fi menu top-right of Recovery screen before trying Disk Utility First Aid!

### L2 Technical Diagnostics
1. **Verify Disk & Volume Health Read-Only (inside Recovery -> Utilities -> Terminal, or booted macOS):**
   ```bash
   diskutil list
   diskutil verifyVolume /System/Volumes/Data
   ```
3. **Check whether Time Machine / OneDrive backups exist** before performing any disk repair or macOS reinstall.

## Deep-Dive Investigation (L3)
1. **APFS Container / Preboot Snapshot Corruption:** Inside Recovery Terminal, check `diskutil apfs list` to confirm both **`Macintosh HD`** (read-only signed system volume) and **`Macintosh HD - Data`** are present and mountable (`Unlocked`).
2. **MDM Recovery Lock (Apple Silicon) / Activation Lock:** On Intune ABM/ADE-enrolled Macs, if Recovery asks for an IT Recovery Lock password or Apple ID Activation Lock, retrieve the **Recovery Lock Password** or **Activation Lock Bypass Code** from **Intune Admin Center -> Devices -> `Device` -> Monitor / Hardware**!

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Run Disk Utility First Aid (Non-Destructive Repair):**
   - Inside **macOS Recovery**, select **`Disk Utility` -> `Continue`**.
   - Click **`View` (top-left of Disk Utility window) -> `Show All Devices`**! *(Critical beginner step — without this, Disk Utility hides the physical container and parent disk!)*
   - Run **`First Aid`** from bottom-up order:
     1. `Macintosh HD - Data` -> click **First Aid** -> **Run**
     2. `Macintosh HD` -> click **First Aid** -> **Run**
     3. `Container disk...` -> click **First Aid** -> **Run**
     4. Top physical SSD (`APPLE SSD...`) -> click **First Aid** -> **Run**
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **In-Place Reinstall macOS (Repairs OS System Files WITHOUT Erasing User Files or Apps!):**
   - Connect to Wi-Fi (top-right Wi-Fi icon in Recovery menu bar) or Ethernet.
   - Quit Disk Utility -> select **`Reinstall macOS <Version>`** -> **Continue** -> select **`Macintosh HD`** -> follow prompts.
   - *(NEVER open Disk Utility and click **`Erase`** unless explicitly approved to wipe the Mac completely!)*

## Verification & Post-Fix Checks
1. Allow the Mac to reboot into the normal macOS login screen (`jsmith@example.com`) without `?` or `⊘` symbols.
2. Confirm user files, Company Portal MDM sync (`[mdm-001]`), and FileVault (`fdesetup status`) remain intact and healthy.

## Cross-Subject Escalation & Pivot Links
- **Startup disk exhaustion / snapshot corruption prevented macOS upgrade boot:** [mdm-005 — Beginner macOS Startup Disk Full, System Data Bloat, and APFS Snapshots](./mdm-005-macos-startup-disk-full-and-apfs-snapshots.md)
- **FileVault startup unlock issue or Keychain desync after password reset:** [mdm-002 — macOS Login Keychain Password Loop and Platform SSO / FileVault Desync](./mdm-002-macos-keychain-loop-and-platform-sso.md)
- **Beginner macOS desktop navigation and Safe Mode checks once Recovery succeeds:** [mdm-003 — Beginner macOS Troubleshooting Guide — Navigation, Force Quit, and Slow Mac](./mdm-003-macos-beginner-navigation-force-quit-and-slow-mac.md)

## Useful Links & External Tools
- **[Apple Official Startup Key Combinations & Recovery](https://support.apple.com/en-us/102603)** — Reference guide for Apple Silicon (hold Power button) vs. Intel (`⌘+R` / Safe Mode / Diagnostics) boot key sequences.
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Retrieve FileVault Personal Recovery Keys and Mac Recovery Lock passwords for enrolled devices.

## Client Update Snippets (EN / FR)
- **EN:** We guided you into macOS Recovery, repaired the APFS startup volume using Disk Utility First Aid (and/or completed an in-place macOS system repair without erasing your files), and confirmed the Mac boots normally. Could you sign in and verify your apps and files look intact?
- **FR:** Nous avons démarré le Mac en mode Récupération macOS, réparé le volume APFS avec SOS d'Utilitaire de disque (et/ou réinstallé le système sans effacer vos données) et vérifié le démarrage normal. Pouvez-vous ouvrir votre session et confirmer que tout est intact ?
