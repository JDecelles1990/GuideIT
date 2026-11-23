---
id: net-007
domain: 04_Network_VPN_VoIP
subject: "Network, VPN & VoIP"
subcategory: dns_dhcp_wifi_voip
title: Office VoIP Desk Phone No Dial Tone, PoE Power Down, or Stuck Registering
tier: L1
keywords_en:
  - voip phone not working
  - desk phone no dial tone
  - yealink poly phone stuck registering
  - phone screen blank poe
  - sip phone 403 408 error
keywords_fr:
  - telephone ip ne fonctionne pas
  - poste telephonique pas de tonalite
  - telephone voip bloquee enregistrement
  - ecran telephone eteint poe
  - erreur sip telephone bureau
error_codes:
  - SIP_403
  - SIP_408
  - NO_SERVICE
  - POE_OFF
tags:
  - voip_desk_phone
  - voip_poe_registration
os:
  - cross_platform
environment:
  - network
  - saas
tools:
  - VoIP Switch / Admin Portal
  - Network Switch PoE Port Status
  - Phone Web UI
  - PowerShell
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - net-003
  - net-001
  - srv-012
linked_scripts:
  - 02_Network/Test-NetworkQuality.ps1
  - 02_Network/Test-PortConnectivity.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is the **desk phone screen completely black/off (`POE_OFF`)**, or is the screen lit showing **`No Service` / `Registering...` / `Network Unavailable`**?
2. Is this **only your desk phone**, or are **all phones in the same office/floor** down at the same time?
3. Was the phone **moved to another desk/wall jack** recently, or did someone plug into the wrong back port (**`PC` port** instead of **`LAN / Internet / PoE` port**)?
4. If the phone screen is lit, can you make/receive calls at all, or do calls ring without audio (`net-003`)?

### Initial Scope & Classification
- Separate **physical cabling / PoE power** (screen black -> check cable port & switch PoE) from **DHCP / VLAN / SIP registration** (screen lit with `No Service` / `SIP_408` / `SIP_403`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Check physical cables on the back of the desk phone (fixes ~50% of calls!):**
   - Wall jack Ethernet cable MUST plug into the phone's **`LAN` / `SW` / `Internet` (PoE symbol)** port — NOT the **`PC`** pass-through port!
   - If the screen is completely blank, test with a known-good Ethernet patch cord or test a different AC power adapter (if not PoE) / adjacent active VoIP jack.
   - If a **computer** is plugged into the phone's `PC` port, check if the PC still gets internet (`[net-001]`).
2. **Read status directly from the phone screen:** Press **OK** / **Menu -> Status** (Yealink/Poly/Cisco) to note its **IPv4 Address** (does it show `0.0.0.0` or `169.254.x.x` or valid Voice VLAN IP `10.0.20.x`?), **MAC Address**, and exact error (`Register Failed` / `SIP_403` / `SIP_408`).
3. **Check VoIP Provider / Cloud PBX Status Page:** Before touching switches, confirm the hosted VoIP carrier (RingCentral / Teams Phone / 3CX / FreePBX) is not having an outage.

### L2 Technical Diagnostics
1. **Verify Voice VLAN, DHCP Option (`Option 66` / `132` / LLDP-MED), and PoE Power on the Access Switch:**
   - Check switch port PoE wattage budget (did someone plug in a new camera/AP exhausting switch PoE budget?) and confirm the port carries the Voice VLAN.
   - Check DHCP lease status on the Voice VLAN scope (`[srv-012]`) if the phone shows `0.0.0.0` or `Obtaining IP`.
2. **Verify SIP Port & Provisioning Server Reachability (from VoIP/office subnet, read-only):**
   ```powershell
   # Verify DNS resolution & TCP/TLS provisioning reachability to VoIP SBC/PBX host
   Resolve-DnsName -Name "sip.example.com" -ErrorAction SilentlyContinue
   Test-NetConnection -ComputerName "sip.example.com" -Port 5061 | Select-Object ComputerName, TcpTestSucceeded
   ```
   - **`SIP_408` (Request Timeout):** Firewall/modem **SIP ALG** corrupting packets, outbound UDP `5060` / TLS `5061` blocked, or WAN outage.
   - **`SIP_403` (Forbidden):** Stale SIP password/extension provisioning, wrong device MAC in VoIP portal, or carrier anti-fraud block.

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Phone model + MAC address (from sticker underneath), exact screen message + IP shown under Status, wall jack label (`W-12`), and whether nearby phones also dropped.

## Deep-Dive Investigation (L3)
1. **Provisioning Lockout / Expired Phone Certificate (`SIP_403` / `Provision Failed`):** Inspect phone web UI (`https://<phone-ip>`) -> `Settings -> Auto Provision` for TLS certificate trust errors on older Yealink/Poly firmware needing an intermediate firmware step.
2. **Switch LLDP-MED & QoS / Router SIP ALG:** Verify switch ports negotiate Voice VLAN cleanly via LLDP-MED and ensure router/firewall **SIP ALG** is strictly **Disabled** (`[net-003]`).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Power-cycling a PoE switch port drops the desk phone AND any PC daisy-chained behind its `PC` pass-through port! Warn the user to save work before unplugging or bouncing the port.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Quick Fix)** Move wall Ethernet cable to the correct **`LAN` / `Internet`** port on the phone, verify snug RJ45 clicks on both ends, or gently unplug the `LAN` cable for **15 seconds** to reboot the phone cleanly.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Switch / Provisioning Fix)** With network admin approval, cycle **PoE** on the single switch port ONLY (confirming Voice VLAN + LLDP enabled), or click **Re-sync / Re-provision** in the cloud PBX portal for the phone's MAC address after confirming extension credentials (`SIP_403`).

## Verification & Post-Fix Checks
1. Confirm the phone screen displays the extension name/number with a solid green line icon (no `No Service` / red X).
2. Place both an **inbound** and **outbound** test call and confirm clear two-way audio and dial tone.

## Cross-Subject Escalation & Pivot Links
- **Desk phone registers yet audio is choppy, robotic, or one-way (SIP ALG / QoS):** [net-003 — Teams and VoIP Choppy Audio, High Jitter, and One-Way Sound Triage](./net-003-teams-voip-choppy-audio-and-jitter.md)
- **Phone gets 169.254.x.x or no IP alongside workstation PC on same drop:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](./net-001-dns-apipa-vpn-triage.md)
- **Entire Voice VLAN scope ran out of DHCP leases on Windows Server:** [srv-012 — Windows Server DHCP Scope Exhausted, DNS AD Load Failure, and Kerberos Time Skew](../08_Servers_Cloud_Infra/srv-012-windows-dhcp-exhausted-dns-forwarder-and-ntp-skew.md)


## Useful Links & External Tools
- **[IPv4 CIDR Subnet Calculator (ipcalc)](https://jodies.de/ipcalc)** — Verify Voice VLAN subnet mask, gateway, and DHCP pool boundaries.
- **[Downdetector](https://downdetector.com/)** — Check upstream SIP trunk / VoIP provider outage reports.
## Client Update Snippets (EN / FR)
- **EN:** We checked the VoIP desk phone cabling / PoE link and SIP registration, re-synced the line profile, and verified dial tone and two-way call audio. Could you try picking up the handset and placing a quick test call?
- **FR:** Nous avons vérifié le câblage / alimentation PoE et l'enregistrement SIP de votre poste téléphonique VoIP, resynchronisé le profil de ligne et validé la tonalité. Pouvez-vous effectuer un court appel test pour confirmer que tout fonctionne ?
