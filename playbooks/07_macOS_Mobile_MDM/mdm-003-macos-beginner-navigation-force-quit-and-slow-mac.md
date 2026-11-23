---
id: mdm-003
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: macos_basics_apps_shares
title: Beginner macOS Troubleshooting Guide — Navigation, Force Quit, and Slow Mac
tier: L1
keywords_en:
  - mac spinning beachball force quit
  - macos beginner guide
  - mac running slow freeze
  - how to open activity monitor mac
  - mac safe mode boot
keywords_fr:
  - mac lent roue multicolore
  - guide debutant macos
  - forcer quitter application mac
  - moniteur activite mac
  - mode sans echec mac
error_codes:
  - SPINNING_BEACHBALL
  - FORCE_QUIT
tags:
  - macos_beginner_basics
  - macos_slow_freeze
os:
  - macos
environment:
  - local_endpoint
  - intune
tools:
  - Spotlight
  - Activity Monitor
  - Terminal
  - Finder
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - mdm-005
  - mdm-004
  - mdm-006
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is **only ONE specific app frozen** (spinning rainbow beachball, `(Not Responding)`), OR is the **entire Mac sluggish / fans loud / freezing across everything**?
2. When was the **last time you actually clicked ` -> Restart...`** (many MacBook users only close the lid for weeks/months without rebooting!)?
3. Are you connected to an external dock/4K monitor (`[prt-003]`), or running low on Mac storage (`[mdm-005]`)?

### Quick Windows-to-Mac Cheatsheet (for Technicians New to Apple)
- **Command key (`⌘`)** = Windows `Ctrl` (Copy `⌘+C`, Paste `⌘+V`, Quit app `⌘+Q`).
- **Option key (`⌥`)** = Windows `Alt`.
- **Spotlight (`⌘ + Space`)** = Windows Start Search (type any app name like **`Terminal`** or **`Activity Monitor`** and press Enter!).
- **Finder** (blue smiley face in bottom Dock) = Windows File Explorer.
- **System Settings** (top-left **` Apple menu -> System Settings`**) = Windows Settings / Control Panel.
- **Activity Monitor** = Windows Task Manager.
- **Note:** Clicking the red `✕` circle on a Mac window closes the window, **NOT** the app — press **`⌘ + Q`** (or right-click Dock icon -> **Quit**) to fully close an app!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Activity Monitor GUI, Zero Terminal!)
1. **Open Activity Monitor (GUI — zero Terminal needed):**
   - Press **`⌘ + Space`**, type **`Activity Monitor`**, press **Return**.
   - Click the **CPU** tab and click **`% CPU`** header so highest consumers sort to the top (look for apps labeled `(Not Responding)` in red).
   - Click the **Memory** tab and check **Memory Pressure** graph at the bottom (**Green** = healthy; **Yellow/Red** = RAM exhausted / heavy swap!).
2. **Check Apple Menu (` -> About This Mac` & Storage):** Check whether **Startup Disk** is nearly full (`< 15 GB free` slows macOS severely -> `[mdm-005]`).

### L2 Technical Diagnostics
1. **Run quick read-only system checks in Terminal (`⌘ + Space` -> type `Terminal` -> Return):**
   ```bash
   sw_vers
   uname -m
   uptime
   top -l 1 -n 10 -o cpu
   vm_stat
   pmset -g therm
   ```
   *(Note: `uname -m` shows `arm64` for **Apple Silicon M1/M2/M3/M4** vs `x86_64` for older **Intel** Macs — this matters for Recovery/Safe Mode steps!)*

## Deep-Dive Investigation (L3)
1. **Login Items & Background Daemons:** On macOS Ventura/Sonoma/Sequoia, go to **` Apple menu -> System Settings -> General -> Login Items & Extensions`** to spot duplicate cloud sync clients, old antivirus agents, or broken background updaters looping CPU.
2. **Spotlight (`mds_stores`) or Time Machine Re-Indexing:** Temporary high CPU right after a macOS update often comes from `mds_stores` indexing; verify disk space is not critically low (`[mdm-005]`).
3. **Thermal Throttling (`CPU_Speed_Limit < 100` in `pmset -g therm`):** Blocked vents, soft surfaces, or heavy dock charging on Intel MacBooks throttle CPU to prevent overheating.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Force Quit a Frozen App (`FORCE_QUIT`):**
   - Press **`⌘ + ⌥ + Esc`** (Command + Option + Escape — Mac equivalent of `Ctrl+Alt+Del` Task Manager), select the `(Not Responding)` app, and click **Force Quit**.
   - *(Or in **Activity Monitor**, select the process -> click the stop **`⊗`** icon in top toolbar -> **Force Quit**.)*
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Restart the Mac Cleanly (Important: Macs are often left asleep for weeks!):**
   - Click **` Apple menu -> Restart...`** and uncheck `"Reopen windows when logging back in"` so hung apps don't immediately re-open.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Boot into macOS Safe Mode** to isolate third-party startup extensions/fonts:
   - **Apple Silicon (`arm64`):** Shut down completely -> press and **HOLD the Power button** until `"Loading startup options"` appears -> select `Macintosh HD` -> **hold `Shift`** and click **`Continue in Safe Mode`**.
   - **Intel (`x86_64`):** Click Restart -> immediately **hold `Shift`** until the login window appears.

## Verification & Post-Fix Checks
1. Confirm **Activity Monitor -> CPU** idle sits calmly and **Memory Pressure** stays **Green**.
2. Have `jsmith@example.com` open their working apps and verify responsive scrolling and zero spinning beachball pauses.

## Cross-Subject Escalation & Pivot Links
- **Spinning beachball slowdown caused by APFS snapshots or bloated System Data disk exhaustion:** [mdm-005 — Beginner macOS Startup Disk Full, System Data Bloat, and APFS Snapshots](./mdm-005-macos-startup-disk-full-and-apfs-snapshots.md)
- **App hangs or cannot save files due to Gatekeeper block or missing TCC privacy consent:** [mdm-004 — Beginner macOS Gatekeeper App Blocked and Privacy (TCC) Permissions Guide](./mdm-004-macos-gatekeeper-app-blocked-and-privacy-permissions.md)
- **Mac crashes continuously or fails booting past Apple logo to macOS desktop:** [mdm-006 — Beginner macOS Recovery Mode, Boot Failure, and Disk Utility First Aid Guide](./mdm-006-macos-recovery-mode-boot-failure-and-first-aid.md)

## Client Update Snippets (EN / FR)
- **EN:** We identified the frozen / high-resource process on your Mac using Activity Monitor, force-closed the stalled app, and verified normal CPU and memory health after restarting. Could you test your workflow and confirm the Mac feels responsive?
- **FR:** Nous avons identifié le processus bloqué sur votre Mac via le Moniteur d'activité, fermé l'application figée et vérifié l'état du processeur et de la mémoire après redémarrage. Pouvez-vous tester vos applications et confirmer que votre Mac est fluide ?
