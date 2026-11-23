---
id: win-012
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: boot_bitlocker_bsod
title: Dead PC, Won't Turn On, and No Power Hardware Triage (Desktop & Laptop)
tier: L1
keywords_en:
  - dead pc
  - pc won't start
  - pc won't turn on
  - computer won't turn on
  - computer has no power
  - laptop won't turn on
  - no lights no fans
keywords_fr:
  - pc mort
  - pc ne s'allume pas
  - pc ne s'allume plus
  - ordinateur ne s'allume pas
  - aucune alimentation pc
  - portable ne s'allume plus
error_codes:
  - NO_POWER
  - DEAD_PC
  - NO_LED_NO_FANS
  - PSU_FAIL
tags:
  - pc_no_power
  - dead_pc_triage
  - hardware_power_fail
os:
  - windows
environment:
  - local_endpoint
tools:
  - OEM AC Adapter
  - Power Cable / Wall Outlet
  - Dell/HP PSU BIST Button
  - Vendor Warranty Portal
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - win-013
  - win-009
  - prt-003
  - win-014
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. When you press the power button on `PC-LAB-01`, is the computer **100% lifeless (zero lights, zero fan spin, zero charger LED)**, OR do fans/power lights come on with nothing on screen (`[win-013]`) / fail at the logo (`[win-014]`)?
2. Is `PC-LAB-01` a **laptop** or a **desktop tower / mini-PC**, and is it plugged into a **power strip / UPS / USB-C dock** instead of directly into a known-working wall outlet?
3. Before checking anything else: did the PC suffer a **liquid spill, burning smell, hot/swollen battery bulge, or nearby power surge / lightning storm**?
4. When a laptop AC charger is plugged into the wall and directly into the laptop, does the **charging LED** near the power port or on the AC brick light up at all?

### Initial Scope & Classification
- Separate **wall outlet / power strip / dead AC adapter** (most common L1 instant fixes) from **USB peripheral / dock 5V rail short or Embedded Controller (EC) static latch** vs **failed internal PSU / motherboard**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Zero CLI Physical Isolation)
1. **Safety First (Stop & Escalate Immediately If Observed):** If `jsmith@example.com` reports smoke, burnt odor, sparking, spilled liquid, or a warped/bulging laptop trackpad/chassis (`SWOLLEN BATTERY`), instruct them to **unplug the wall cable immediately and stop touching it** — dispatch hardware replacement!
2. **Test the Wall Outlet & Bypass Power Strips / Docks:**
   - Have the user plug a desk lamp or phone charger into the same wall socket to confirm live `120V/240V` power, and confirm a tripped GFCI/breaker or switched wall outlet isn't off!
   - Plug the PC's **OEM AC power cord directly into the wall** (bypassing faulty surge bars, switched power strips, uncharged UPS batteries, and USB-C docking stations `[prt-003]`).
3. **Desktop PSU & Front-Panel Sanity Check:**
   - Check the rocker switch (`I` / `O`) on the rear power supply unit (PSU) of desktop towers — ensure it is set to **`I` (On)** and the C13 power cord is seated firmly at both ends!
   - Listen/watch closely when pressing power: look for even a `0.5s` fan twitch or brief amber/white blink on the power button.
4. **Laptop Charger LED, USB-C Port & Peripheral Unplug Test:**
   - Unplug **ALL USB drives, docks, monitors, headsets, and Ethernet cables** (a shorted USB hub or defective dock can prevent a PC from powering on!).
   - Inspect the laptop USB-C or barrel power port with a phone flashlight for lint/bent pins; if dual USB-C ports exist, test charging in the alternate port using the **original high-wattage OEM AC brick** (phone USB-C chargers often cannot wake a deeply drained laptop!).

### L2 Technical Diagnostics
1. **Desktop PSU Built-In Self-Test (`BIST`) & Motherboard Standby LED:**
   - On Dell / HP desktops with a rear green/black **PSU BIST test button**, unplug the internal 24-pin ATX harness only if authorized for hardware bench testing (or press the rear BIST button with AC connected): verify the green LED illuminates cleanly while the PSU fan spins (`PSU_FAIL` if dead!).
   - Check inside the desktop case window/vents for the green/amber **motherboard `AUX_PWR` standby LED** and any **2-color amber/white blink pattern** (`[win-013]`).
2. **Look Up Asset Tag / Warranty Coverage & Data Sync Continuity:**
   - Check Dell Support / Lenovo Vantage / HP Warranty portal by Service Tag for active next-business-day onsite hardware replacement.
   - Verify in **Intune / M365 Admin ([Microsoft Entra Admin Center](https://entra.microsoft.com/))** and **OneDrive** when `PC-LAB-01` last checked in and retrieve its **48-digit BitLocker Recovery Key (`[win-002]`)** proactively in case an intact SSD needs to be unlocked on a loaner/bench machine!

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm direct wall outlet tested good, known-good AC brick/cord tested (if available), all USB peripherals/docks disconnected, flea-power drain attempted, exact LED/beep/BIST behavior recorded, and PC serial/asset tag + BitLocker recovery key status documented.

## Deep-Dive Investigation (L3)
1. **Embedded Controller (EC) Latch vs Motherboard VRM / Power-Rail Short:** Modern business laptops can enter an EC brownout lock after a complete battery discharge or Type-C PD surge; disconnecting main battery + CMOS battery for 60 seconds (bench hardware work) distinguishes an EC latch from a shorted motherboard component.
2. **Data Recovery From Non-Powering Hardware:** When a system board fails out of warranty or before onsite depot swap, pull the M.2 NVMe SSD into a USB-NVMe enclosure on a technician bench PC and unlock with the escrowed BitLocker key (`manage-bde -unlock E: -RecoveryPassword <48-digit-key>`).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Verify there is NO liquid spill, burnt smell, or swollen battery before re-applying AC power! Always unplug external drives and docks first.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Quick Fix — 30-Second Flea-Power Drain & Laptop EC Reset)**
   - Unplug the **AC charger/power cord**, **USB-C dock**, and **ALL USB peripherals** from `PC-LAB-01`.
   - Hold the physical **Power button continuously for 30 seconds** to discharge motherboard capacitors (on laptops with a tiny underside **Emergency Reset pinhole**, press it with a paperclip for 10 seconds instead).
   - Connect **ONLY the verified OEM AC charger / power cord directly to a live wall outlet** (wait 2 minutes if a laptop battery was 0%), then press Power once.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Known-Good AC Adapter / Cord Swap)** Swap the desktop C13 power cord (`10A` seated firmly) or test with a verified spare OEM laptop charger (matching >= `65W`–`130W` wattage), keeping all docks and USB hubs disconnected until the PC boots cleanly.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Hardware Warranty Dispatch & Loaner Provisioning)** If zero LEDs, zero PSU BIST response, or suspected board failure persists after clean wall power + flea-power reset: issue a spare loaner PC signed into `jsmith@example.com`'s M365/OneDrive profile, open an OEM warranty hardware ticket (or bench SSD pull with escrowed BitLocker key `[win-002]`), and keep ticket updated.

## Verification & Post-Fix Checks
1. Confirm `PC-LAB-01` powers on consistently across 2 cold boot cycles, LEDs and fans start cleanly, and laptop battery charges smoothly when the OEM AC brick is attached (`[win-009]`).
2. Reconnect external monitors/dock (`[prt-003]`) and USB peripherals **one at a time** to verify none of the accessories caused a short-circuit power trip.

## Cross-Subject Escalation & Pivot Links
- **PC powers on (fans/LEDs active) but screen stays completely black with no logo:** [win-013 — PC Turns On With Black Screen, No Display, or Fails POST (Beep / LED Blink Codes)](./win-013-pc-power-on-black-screen-no-post-display-triage.md)
- **Laptop powers on only briefly or battery drains / shows "Plugged in, not charging":** [win-009 — Windows Laptop Battery Draining Fast, Not Charging, and Sleep/Wake Failures](./win-009-laptop-battery-draining-fast-not-charging-and-sleep-wake.md)
- **USB-C dock fails to supply enough power or blanks external displays:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](../05_Printers_Devices/prt-003-usbc-dock-monitors-not-detected.md)
- **PC powers on and shows OEM logo / Automatic Repair but fails booting Windows:** [win-014 — Windows Won't Boot Up, Automatic Repair Loop, No Bootable Device, and WinRE / BCD Recovery](./win-014-windows-wont-boot-automatic-repair-loop-and-bcd.md)

## Useful Links & External Tools
- **[Microsoft Entra Admin Center](https://entra.microsoft.com/)** — Look up BitLocker recovery keys or device ownership before dispatching hardware replacement.
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Check Windows LAPS / BitLocker escrow and serial/hardware inventory prior to OEM warranty ticket.

## Client Update Snippets (EN / FR)
- **EN:** We isolated the power issue on `PC-LAB-01` by checking the wall outlet, disconnecting external docks/USB accessories, and performing a capacitor power reset (or initiating an OEM hardware warranty dispatch with a loaner workstation). Could you confirm if the workstation now powers on reliably?
- **FR:** Nous avons diagnostiqué le problème d'alimentation sur `PC-LAB-01` en vérifiant la prise murale, en débranchant les stations d'accueil et périphériques USB, puis en effectuant une décharge électrique complète (ou en lançant une intervention matérielle sous garantie avec poste de prêt). Pouvez-vous confirmer si le poste démarre maintenant ?
