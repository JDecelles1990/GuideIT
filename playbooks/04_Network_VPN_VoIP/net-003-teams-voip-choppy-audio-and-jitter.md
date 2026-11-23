---
id: net-003
domain: 04_Network_VPN_VoIP
subject: "Network, VPN & VoIP"
subcategory: dns_dhcp_wifi_voip
title: Teams and VoIP Choppy Audio, High Jitter, and One-Way Sound Triage
tier: L2
keywords_en:
  - choppy call
  - teams audio robotic
  - one way audio
  - voip call drops
  - teams call quality poor
keywords_fr:
  - appel hache
  - son robotique teams
  - voix coupee
  - audio unidirectionnel voip
  - mauvaise qualite appel teams
error_codes:
  - SIP_ALG
  - UDP_3478
tags:
  - voip_choppy_audio
  - teams_call_quality
os:
  - windows
  - macos
environment:
  - network
  - m365
  - saas
tools:
  - Microsoft Teams
  - PowerShell
  - Test-NetConnection
  - pathping
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - net-002
  - net-001
  - prt-002
  - win-007
linked_scripts:
  - 03_M365/Get-TeamsDiagnostics.ps1
  - 02_Network/Test-NetworkQuality.ps1
  - 02_Network/Get-WiFiDiagnostics.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Does the choppy/robotic audio happen on **ALL calls** or ONLY when **talking to one external person** (or only in large meetings)?
2. Are you currently on **Wi-Fi (`[net-002]`) vs wired Ethernet**, using **Bluetooth headphones (`[prt-002]`) vs laptop mic/wired headset**, and connected to **corporate VPN (`[net-006]`)**?
3. During a live call, can people **not hear you at all (`One-way audio`)**, or is the sound **stuttering/lagging (`Jitter`)**?

### Initial Scope & Classification
- Check **Teams Call Health** during a live call (**More (`...`) -> Settings -> Call health**) for live **Jitter (>30 ms)**, **Round-trip latency (>100 ms)**, or **Packet loss (>1%)**.
- Quickly run **Teams -> Settings -> Devices -> Make a test call** to split local headset/Bluetooth faults (`[prt-002]`/`[win-007]`) from internet/VPN network congestion!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Teams "Make a test call" & Switch Off VPN/Bluetooth Briefly:**
   - Run **Teams -> Settings -> Devices -> Make a test call**. If your own playback recording sounds choppy BEFORE touching the network, test a wired headset or laptop speakers (`[prt-002]` / `[win-007]`).
   - Turn **off Home/Other Video Downloads** and test **disconnecting full-tunnel VPN briefly** or switching from Wi-Fi (`2.4 GHz`) to **Wired Ethernet / `5 GHz`**!
2. **Verify Teams Video Bandwidth & Background Apps:** Check Task Manager (`Ctrl + Shift + Esc`) for OneDrive/Windows Update saturating home upload bandwidth during the call (`[win-006]`).

### L2 Technical Diagnostics
1. **Isolate Endpoint Audio Device vs. Network:**
   - Inspect Teams Call Health metrics and confirm whether local media passes directly over UDP.
2. **Test Network Latency, Packet Loss, and M365 Media Relay Ports (read-only):**
   ```powershell
   # Verify UDP 3478-3481 isn't forced over broken proxy/TCP fallback and check path latency
   Test-NetConnection -ComputerName "worldaz.tr.teams.microsoft.com" -Port 443 | Select-Object ComputerName, TcpTestSucceeded
   ```
   ```cmd
   pathping -n -q 25 -p 100 1.1.1.1
   ```
3. **Check Active VPN Routes (`net-001`):**
   ```powershell
   Get-VpnConnection -AllUserConnection -ErrorAction SilentlyContinue | Select-Object Name, ConnectionStatus, SplitTunneling
   Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Select-Object InterfaceAlias, NextHop, RouteMetric
   ```

## Deep-Dive Investigation (L3)
1. **VPN Hairpinning & TCP Fallback (`UDP_3478` Blocked):** Microsoft Teams real-time audio/video requires **UDP ports `3478–3481`** direct to Microsoft Teams Transport Relay / M365 **Optimize** media endpoints (bypassing SSL proxies and full-tunnel VPNs!). When UDP `3478` is blocked or routed over VPN, media falls back to TCP `443` and buffers/jitters during congestion.
2. **Router `SIP_ALG` Breaking Desk Phones / Softphones:** On VoIP/SIP trunks experiencing **one-way audio** or dropped calls at exactly 30 seconds / 15 minutes, verify **SIP ALG** is disabled on the ISP modem and edge firewall (Meraki/FortiGate/SonicWall/Sophos).
3. **Bufferbloat & QoS DSCP Tagging:** On congested office WAN circuits, verify DSCP markings (`EF 46` for voice, `AF41 34` for video) and WAN bandwidth prioritization so large OneDrive/Windows Update downloads don't starve voice packets.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For remote workers on corporate VPN: test disconnecting VPN (or enable **VPN Split Tunneling** excluding Microsoft Teams Media IPs + `UDP 3478–3481`) so voice traffic takes the direct ISP path.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** On endpoint `PC-LAB-01`: switch from crowded `2.4 GHz` Wi-Fi to wired Ethernet (or `5 GHz` near AP) and prefer a wired/USB-dongle headset over native laptop Bluetooth for long meetings.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** On edge firewall/ISP gateway (with change approval): allow outbound `UDP 3478–3481` for Teams Media without DPI/SSL inspection, and disable **SIP ALG** for VoIP trunk one-way audio issues.

## Verification & Post-Fix Checks
1. Join a live Teams test call and inspect **Call health**: verify **Audio packet loss < 1%**, **Jitter < 30 ms**, and media protocol reports **UDP** (not TCP).
2. Confirm two-way voice clarity with `jsmith@example.com` and an external/internal participant.

## Cross-Subject Escalation & Pivot Links
- **Wi-Fi roaming drops, low RSSI, or co-channel interference causes RTP packet loss:** [net-002 — Wi-Fi Random Disconnects, Connected Without Internet, and 802.1X Auth Triage](./net-002-wifi-drops-and-8021x-auth.md)
- **VPN hairpinning forces Teams media through congested tunnel instead of UDP split-tunnel:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](./net-001-dns-apipa-vpn-triage.md)
- **Bluetooth headset profile switching (HFP vs A2DP) causes robotic or muted call audio:** [prt-002 — Bluetooth Headphones Cannot Connect, Drop Audio, or Mic Fails in Calls](../05_Printers_Devices/prt-002-bluetooth-headphones-wont-connect-or-no-audio.md)
- **Windows mic privacy toggle or local audio driver defect breaks voice pickup:** [win-007 — Windows Webcam, Microphone, and Speaker Audio Not Working (0xA00F4244 / Code 10 / 43)](../03_Windows_Endpoints/win-007-windows-audio-webcam-and-mic-not-working.md)

## Client Update Snippets (EN / FR)
- **EN:** We identified the network routing / VPN / headset bottleneck affecting your Teams call quality and adjusted the configuration. Could you join a quick test call and confirm the audio sounds clear on both sides?
- **FR:** Nous avons identifié la source des coupures audio Teams (routage VPN / réseau / périphérique audio) et ajusté la configuration. Pouvez-vous effectuer un court appel test et confirmer que le son est clair des deux côtés ?
