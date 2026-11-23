---
id: win-010
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: updates_win11_licensing
title: Windows Slow Startup, Black Screen After Login, and Explorer.exe Freeze
tier: L1
keywords_en:
  - windows slow startup
  - black screen after login windows
  - black screen after login
  - taskbar missing explorer freeze
  - pc takes forever to boot
  - startup apps slowing pc
keywords_fr:
  - demarrage windows tres lent
  - ecran noir apres connexion windows
  - ecran noir apres connexion
  - barre des taches figee explorer
  - pc long a demarrer
  - applications demarrage ralentissent windows
error_codes:
  - EXPLORER_HANG
  - BLACK_SCREEN_LOGIN
tags:
  - windows_slow_startup
  - black_screen_explorer
os:
  - windows
environment:
  - local_endpoint
  - hybrid_ad
tools:
  - Task Manager
  - PowerShell
  - Event Viewer
  - msconfig
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - win-006
  - win-004
  - win-001
  - prt-003
  - win-013
  - win-014
linked_scripts:
  - 01_System/Get-StartupApplications.ps1
  - 01_System/Get-HighResourceProcesses.ps1
  - 01_System/Get-PendingRebootStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. When you log in, do you see a **black screen with a movable mouse cursor (`BLACK_SCREEN_LOGIN`)**, a **frozen desktop/taskbar (`EXPLORER_HANG`)**, or just **5+ minutes waiting on "Welcome"**?
2. Press **`Ctrl + Shift + Esc`**: does **Task Manager** appear over the black screen? *(Knowing Task Manager opens means Windows IS running — just `explorer.exe` or external display output stalled!)*
3. Are you connected to an **external monitor/dock (`[prt-003]`)** (the login/desktop might be rendering onto a sleeping/powered-off second screen!), or did Windows install updates last night?

### Initial Scope & Classification
- Distinguish **Display / Multi-Monitor projection trap** (`Win + P`), **Hung `explorer.exe` shell**, **Bloated Startup apps** (Teams/OneDrive/Adobe/Steam/browsers auto-launching on HDD/low RAM), and **Slow Group Policy / offline mapped drive wait at logon**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **For Black Screen with Mouse Cursor (`BLACK_SCREEN_LOGIN`):**
   - Press **`Win + Ctrl + Shift + B`** (restarts Windows video driver cleanly) and **`Win + P` -> `PC screen only`** (in case desktop went to a disconnected monitor!).
   - Press **`Ctrl + Shift + Esc`** to open **Task Manager -> More details** -> check if `Windows Explorer` is running (or frozen).
2. **Audit Enabled Startup Apps (GUI):** Open **Task Manager (`Ctrl + Shift + Esc`) -> Startup apps** -> sort by **Startup impact (`High`)**. Look for bloated updaters, personal cloud sync tools, or 10+ auto-starting apps!
3. **Check Disk Space (`win-011`) & Reboot Uptime:** Verify `C:` isn't full and check Task Manager **Performance -> CPU -> Up time** (Fast Startup keeps stale uptime for weeks!).

### L2 Technical Diagnostics
1. **Enumerate Startup Entries, Hung Processes, and Shell Error Events (read-only — or run `psstore://01_System/Get-StartupApplications.ps1`):**
   ```powershell
   Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location, User | Format-Table -AutoSize
   Get-WinEvent -FilterHashtable @{ LogName = 'Application'; ProviderName = 'Application Hang','Application Error'; StartTime = (Get-Date).AddDays(-2) } -MaxEvents 10 -ErrorAction SilentlyContinue |
       Where-Object { $_.Message -match "explorer\.exe|ShellExperienceHost|StartMenuExperienceHost" } |
       Select-Object TimeCreated, Id, Message
   ```
2. **Check GPO / Mapped Drive Login Delay (`Event ID 4000–5399`):** Inspect **Event Viewer -> `Applications and Services Logs -> Microsoft -> Windows -> GroupPolicy -> Operational`** if `"Applying user settings..."` takes 3+ minutes off-VPN.

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm whether `Ctrl + Shift + Esc` opens Task Manager, external monitors tested disconnected, list of `High` startup impact items, and boot vs post-login black screen timing.

## Deep-Dive Investigation (L3)
1. **Corrupted Shell Extension / AppReadiness Delay:** Third-party Explorer context-menu shell extensions (stale cloud drives, old archive tools) hang `explorer.exe` at login; inspect **AppReadiness** operational log when black screen lasts exactly 5–10 minutes after monthly Cumulative Updates!
2. **User Profile Corruption Check:** If black screen + desktop errors happen only for one domain profile while another local test profile logs in in 5 seconds, pivot to `[win-004]` or `[win-001]` (`SFC/DISM`).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Warn the user before restarting `explorer.exe` (open File Explorer windows will close, though unsaved Word/Excel apps stay open). Never disable critical EDR/AV/VPN services in Startup!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Restart `explorer.exe` on Black Screen / Frozen Taskbar)** Inside **Task Manager (`Ctrl + Shift + Esc`) -> File -> Run new task -> type `explorer.exe` -> Enter** (or right-click `Windows Explorer` -> **Restart**):
   ```powershell
   Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
   Start-Process explorer.exe
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Disable Unnecessary Startup Bloat)** In **Task Manager -> Startup apps**, disable non-essential consumer/bloat apps (`High` impact items not required for corporate security/VPN), then perform a full **Restart** (not Shut down) to clear Fast Startup state.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Repair Damaged Shell / System Files)** If `StartMenuExperienceHost` or `explorer.exe` crashes repeatedly (`Application Error`), run `DISM /Online /Cleanup-Image /RestoreHealth` and `sfc /scannow` (`[win-001]`).

## Verification & Post-Fix Checks
1. Perform a full **Restart** (`Start -> Power -> Restart`), time the boot-to-desktop duration, and verify desktop icons, Start Menu, and Taskbar respond immediately.
2. Confirm Task Manager shows healthy CPU/disk idle after login (`[win-006]`).

## Cross-Subject Escalation & Pivot Links
- **PC turns on to a pitch-black screen with zero cursor, no OEM logo, or blink/beep codes:** [win-013 — PC Turns On With Black Screen, No Display, or Fails POST (Beep / LED Blink Codes)](./win-013-pc-power-on-black-screen-no-post-display-triage.md)
- **Windows loops on Automatic Repair, fails to boot (`INACCESSIBLE_BOOT_DEVICE`), or reports no bootable device:** [win-014 — Windows Won't Boot Up, Automatic Repair Loop, No Bootable Device, and WinRE / BCD Recovery](./win-014-windows-wont-boot-automatic-repair-loop-and-bcd.md)
- **High CPU or 100% Disk usage continues permanently after desktop loads:** [win-006 — Windows High CPU, 100% Disk Usage, and Memory Leak Triage (Event 129 / 153 / 2004)](./win-006-windows-high-cpu-100-disk-and-memory-leak.md)
- **Black screen stems from external monitor / USB-C dock output mismatch:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](../05_Printers_Devices/prt-003-usbc-dock-monitors-not-detected.md)
- **Corrupted user profile triggers missing desktop after slow login:** [win-004 — Windows Temporary User Profile Recovery (Event ID 1511 / 1515)](./win-004-windows-temporary-profile-recovery.md)
- **Pending or corrupted Windows Update triggers black screen AppReadiness hang:** [win-001 — Windows Update Failure and Component Store Corruption](./win-001-windows-update-corruption.md)

## Client Update Snippets (EN / FR)
- **EN:** We restarted the hung Windows Explorer shell, disabled unnecessary high-impact startup programs on `PC-LAB-01`, and performed a clean reboot to improve startup speed. Could you confirm your desktop and taskbar now load quickly and normally?
- **FR:** Nous avons relancé l'explorateur Windows (`explorer.exe`), désactivé les applications non essentielles ralentissant le démarrage sur `PC-LAB-01` et effectué un redémarrage complet. Pouvez-vous confirmer que votre bureau s'affiche maintenant rapidement et sans blocage ?
