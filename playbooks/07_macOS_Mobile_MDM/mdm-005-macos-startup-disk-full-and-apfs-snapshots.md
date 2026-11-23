---
id: mdm-005
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: macos_disk_recovery
title: Beginner macOS Startup Disk Full, System Data Bloat, and APFS Snapshots
tier: L2
keywords_en:
  - mac startup disk full
  - macos system data huge
  - mac disk space full
  - apfs local snapshots mac
  - purgeable space macos
keywords_fr:
  - disque demarrage sature mac
  - donnees systeme volumineuses mac
  - espace disque plein macos
  - instantanes apfs time machine
  - vider cache stockage mac
error_codes:
  - ENOSPC
  - APFS_PURGEABLE
tags:
  - macos_disk_full
  - apfs_snapshots
os:
  - macos
environment:
  - local_endpoint
  - intune
tools:
  - System Settings
  - Terminal
  - diskutil
  - tmutil
risk_level: medium
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - m365-005
  - mdm-003
  - mdm-006
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Did you see `"Your startup disk is almost full"`, fail a **macOS update**, or notice **100+ GB under `"System Data"`** in Storage settings (`ENOSPC`)?
2. Do you have **old iPhone/iPad local backups**, lots of **`.dmg`/video files in Downloads / Trash**, or huge **OneDrive / SharePoint synced folders** set to *Keep on Device*?
3. **Important Beginner Warning:** Never randomly delete files inside `~/Library` or `Macintosh HD/System` — always check folder sizes first!

### Initial Scope & Classification
- Remember macOS **Finder -> Get Info** shows **Available = Free + Purgeable**, whereas **macOS updates and installers need actual non-purgeable Free space**!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — macOS System Settings GUI)
1. **Check Storage Breakdown in GUI (Beginner Step-by-Step):**
   - Click **` Apple menu -> System Settings -> General -> Storage`**.
   - Click the **`(i)`** info icon next to **Applications**, **Documents**, **iOS Files** (old iPhone backups often eat 50+ GB!), and **Trash** (remember: emptying Trash is often forgotten!).
   - Click the **OneDrive cloud icon** top-right -> **Settings/Preferences** -> check if **Files On-Demand** is turned on so large SharePoint folders aren't stored locally!

### L2 Technical Diagnostics
1. **Inspect True APFS Space, Local Time Machine Snapshots, and Largest Folders in Terminal (`⌘ + Space` -> `Terminal`, read-only):**
   ```bash
   df -h /System/Volumes/Data
   diskutil apfs list
   tmutil listlocalsnapshots /
   du -sh ~/Downloads ~/Library/Caches/* ~/Library/Application\ Support/MobileSync/Backup 2>/dev/null | sort -hr | head -n 15
   ```
   *(Common culprits: `com.apple.TimeMachine` local snapshots waiting for an unplugged backup drive, Outlook/Teams/Xcode/Docker caches, or iPhone backups in `MobileSync/Backup`.)*

## Deep-Dive Investigation (L3)
1. **System-Wide `/Library` & OneDrive Cache Bloat:** Check `/Library/Updates`, `/private/var/folders`, and `~/Library/Group Containers/UBF8T346G9.OneDriveStandaloneSync` (`OneDrive Files On-Demand` pinning entire SharePoint libraries offline!).
2. **Broken APFS Snapshot Accumulation (`APFS_PURGEABLE`):** If Time Machine is enabled without plugging in the external drive for weeks, hourly local APFS snapshots pile up and lock storage until thinned.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Safe GUI Cleanup First:**
   - Empty **Trash** (right-click Trash in Dock -> **Empty Trash**).
   - Remove old installers (`.dmg` / `.pkg`) in **Downloads** and delete verified obsolete iPhone backups under **System Settings -> General -> Storage -> iOS Files**.
   - In **OneDrive** (cloud icon in top-right menu bar -> **Preferences -> Free up disk space** / **Files On-Demand**), dehydrate huge unused synced folders back to cloud-only.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Thin Local APFS Time Machine Snapshots Safely** (requires admin if deleting specific snapshots; `thinlocalsnapshots` requests macOS to reclaim e.g. 20 GB cleanly without breaking OS boot):
   ```bash
   sudo tmutil thinlocalsnapshots / 20000000000 4
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Clear Safe User Browser / App Caches ONLY** (quit affected apps first via `⌘ + Q` — do NOT delete `~/Library/Application Support` or `Keychains`!):
   ```bash
   rm -rf ~/Library/Caches/com.microsoft.teams2/* ~/Library/Caches/Google/Chrome/*
   ```

## Verification & Post-Fix Checks
1. Run `df -h /System/Volumes/Data` and confirm at least **20–25 GB actual free capacity** (`Avail` column).
2. Re-open **` -> System Settings -> General -> Storage`** and confirm the storage warning disappears and macOS updates/apps run smoothly.

## Cross-Subject Escalation & Pivot Links
- **Hidden OneDrive Files On-Demand cache or Outlook Mac profile consumes tens of gigabytes:** [m365-005 — OneDrive Sync Stuck Processing Changes and SharePoint Path Limit Errors](../02_M365_Email_Collab/m365-005-onedrive-sync-stuck-and-sharepoint-path-limit.md)
- **Low APFS free space degrades Finder responsiveness and causes spinning beachballs:** [mdm-003 — Beginner macOS Troubleshooting Guide — Navigation, Force Quit, and Slow Mac](./mdm-003-macos-beginner-navigation-force-quit-and-slow-mac.md)
- **macOS upgrade fails or loops on low disk requiring Recovery Mode Disk Utility First Aid:** [mdm-006 — Beginner macOS Recovery Mode, Boot Failure, and Disk Utility First Aid Guide](./mdm-006-macos-recovery-mode-boot-failure-and-first-aid.md)

## Client Update Snippets (EN / FR)
- **EN:** We reclaimed disk space on your Mac by thinning local APFS snapshots and clearing safe application caches/downloads. You now have healthy free storage — please let us know if any warning returns.
- **FR:** Nous avons libéré de l'espace disque sur votre Mac en purgeant les instantanés APFS locaux et les caches applicatifs sécuritaires. Votre disque dispose maintenant d'un espace libre sain ; veuillez nous aviser si l'alerte réapparaît.
