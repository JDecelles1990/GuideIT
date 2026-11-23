---
id: prt-005
domain: 05_Printers_Devices
subject: "Printers & Peripherals"
subcategory: bluetooth_docks_displays
title: USB Keyboard, Mouse, Headset, or External Drive Not Recognized (Power & Driver Triage)
tier: L1
keywords_en:
  - usb device not recognized
  - keyboard mouse not working windows
  - usb headset not detected
  - external hard drive not showing up
  - device descriptor request failed
keywords_fr:
  - peripherique usb non reconnu
  - clavier souris ne fonctionne plus windows
  - casque usb non detecte
  - disque dur externe invisible windows
  - erreur peripherique usb code 43
error_codes:
  - USB_DESC_FAIL
  - Code 43
  - Code 28
tags:
  - usb_device_not_recognized
  - usb_peripheral_driver
os:
  - windows
  - macos
environment:
  - local_endpoint
tools:
  - Device Manager
  - Disk Management (diskmgmt.msc)
  - PowerShell
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - prt-003
  - prt-002
  - win-007
linked_scripts:
  - 04_Devices/Get-ProblemDevices.ps1
  - 04_Devices/Get-DeviceDrivers.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is the device plugged into a **USB-C dock / unpowered USB hub (`[prt-003]`)** or **directly into the laptop/PC**? *(If through a dock/hub, always test direct laptop USB port first!)*
2. For a **wireless keyboard/mouse/headset**, did you check the **AA/AAA battery / charge switch**, **On/Off slider**, and ensure the **tiny USB wireless dongle** is plugged in?
3. When plugging it in, does Windows pop up **`USB device not recognized` (`USB_DESC_FAIL`)**, play the USB chime with nothing working, or show zero lights/power?
4. For an **external USB drive**, do you hear it spin/light up yet no drive letter appears in File Explorer?

### Initial Scope & Classification
- Distinguish **dead hardware / wireless battery / unpowered dock port** (test direct port + another PC!) from **Windows USB controller sleep/Code 43 latch**, **BitLocker/Intune USB Storage block policy**, or **missing drive letter in `diskmgmt.msc`**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Direct Port & Known-Good Test (Solves 60% of Cases!):** Unplug from USB-C dock/hub -> plug directly into another physical USB port on `PC-LAB-01` -> if still dead, test the keyboard/mouse/headset on a second computer to confirm whether the peripheral itself died!
2. **Check Wireless Dongle / Batteries / Mute Switch:** Replace wireless keyboard/mouse batteries, check bottom power switch, and verify Logitech Unifying / Jabra Link dongle isn't missing or paired only via Bluetooth (`[prt-002]`).
3. **Check Device Manager (`devmgmt.msc`) & Disk Management (`diskmgmt.msc`):**
   - Look under **Universal Serial Bus controllers**, **Other devices**, **Keyboards/Mice**, or **Sound, video and game controllers** for a yellow warning triangle (**`Code 43`** / **`Code 28` No driver** / **`Device Descriptor Request Failed`**).
   - For external USB drives: open **`diskmgmt.msc`** to check if the disk is visible yet missing a Drive Letter (`D:`/`E:`), or blocked as `Offline / Read-Only` by policy!

### L2 Technical Diagnostics
1. **Inspect PnP Problem USB Devices & Driver Status (`PC-LAB-01`, read-only — or run `psstore://04_Devices/Get-ProblemDevices.ps1`):**
   ```powershell
   Get-PnpDevice | Where-Object { $_.Status -ne "OK" -or $_.FriendlyName -match "Unknown USB|Descriptor" } |
       Select-Object Class, Status, FriendlyName, ProblemDescription, InstanceId | Format-Table -AutoSize
   Get-PnpDevice -Class USB | Select-Object Status, FriendlyName | Format-Table -AutoSize
   ```
2. **Check Intune / GPO Removable Storage Block (Corporate Security Policy!):** If ALL USB flash drives fail while mice/keyboards work, verify whether **Device Control / Removable Storage Access** intentionally blocks USB mass storage!

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact device make/model, whether tested direct-to-PC + on a second computer, exact Device Manager `Code 28 / 43` status, and screenshot of `diskmgmt.msc` (if storage drive).

## Deep-Dive Investigation (L3)
1. **USB Selective Suspend / xHCI Controller Hang:** Windows powers down idle USB Root Hubs or Intel/AMD Thunderbolt/USB4 controllers after sleep, leaving docks or headsets dead (`USB_DESC_FAIL`) until the USB Root Hub driver resets or laptop EC power drains.
2. **Custom Vendor Software / Firmware Driver Required (`Code 28`):** Smartcard readers, barcode scanners, Foot Pedals, or label printers often require signed vendor drivers before Windows enumerates them.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** WARNING: If the user is on a remote desktop session using ONLY a USB mouse/keyboard, uninstalling the **USB Root Hub** disconnects ALL USB peripherals temporarily until reboot completes! Proceed carefully and prefer targeted device uninstall first.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Quick Reset)** Move the peripheral to a direct PC USB port, replace wireless batteries, or **shut down / full Restart** (`Start -> Power -> Restart`, unplugging the USB device during reboot and plugging back in at Windows desktop).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Clear `Code 43` / `USB_DESC_FAIL` Ghost Device)** In **Device Manager**, right-click the faulted `Unknown USB Device` (`Code 43`) -> **Uninstall device** -> unplug physical USB cable for 10 seconds -> Action -> **Scan for hardware changes** (or reboot) -> plug cable back in!
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 External Drive Missing Drive Letter)** If a healthy unblocked external drive appears in `diskmgmt.msc` cleanly with a partition yet no letter, right-click the partition -> **Change Drive Letter and Paths -> Add -> Assign letter** (NEVER click *Format* if data exists!).

## Verification & Post-Fix Checks
1. Confirm `Get-PnpDevice` shows `Status = OK` with zero `Code 43 / Unknown USB` warnings.
2. Have `jsmith@example.com` test typing, mouse movement, headset audio (`[win-007]`), or opening a file on the recognized USB device.

## Cross-Subject Escalation & Pivot Links
- **All USB peripherals AND external monitors drop together on a USB-C dock:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](./prt-003-usbc-dock-monitors-not-detected.md)
- **Headset connects over USB/Bluetooth yet Teams mic/audio stays silent:** [win-007 — Windows Webcam, Microphone, and Speaker Audio Not Working (0xA00F4244 / Code 10 / 43)](../03_Windows_Endpoints/win-007-windows-audio-webcam-and-mic-not-working.md)
- **Wireless headset connects over Bluetooth instead of a USB dongle:** [prt-002 — Bluetooth Headphones Cannot Connect, Drop Audio, or Mic Fails in Calls](./prt-002-bluetooth-headphones-wont-connect-or-no-audio.md)

## Useful Links & External Tools
- **[Windows Release Health & Known Issues](https://learn.microsoft.com/en-us/windows/release-health/)** — Check for recent Windows USB controller or driver update advisories.

## Client Update Snippets (EN / FR)
- **EN:** We cleared the faulted Windows USB device entry (`Code 43 / Device Descriptor`), verified direct port power and driver status on `PC-LAB-01`, and confirmed the peripheral enumerates cleanly. Could you test using the device now and confirm it responds normally?
- **FR:** Nous avons supprimé le périphérique USB en erreur (`Code 43`) dans le Gestionnaire de périphériques sur `PC-LAB-01`, vérifié l'alimentation directe du port et le pilote, et validé la détection. Pouvez-vous tester votre périphérique maintenant ?
