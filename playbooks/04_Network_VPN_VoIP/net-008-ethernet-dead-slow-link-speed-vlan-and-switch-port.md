---
id: net-008
domain: 04_Network_VPN_VoIP
subject: "Network, VPN & VoIP"
subcategory: ethernet_proxy_filtering
title: Wired Ethernet Dead, 100 Mbps Slow Link Speed, VLAN Mismatch, and Switch Port Triage
tier: L1
keywords_en:
  - ethernet not working cable unplugged
  - slow wired internet capped 100 mbps
  - network cable disconnected ethernet
  - dock ethernet not working wrong vlan
  - switch port shut down 802.1x wired
keywords_fr:
  - cable ethernet ne fonctionne pas debranche
  - reseau filaire lent bloque 100 mbps
  - port ethernet station accueil vlan
  - port switch desactive reseau bureau
  - carte reseau filaire introuvable
error_codes:
  - MEDIA_DISCONNECTED
  - LINK_100MBPS
  - VLAN_MISMATCH
  - 8021X_PORT_BLOCK
tags:
  - ethernet_no_link
  - slow_link_speed_100mbps
  - vlan_switch_port
os:
  - windows
  - macos
environment:
  - network
  - local_endpoint
tools:
  - PowerShell
  - Device Manager
  - Network Switch CLI / Portal
  - Speedtest / iPerf3
risk_level: low
requires_admin: false
last_verified: 2026-11-23
related_ids:
  - net-001
  - net-002
  - net-007
  - prt-003
linked_scripts:
  - 02_Network/Get-WebProxyAndTLSDiagnostics.ps1
  - 02_Network/Get-NetworkSnapshot.ps1
  - 02_Network/Test-NetworkQuality.ps1
  - 02_Network/Reset-NetworkStack.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are the **link lights (green/amber LEDs)** turned on where the patch cord plugs into the laptop/desktop or USB-C dock (`prt-003`), AND at the wall jack / VoIP desk phone passthrough (`net-007`)?
2. Is wired Ethernet **completely dead (`Network cable unplugged` / `MEDIA_DISCONNECTED`)**, getting the **wrong subnet/no corporate access (`VLAN_MISMATCH`)**, or working but capped around **90–95 Mbps (`LINK_100MBPS`)** instead of **1 Gbps / 2.5 Gbps**?
3. Are coworkers at adjacent desks plugged into the **same floor switch** also offline, or did someone just move desks or swap a patch cable / USB-C dock?
4. When unplugging the patch cable and connecting to **corporate Wi-Fi**, does internet/VPN start working immediately?

### Initial Scope & Classification
- **Zero link lights on laptop & known-good cable:** Faulty wall jack (unpatched in IDF closet), PoE switch port disabled/err-disabled (`8021X_PORT_BLOCK`), daisy-chained through an unpowered VoIP phone (`net-007`), or dead USB-C dock NIC (`prt-003`).
- **Link Up but capped at `100 Mbps` (`LINK_100MBPS`):** Broken pair in a Cat5e/Cat6 patch cord or wall punch-down (Gigabit requires all 4 wire pairs; 100 Mbps runs on only 2 pairs!), or NIC `Speed & Duplex` manually pinned to `100 Mbps Half/Full`.
- **Link Up at `1.0 Gbps` with `169.254.x.x` or wrong IP range (`VLAN_MISMATCH`):** Switch port tagged/untagged in wrong voice/guest/quarantine VLAN or 802.1X wired authentication failure.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Physical Layer & Windows Status)
1. **Inspect Physical Cable Path (`PC-LAB-01` -> Dock -> Phone -> Wall Jack):**
   - Check if Ethernet runs **through the back of an office VoIP phone (`PC` port)** — if the phone lost PoE power or rebooted, the PC loses link (`net-007`). Plug Ethernet **directly** into the laptop/dock temporarily to isolate the phone!
   - Test a **known-good factory Cat6 patch cord** and verify the RJ45 clip clicks firmly (broken latch = intermittent `MEDIA_DISCONNECTED`).
2. **Check Link Speed in Windows Settings (`Settings -> Network & internet -> Ethernet`):**
   - Look at **`Aggregated link speed (Receive/Transmit)`**: **`100/100 (Mbps)`** proves a 2-pair cable/jack fault or forced duplex mismatch; **`1000/1000 (Mbps)`** proves Gigabit PHY negotiation succeeded.
3. **Check USB-C / Thunderbolt Dock vs Onboard NIC (`[prt-003]`):**
   - If using a USB-C dock Ethernet port, test a direct USB-C Ethernet dongle or Wi-Fi; check Device Manager -> **Network adapters** for yellow exclamation marks (`Code 10` / `Code 43`) or disabled `Realtek USB GbE Family Controller`.

### L2 Technical Diagnostics
1. **Audit Physical Adapter State, Negotiated Link Speed, IP/Subnet & Gateway on `PC-LAB-01` (read-only):**
   ```powershell
   # Check Ethernet/USB NIC operational state and negotiated link speed
   Get-NetAdapter -IncludeHidden |
       Where-Object { $_.InterfaceDescription -notmatch 'Loopback|VirtualBox|WAN Miniport' } |
       Select-Object Name, InterfaceDescription, Status, LinkSpeed, FullDuplex, MacAddress |
       Format-Table -AutoSize

   # Check assigned IPv4 subnet, gateway, and DHCP server (expose wrong VLAN or APIPA!)
   Get-NetIPConfiguration |
       Select-Object InterfaceAlias, IPv4Address, IPv4DefaultGateway, DNSServer |
       Format-List

   # Inspect NIC Speed & Duplex / Energy Efficient Ethernet (EEE) advanced driver settings (read-only)
   Get-NetAdapterAdvancedProperty -Name "*Ethernet*" -ErrorAction SilentlyContinue |
       Where-Object { $_.DisplayName -match 'Speed|Duplex|Energy|Green|Flow' } |
       Select-Object Name, DisplayName, DisplayValue
   ```
   *(Run the linked `02_Network/Get-WebProxyAndTLSDiagnostics.ps1`, `02_Network/Get-NetworkSnapshot.ps1`, and `02_Network/Test-NetworkQuality.ps1` scripts directly from PowerShellStore.)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact wall jack / floor drop label (`e.g., B-24`), USB-C dock model, MAC address of Ethernet NIC, negotiated link speed (`100 Mbps` vs `1 Gbps`), assigned IPv4 subnet vs expected office VLAN, and whether a direct patch cable swap changed link LEDs.

## Deep-Dive Investigation (L3)
1. **Switch Port Telemetry, Duplex Errors, and 802.1X NAC Quarantine:** Check managed switch logs (`show interface status`, `show interface counters errors`, `show dot1x all`) for FCS/CRC frame errors (bad wall cable), `err-disable` (BPDU guard / port-security MAC limit hit when plugging in a mini-switch or dock), or RADIUS 802.1X placing `PC-LAB-01` on a restricted remediation VLAN.
2. **NIC Power Saving / Energy-Efficient Ethernet (EEE) & USB Selective Suspend:** Certain Realtek/Intel dock NICs drop carrier intermittently or fall back from 1 Gbps to 100 Mbps when **Energy-Efficient Ethernet (EEE)** or **Green Ethernet** conflicts with older Cisco/Aruba/UniFi switches.
3. **VLAN Subnet Validation:** Use [IPv4 CIDR Subnet Calculator](https://jodies.de/ipcalc) to verify whether the IP handed to `PC-LAB-01` belongs to Staff Data VLAN vs Guest/IoT/Voice VLAN before escalating switch trunk/access config changes.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Never change switch port VLANs, disable 802.1X security, or reset the TCP/IP stack while remotely connected solely over that same Ethernet adapter without a secondary Wi-Fi / out-of-band session.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Physical Swap & Clean Dock Re-Enumeration)**
   - Replace damaged patch cables showing `100/100 Mbps` or bent pins, bypass chained VoIP phones directly to the wall jack to test, and power-cycle USB-C docks (`30 seconds` unplugged from AC + laptop) to reset hung Realtek/ASIX USB NICs.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Restore `Auto Negotiation` & Renew DHCP Lease)**
   ```powershell
   # Confirm Ethernet interface name first with Get-NetAdapter
   # Restore Speed & Duplex to Auto Negotiation (fixes forced 100 Mbps pins)
   Set-NetAdapterAdvancedProperty -Name "Ethernet" -DisplayName "Speed & Duplex" -DisplayValue "Auto Negotiation" -ErrorAction Stop
   # Renew DHCP lease on the wired interface
   ipconfig /release "Ethernet"
   ipconfig /renew "Ethernet"
   ```
   - Or run `02_Network/Reset-NetworkStack.ps1` with `FlushDNS` and `RenewDHCP` checked (keep `ResetWinsock` / `ResetTCPStack` disabled first if connected remotely!).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L3 Switch Port Bounce / VLAN & Dot1X Remediation)**
   - On the network switch (`IDF/MDF`), bounce the `err-disabled` port (`shutdown` / `no shutdown`), clear stale port-security MAC bindings, or tag/untag the correct Data VLAN (`show interface` verification) and confirm `Authentication Manager` re-authorizes `PC-LAB-01`.

## Verification & Post-Fix Checks
1. Verify `Get-NetAdapter` reports `Status = Up` and `LinkSpeed = 1 Gbps` (or expected port speed) without carrier flaps over 2–3 minutes.
2. Confirm `ipconfig /all` receives the proper corporate VLAN IPv4 address, gateway, and internal DNS servers, and run `02_Network/Test-NetworkQuality.ps1` showing `0%` packet loss and low latency (`< 5 ms` LAN).

## Cross-Subject Escalation & Pivot Links
- **Ethernet link is Up at 1 Gbps, yet IP is `169.254.x.x` or DNS fails:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](./net-001-dns-apipa-vpn-triage.md)
- **Switched to Wi-Fi and experiencing random drops or 802.1X certificate failures:** [net-002 — Wi-Fi Random Disconnects, Connected Without Internet, and 802.1X Auth Triage](./net-002-wifi-drops-and-8021x-auth.md)
- **VoIP desk phone on the same wall drop also has no power or dial tone:** [net-007 — Office VoIP Desk Phone No Dial Tone, PoE Power Down, or Stuck Registering](./net-007-voip-desk-phone-no-dial-tone-poe-or-registering.md)
- **Ethernet fails ONLY through the USB-C / Thunderbolt docking station:** [prt-003 — USB-C / Thunderbolt Docking Station External Monitors Blank or Flickering](../05_Printers_Devices/prt-003-usbc-dock-monitors-not-detected.md)

## Useful Links & External Tools
- **[IPv4 CIDR Subnet Calculator](https://jodies.de/ipcalc)** — Confirm whether the DHCP IP received by the Ethernet adapter matches the intended office Data VLAN vs Voice/Guest subnet.
- **[Visual Subnet Calculator](https://www.davidc.net/sites/default/subnets/subnets.html)** — Map overlapping VLANs and switch port subnet boundaries when diagnosing wrong-VLAN drops.
- **[Microsoft 365 Network Connectivity Test](https://connectivity.office.com/)** — Benchmark wired Ethernet throughput, latency, and packet loss after link restoration.

## Client Update Snippets (EN / FR)
- **EN:** We isolated the wired network slowdown/disconnection on `PC-LAB-01` to the Ethernet link/patch path, verified the port now negotiates at full Gigabit speed on the proper office network, and confirmed zero packet loss. Could you please test your wired connection and confirm everything is working smoothly?
- **FR:** Nous avons isolé la perte de lien ou la lenteur filaire sur `PC-LAB-01`, vérifié que le port Ethernet négocie maintenant à pleine vitesse Gigabit sur le bon réseau et confirmé l'absence de perte de paquets. Pouvez-vous tester votre connexion filaire et confirmer que tout fonctionne bien ?
