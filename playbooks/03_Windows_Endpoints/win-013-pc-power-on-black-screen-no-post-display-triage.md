---
id: win-013
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: boot_bitlocker_bsod
title: PC Turns On With Black Screen, No Display, or Fails POST (Beep / LED Blink Codes)
tier: L1
keywords_en:
  - black screen
  - pc black screen on startup
  - pc turns on but screen is black
  - no signal monitor boot
  - pc no post beep codes
  - screen stays black no logo
keywords_fr:
  - ecran noir demarrage
  - ecran noir pc
  - pc s'allume mais ecran noir
  - aucun signal ecran ordinateur
  - ecran noir aucun logo windows
error_codes:
  - NO_POST
  - NO_SIGNAL
  - BLACK_SCREEN_BOOT
  - POST_BEEP_LED
tags:
  - pc_black_screen_nopost
  - post_blink_codes
os:
  - windows
environment:
  - local_endpoint
tools:
  - External Monitor / HDMI-DP Cable
  - Keyboard LEDs (Caps Lock)
  - OEM Diagnostic LEDs / Beep Guide
  - PowerShell
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - win-010
  - win-012
  - prt-003
  - win-014
linked_scripts:
  - 04_Devices/Get-DisplayTopology.ps1
  - 01_System/Get-HardwareInventory.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are the **power LED, keyboard backlight, or cooling fans turning ON**, OR is the PC 100% lifeless with zero lights/sounds (if totally dead -> jump to `[win-012]`)?
2. On the black screen, do you see a **movable white mouse cursor** or did it turn black **right after entering your Windows password** (if mouse cursor/post-login -> jump to `[win-010]`)?
3. If using a laptop connected to monitors or a dock (`[prt-003]`): does the **built-in laptop screen work when the lid is open and the dock is unplugged**, or is the built-in panel black right from pressing power (no Dell/HP/Lenovo logo at all)?
4. Do you hear any **beep patterns** from the PC, or see the **power LED / charging LED / Caps Lock key blinking** in a repeating amber/white pattern?

### Initial Scope & Classification
- Separate three very different causes that all look like a "black screen" to end users:
  1. **PC Passed POST, Display Output Wrong / Backlight Dead (`NO_SIGNAL`):** Caps Lock LED toggles normally; Windows booted onto an off-input monitor, disconnected dock, wrong GPU port, or dead laptop LCD backlight!
  2. **PC Failed POST Before OS (`NO_POST` / `POST_BEEP_LED`):** Fans spin but keyboard `Caps Lock` never responds and blink/beep codes indicate RAM, BIOS NVRAM, CPU, or motherboard failure.
  3. **Post-Login Black Screen (`[win-010]`):** Cursor visible (`Ctrl+Shift+Esc` works).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Zero CLI Tests That Solve 75% of Black Screens)
1. **Run the Golden L1 `Caps Lock` POST Test (Wait 30 Seconds After Power-On):**
   - Press **`Caps Lock`** (or `Num Lock` on a wired USB keyboard) several times:
     - **If the `Caps Lock` LED turns ON and OFF normally:** **Great news!** The motherboard, CPU, RAM, and Windows passed POST — the PC IS awake, just not showing an image on the right screen!
     - **If the `Caps Lock` LED stays completely dead / frozen:** The PC is hung **pre-boot (`NO_POST`)** — record any blink/beep codes immediately!
2. **Unplug Docks, USB Devices & Check Desktop GPU Ports:**
   - Unplug USB-C docks (`[prt-003]`), external monitors, and extra USB drives; lift the laptop lid and check the built-in display alone.
   - On **desktop towers with a dedicated graphics card**, verify the HDMI/DisplayPort cable is plugged into the **lower horizontal GPU ports**, NOT the upper motherboard video ports (which are disabled whenever an add-in GPU is installed!).
   - Press the physical **Input / Source** button on external monitors and confirm the monitor has AC power (solid white/blue LED vs amber standby `No Signal`).
3. **Phone Flashlight LCD Backlight Test (Laptops):**
   - If `Caps Lock` toggles on a laptop whose built-in screen looks pitch black, shine a smartphone flashlight directly against the LCD glass at an angle: if you can faintly see the login screen/clock, the **screen backlight/inverter failed** (plugging an external HDMI monitor directly into the laptop will work immediately so the user can keep working!).
4. **Record Exact OEM Blink / Beep Diagnostic Pattern:**
   - Count repeating amber/white power light flashes (e.g., Dell `2 Amber / 3 White` or `2 Amber / 4 White` = No RAM / Memory failure; `2 Amber / 1 White` = CPU; `3 Amber / 1 White` = CMOS coin battery; HP Caps Lock blink codes; Lenovo ThinkPad 4-tone melody beeps -> decode with Lenovo PC Diagnostics smartphone app!).

### L2 Technical Diagnostics
1. **Test Blind Keyboard Display Recovery & External Video Direct Connection:**
   - When `Caps Lock` toggles on a running black screen, test **`Win + Ctrl + Shift + B`** (restarts Windows display driver — listen for a faint chime/beep!) and **`Win + P` -> Down Arrow -> Enter** (`Duplicate`) to force display onto the primary monitor.
   - Plug a known-good monitor + HDMI cable **directly** into the PC (no USB-C adapter) and test hitting `F2`/`F10`/`F12` at boot to see if BIOS text renders outside Windows (proves Windows GPU driver crash vs hardware LCD failure!).
2. **Once Temporary External Video Works, Audit Display Topology & GPU Driver Faults (read-only — or run `psstore://04_Devices/Get-DisplayTopology.ps1`):**
   ```powershell
   Get-CimInstance Win32_VideoController | Select-Object Name, Status, DriverVersion, DriverDate
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; StartTime = (Get-Date).AddDays(-2) } -MaxEvents 20 -ErrorAction SilentlyContinue |
       Where-Object { $_.ProviderName -match 'Display|nvlddmkm|igfx|amdkmdag|BasicDisplay' -or $_.Id -eq 4101 } |
       Select-Object TimeCreated, ProviderName, Id, Message
   ```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm whether `Caps Lock` LED toggles, whether external HDMI monitor directly attached shows BIOS/Windows, whether flashlight test showed faint text, exact OEM amber/white blink or beep count, and desktop GPU vs motherboard port check.

## Deep-Dive Investigation (L3)
1. **Unseated/Failed SODIMM RAM or Corrupted UEFI BIOS Update:** Windows Update / Intune BIOS firmware capsules (`Dell/Lenovo/HP BIOS Update`) can leave NVRAM/MRC memory training hung at black screen for 2–4 minutes (never power off mid-BIOS flash!) or require OEM BIOS Crisis Recovery (`Ctrl+Esc` / `Win+B`) / CMOS drain.
2. **Event ID `4101` (`Display driver stopped responding`):** Repeated TDR timeouts in `nvlddmkm` / `igfx` / `amdkmdag` paired with OEM dock DisplayPort MST firmware often blank screens on wake (`[prt-003]` / `[win-003]`).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Ask the user to save work blindly only if Windows is running; if fans are loud and a **BIOS firmware update screen** was just in progress, wait at least **5–10 minutes** before forcing power off!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Hard Power Cycle + 30-Second Flea-Power Drain)**
   - Hold the physical power button for **10–15 seconds** until fans/LEDs turn completely off.
   - Unplug AC power, USB-C dock, and all USB devices (`PC-LAB-01` isolated); hold power **30 seconds** to drain capacitors.
   - Reconnect **ONLY AC power + one direct display** and power back on (wait up to 2 minutes in case memory training runs).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Graphics Driver Reset & OEM GPU/BIOS Update)** Once display appears on built-in or direct HDMI monitor (or triggered blindly while `Caps Lock` responds), press **`Win + Ctrl + Shift + B`**, verify display driver resets, then install the latest OEM **Intel/AMD/NVIDIA Graphics + BIOS + Dock Firmware** (`[prt-003]` / `[win-003]`) after verifying the **48-digit BitLocker Recovery Key (`[win-002]`)** is escrowed!
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Hardware BIOS Recovery, RAM Reseat, or Warranty Repair)** For confirmed `NO_POST` hardware blink/beep codes:
   - Try OEM crisis BIOS recovery (Dell: unplug AC -> hold **`Ctrl + Esc`** while plugging AC; HP: hold **`Win + B` + Power** 3 seconds) ONLY per vendor instructions.
   - On authorized serviceable desktops, discharge static, pull AC cord, and test booting with a single reseated RAM stick (or clear CMOS). If POST still fails or LCD panel backlight is dead, dispatch OEM warranty repair and connect a temporary external monitor so `jsmith@example.com` can continue working!

## Verification & Post-Fix Checks
1. Confirm the OEM splash logo (`Dell`/`HP`/`Lenovo`) and Windows lock screen render cleanly on the built-in screen and external display across a full restart.
2. Verify **Device Manager -> Display adapters** shows the OEM graphics driver active (not `Microsoft Basic Display Adapter`) and zero new `Event ID 4101` errors occur (`[win-003]`).

## Cross-Subject Escalation & Pivot Links
- **Black screen shows a movable mouse cursor or happens ONLY after Windows password login:** [win-010 — Windows Slow Startup, Black Screen After Login, and Explorer.exe Freeze](./win-010-slow-startup-black-screen-after-login-and-explorer-freeze.md)
- **PC shows zero LEDs, zero fans, and zero power when pressing the power button:** [win-012 — Dead PC, Won't Turn On, and No Power Hardware Triage (Desktop & Laptop)](./win-012-pc-wont-turn-on-dead-pc-no-power-triage.md)
- **Laptop built-in screen works, but external monitors on a USB-C dock are blank or flickering:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](../05_Printers_Devices/prt-003-usbc-dock-monitors-not-detected.md)
- **PC shows the OEM logo or spinning circle then hits Automatic Repair / boot failure:** [win-014 — Windows Won't Boot Up, Automatic Repair Loop, No Bootable Device, and WinRE / BCD Recovery](./win-014-windows-wont-boot-automatic-repair-loop-and-bcd.md)

## Client Update Snippets (EN / FR)
- **EN:** We isolated the black-screen issue on `PC-LAB-01` by testing POST (`Caps Lock`), removing external dock connections, performing a power-controller reset, and refreshing display output / drivers (or arranging hardware service if POST/panel hardware failed). Could you confirm whether your display now shows the login screen cleanly?
- **FR:** Nous avons diagnostiqué l'écran noir sur `PC-LAB-01` en vérifiant le POST (`Verr Maj`), en débranchant la station d'accueil, en effectuant une réinitialisation électrique et en rétablissant la sortie d'affichage / les pilotes (ou en lançant une prise en charge matérielle si le panneau ou le POST est en cause). Pouvez-vous confirmer si l'affichage fonctionne maintenant ?
