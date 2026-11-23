---
id: win-007
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: profiles_audio_av
title: Windows Webcam, Microphone, and Speaker Audio Not Working (0xA00F4244 / Code 10 / 43)
tier: L1
keywords_en:
  - webcam not working teams
  - microphone not detected windows
  - no camera attached
  - speaker no sound windows
  - device manager code 43 camera
keywords_fr:
  - camera ne fonctionne pas teams
  - micro non detecte windows
  - aucune camera detectee 0xa00f4244
  - pas de son ordinateur windows
  - microphone muet teams windows
error_codes:
  - "0xA00F4244"
  - Code 10
  - Code 43
tags:
  - windows_audio_webcam
  - teams_mic_camera_blocked
os:
  - windows
environment:
  - local_endpoint
  - m365
tools:
  - PowerShell
  - Device Manager
  - Windows Settings
  - Teams Device Settings
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - prt-002
  - prt-003
  - net-003
---

## Fast Triage (Under 2 Minutes)
- **Physical Checks First (Saves 80% of Calls!):**
  - Check for a **physical webcam privacy shutter slider** above the laptop screen (shows black/gray image even though camera LED is on!).
  - Check for a hardware **`F4` / `F8` / `Fn` microphone-mute or camera-kill switch** on Dell/Lenovo/HP keyboards, or an inline mute LED on USB headsets!
- Test the built-in **Windows Camera** app and **Settings -> System -> Sound** input bar: does the fault affect Windows itself (`0xA00F4244 NoCamerasAreAttached`), or ONLY inside Teams/Zoom?

## Read-Only Diagnostics (L1-L2)
1. **Check Camera & Audio Endpoint PnP Device Status (read-only):**
   ```powershell
   Get-PnpDevice -Class Camera, Image, Media, AudioEndpoint -ErrorAction SilentlyContinue |
       Select-Object Class, Status, FriendlyName, ProblemDescription | Format-Table -AutoSize
   Get-Service AudioSrv, AudioEndpointBuilder, FrameServer -ErrorAction SilentlyContinue |
       Select-Object Name, Status, StartType
   ```
   *(Look for `Error` / `Code 10` / `Code 43`, or hidden/disconnected devices when USB hubs are unpowered.)*
2. **Check Windows Privacy & App Permissions:**
   - Open **Settings -> Privacy & security -> Camera** and **Microphone**: verify **Camera access / Microphone access** AND **"Let apps access your camera/microphone"** AND **"Let desktop apps access your camera/microphone"** are ALL **On**!
3. **Check Sound Control Panel (`mmsys.cpl`) & Exclusive Mode:**
   - Confirm the right **Default Playback** and **Default Communication** devices are selected (a newly attached HDMI monitor or USB-C dock often hijacks Default Audio Output to monitor speakers that have no volume!).

## Deep-Dive Investigation (L3)
1. **`0xA00F4244` Camera Missing After Windows Update / Dock Sleep:** Inspect `Device Manager -> Cameras` (enable **View -> Show hidden devices**); check if an Intune/GPO policy (`LetAppsAccessCamera`, `DisableCamera`) or **Lenovo Vantage / HP Sure View** software privacy toggle disabled the camera at driver level!
2. **`FrameServer` Camera Lock (`0xA00F4271`):** Only one desktop app can stream most UVC webcams unless **Windows Camera Frame Server (`FrameServer`)** is running cleanly; closing background Teams/Zoom/browser tabs holding the camera frees the stream.
3. **Intel Smart Sound Technology (`SST`) Audio Crash (`Code 10` / `Code 43`):** Common on 11th–14th Gen Intel laptops after mismatched Realtek + Intel SST driver updates; inspect `Get-CimInstance Win32_PnPSignedDriver` versions.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Switch audio output/input back to the intended headset/laptop speakers via taskbar Volume -> **Select a sound output**, and configure explicit devices inside **Teams -> Settings -> Devices**.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Restart Windows Audio and Camera FrameServer services (requires elevated prompt; interrupts active calls):
   ```powershell
   Restart-Service -Name AudioSrv, AudioEndpointBuilder, FrameServer -Force
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **`Code 10` / `Code 43` / `0xA00F4244`**: plug external webcams directly into a PC USB port (bypassing unpowered hubs), install the official OEM **Audio / Intel SST / Camera driver**, or in Device Manager uninstall the faulted device (without deleting driver unless replacing) and click **Scan for hardware changes** + reboot.

## Verification & Post-Fix Checks
1. Open Windows **Camera** app and verify live video appears cleanly.
2. Run **Teams -> Settings -> Devices -> Make a test call** and confirm mic level bar moves, camera previews, and playback audio is clear.

## Cross-Subject Escalation & Pivot Links
- **Audio issue isolates to Bluetooth headset Hands-Free (HFP) profile or multipoint drop:** [prt-002 — Bluetooth Headphones Cannot Connect, Drop Audio, or Mic Fails in Calls](../05_Printers_Devices/prt-002-bluetooth-headphones-wont-connect-or-no-audio.md)
- **Webcam/headset vanishes only when connected through a USB-C / Thunderbolt dock:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](../05_Printers_Devices/prt-003-usbc-dock-monitors-not-detected.md)
- **Local audio hardware passes Windows tests yet Teams call voice chops or drops:** [net-003 — Teams and VoIP Choppy Audio, High Jitter, and One-Way Sound Triage](../04_Network_VPN_VoIP/net-003-teams-voip-choppy-audio-and-jitter.md)

## Client Update Snippets (EN / FR)
- **EN:** We updated the Windows camera/microphone privacy settings and audio services on `PC-LAB-01` and selected the proper headset/camera devices. Could you run a quick Teams test call and confirm both video and audio work normally?
- **FR:** Nous avons vérifié les autorisations de confidentialité caméra/micro et les services audio sur `PC-LAB-01` et reconfiguré vos périphériques actifs. Pouvez-vous lancer un appel test dans Teams et confirmer que la caméra et le micro fonctionnent ?
