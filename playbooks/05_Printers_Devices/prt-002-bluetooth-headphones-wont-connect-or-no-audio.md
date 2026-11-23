---
id: prt-002
domain: 05_Printers_Devices
subject: "Printers & Peripherals"
subcategory: bluetooth_docks_displays
title: Bluetooth Headphones Cannot Connect, Drop Audio, or Mic Fails in Calls
tier: L1
keywords_en:
  - bluetooth headphones won't connect
  - bluetooth headset no audio
  - bluetooth mic not working
  - paired but not connected
  - teams bluetooth choppy
keywords_fr:
  - casque bluetooth ne se connecte pas
  - ecouteurs bluetooth
  - ecouteurs bluetooth pas de son
  - micro bluetooth teams
  - bluetooth jumelé sans son
error_codes:
  - BTH_PAIR_FAIL
  - HFP_A2DP
tags:
  - bluetooth_audio_connect
  - bluetooth_hfp_a2dp
os:
  - windows
  - macos
environment:
  - local_endpoint
tools:
  - PowerShell
  - Device Manager
  - Bluetooth Settings
  - Terminal
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - win-007
  - net-003
  - prt-003
linked_scripts:
  - 04_Devices/Get-ProblemDevices.ps1
  - 04_Devices/Get-DeviceDrivers.ps1
  - 04_Devices/Update-DeviceDrivers.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Do the headphones show **`Paired`** without connecting (`Can't connect`), or do they **connect cleanly yet have zero audio / broken mic inside Teams calls** (`HFP_A2DP`)?
2. Are the headphones charged and currently **paired to a nearby iPhone/Android phone** (many headsets cap at 1–2 connections and lock onto the phone first!)?
3. Do you have a **vendor USB Bluetooth dongle** (`Jabra Link` / `Poly BT700`), or are you connecting directly to laptop Bluetooth?
4. Is the Windows Bluetooth toggle missing completely from Quick Settings?

### Initial Scope & Classification
- Check phone multipoint hijacking + battery first, then distinguish **`Stereo` (Music A2DP)** vs **`Hands-Free` (Call HFP)** endpoints in Windows & Teams.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Turn Off Phone Bluetooth Temporarily & Check Battery (`Solves 50% of Calls!`):** Turn Bluetooth OFF on `jsmith@example.com`'s phone so it releases the headset, ensure headset is powered on & charged, and test connecting cleanly on `PC-LAB-01`! (If the headset came with a Jabra/Poly USB dongle, plug in the dongle instead of pairing natively!)
2. **Verify Teams / Windows Device Selection (`Teams -> Settings -> Devices`):** Look closely at **Speaker** and **Microphone**: select the matching **`Headset (Hands-Free)`** for BOTH Speaker & Mic during calls (NOT laptop array mic + Stereo Headphones, which causes `HFP_A2DP` silence!).
3. **Check Windows Bluetooth Settings & Services:** Open **Settings -> Bluetooth & devices** (confirm toggle is **On**, not Airplane mode!) and press `Win + R` -> `services.msc` -> check **Bluetooth Support Service (`bthserv`)** and **Windows Audio (`AudioSrv`)**.

### L2 Technical Diagnostics
1. **On Windows**, inspect Bluetooth support service, Audio services, and Bluetooth device status (read-only):
   ```powershell
   Get-Service bthserv, BTAGService, AudioSrv, AudioEndpointBuilder -ErrorAction SilentlyContinue |
       Select-Object Name, Status, StartType
   Get-PnpDevice -Class Bluetooth | Select-Object Status, FriendlyName, InstanceId
   ```
2. **Verify A2DP Stereo vs. Hands-Free (HFP) Audio Endpoints:**
   - Windows separates high-quality output (**Headphones / Stereo - A2DP**) from bidirectional call audio (**Headset / Hands-Free AG Audio - HFP**). When the microphone activates, Windows mutes Stereo and switches to Hands-Free; if the **Hands-Free** endpoint is disabled in `mmsys.cpl` (Sound Control Panel), call audio drops completely.
3. **On macOS**, inspect Bluetooth daemon state and paired audio profiles (read-only):
   ```bash
   system_profiler SPBluetoothDataType
   ```
4. Check if Airplane Mode is enabled or if a corporate Intune/GPO policy blocks Bluetooth audio profiles (`AllowBluetooth`).

## Deep-Dive Investigation (L3)
1. Inspect `System` and `Microsoft-Windows-BTH-BTHPORT/Operational` logs for `BTH_PAIR_FAIL` or driver timeout codes (`Error 43` / `Code 45`).
2. Check if the Bluetooth adapter (`Intel Wireless Bluetooth`, `Qualcomm`, `Realtek`) requires a BIOS/chipset driver update or has **Allow the computer to turn off this device to save power** enabled in Device Manager.
3. If multiple USB Bluetooth dongles or a laptop internal radio + dock dongle exist simultaneously, disable the redundant adapter so Windows does not bind audio to an unattached radio.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Temporarily toggle Bluetooth off on the user's nearby smartphone, put the headphones into explicit **Pairing Mode** (usually 5-second hold), remove the stale paired entry in **Settings -> Bluetooth & devices -> Remove device**, and re-pair cleanly.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** On Windows (`PC-LAB-01`), restart Bluetooth and Windows Audio services (requires elevated prompt):
   ```powershell
   Restart-Service -Name bthserv, AudioSrv -Force
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** In `mmsys.cpl` (**Playback** and **Recording** tabs), ensure both **Headphones (Stereo)** and **Headset (Hands-Free)** are enabled, and select the explicit **Headset (Hands-Free)** device inside Teams/Zoom **Audio Settings** (or use the manufacturer USB-A/USB-C dongle if provided, e.g., Jabra/Poly).
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** On macOS, reset the Bluetooth daemon cleanly (requires local admin; briefly disconnects Bluetooth mouse/keyboard if no wired fallback is attached):
   ```bash
   sudo pkill bluetoothd
   ```

## Verification & Post-Fix Checks
1. Confirm **Settings -> Bluetooth & devices** shows **`Connected voice, music`** (Windows) or active output/input in **System Settings -> Sound** (macOS).
2. Play a short audio test and run a Teams **Make a test call** to confirm both speaker output and microphone input work simultaneously.

## Cross-Subject Escalation & Pivot Links
- **Windows sound privacy settings, missing driver, or Device Manager Code 10/43 disables audio:** [win-007 — Windows Webcam, Microphone, and Speaker Audio Not Working (0xA00F4244 / Code 10 / 43)](../03_Windows_Endpoints/win-007-windows-audio-webcam-and-mic-not-working.md)
- **Call audio glitches persist even on wired speakers due to Teams jitter/packet loss:** [net-003 — Teams and VoIP Choppy Audio, High Jitter, and One-Way Sound Triage](../04_Network_VPN_VoIP/net-003-teams-voip-choppy-audio-and-jitter.md)
- **USB Bluetooth receiver disconnects intermittently through an overloaded USB-C dock:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](./prt-003-usbc-dock-monitors-not-detected.md)

## Client Update Snippets (EN / FR)
- **EN:** We cleared the stale Bluetooth pairing profile on `PC-LAB-01`, refreshed the audio services, and verified both stereo playback and call microphone routing. Could you test your headphones in a quick call and confirm everything sounds clear?
- **FR:** Nous avons supprimé le profil Bluetooth obsolète sur `PC-LAB-01`, relancé les services audio et vérifié le fonctionnement des écouteurs ainsi que du microphone. Pouvez-vous effectuer un court essai d'appel et confirmer que le son fonctionne bien ?
