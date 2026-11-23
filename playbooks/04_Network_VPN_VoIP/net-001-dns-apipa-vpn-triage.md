---
id: net-001
domain: 04_Network_VPN_VoIP
subject: "Network, VPN & VoIP"
subcategory: dns_dhcp_wifi_voip
title: No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage
tier: L2
keywords_en:
  - no internet
  - site won't load
  - mapped drive gone
  - vpn drops
  - split tunnel
  - dns not resolving
keywords_fr:
  - pas de réseau
  - pas de reseau
  - pas d'internet
  - vpn coupe
  - lecteur réseau disparu
  - erreur dns
error_codes:
  - "169.254"
  - NXDOMAIN
  - DNS_PROBE_FINISHED_NXDOMAIN
tags:
  - apipa_dhcp
  - dns_resolution
  - vpn_split_tunnel
os:
  - windows
  - macos
  - linux
environment:
  - network
  - hybrid_ad
  - local_endpoint
tools:
  - PowerShell
  - Test-NetConnection
  - ipconfig
  - nslookup
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - srv-012
  - net-002
  - app-001
  - prt-001
  - net-005
---

## Fast Triage (Under 2 Minutes)
- Is the outage isolated to one user/endpoint (`PC-LAB-01`) or affecting an entire office/VLAN?
- Does the problem occur only when connected to VPN, only on Wi-Fi, or also on wired Ethernet?
- Can the endpoint reach numeric IPs (`1.1.1.1`) while hostnames (`contoso.com`, `DC01.domain.local`) fail?

## Read-Only Diagnostics (L1-L2)
1. Inspect active IP configuration, DHCP lease, default gateway, and DNS servers (read-only):
   - **Windows:**
     ```powershell
     ipconfig /all
     Get-NetAdapter | Where-Object Status -eq "Up" | Select-Object Name, InterfaceDescription, LinkSpeed
     ```
     Check for `169.254.x.x` (APIPA = DHCP offer unreachable) or missing default gateway.
   - **macOS / Linux:**
     ```bash
     ifconfig -a || ip addr show
     ```
2. Separate Layer 3 routing from DNS resolution (read-only):
   ```powershell
   Test-NetConnection -ComputerName 1.1.1.1 -InformationLevel Detailed
   Resolve-DnsName -Name "example.com" -ErrorAction SilentlyContinue
   Resolve-DnsName -Name "DC01.domain.local" -ErrorAction SilentlyContinue
   ```
3. When VPN is connected, verify VPN interface state, split-tunnel routes, and SMB/internal port reachability:
   ```powershell
   Get-VpnConnection -AllUserConnection -ErrorAction SilentlyContinue | Select-Object Name, ConnectionStatus, SplitTunneling
   Get-NetRoute -AddressFamily IPv4 | Sort-Object RouteMetric | Select-Object -First 15 DestinationPrefix, NextHop, InterfaceAlias, RouteMetric
   Test-NetConnection -ComputerName 10.0.10.25 -Port 445
   ```

## Deep-Dive Investigation (L3)
1. **APIPA (`169.254.x.x`) Root Cause:** Verify switch port VLAN assignment, DHCP scope exhaustion on the DHCP server, DHCP Snooping trust ports, or 802.1X NAC quarantine.
2. **DNS / `NXDOMAIN` over VPN:** Inspect DNS server priority (`Get-DnsClientServerAddress -AddressFamily IPv4`) and Name Resolution Policy Table (`Get-DnsClientNrptRule`) to confirm internal domains (`domain.local`) route to the internal DNS server rather than ISP/DoH public resolvers.
3. **Asymmetric / Split-Tunnel Drops:** Capture packet loss or MTU fragmentation using `ping -f -l 1360 10.0.10.25` and compare route metrics when both Wi-Fi and VPN adapters hold overlapping subnets (e.g., home `192.168.1.0/24` colliding with office LAN).

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Flush local DNS cache and renew the DHCP lease on `PC-LAB-01`:
   ```cmd
   ipconfig /flushdns
   ipconfig /release
   ipconfig /renew
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If DNS over VPN fails due to stale IPv6 public DNS taking precedence or Winsock corruption, disconnect/reconnect the VPN client cleanly or reset Winsock (requires reboot):
   ```cmd
   netsh winsock reset
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If a DHCP scope is exhausted or an NRPT rule is missing for VPN clients, expand the scope or push the updated VPN DNS suffix/NRPT policy via MDM/GPO.

## Verification & Post-Fix Checks
1. Confirm `ipconfig /all` shows a valid DHCP lease (not `169.254.x.x`) and expected internal/external DNS servers.
2. Verify `Resolve-DnsName` resolves both internal (`DC01.domain.local`) and external (`example.com`) hosts and mapped drives reconnect cleanly.

## Cross-Subject Escalation & Pivot Links
- **Multiple clients receive 169.254 APIPA due to Windows DHCP scope exhaustion or AD DNS failure:** [srv-012 — Windows Server DHCP Scope Exhausted, DNS AD Load Failure, and Kerberos Time Skew](../08_Servers_Cloud_Infra/srv-012-windows-dhcp-exhausted-dns-forwarder-and-ntp-skew.md)
- **APIPA or no-internet happens strictly on corporate Wi-Fi (VLAN / 802.1X RADIUS failure):** [net-002 — Wi-Fi Random Disconnects, Connected Without Internet, and 802.1X Auth Triage](./net-002-wifi-drops-and-8021x-auth.md)
- **Browser websites and LOB SSO fail because local DNS or PAC proxy is unreachable:** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](../09_Apps_LOB/app-001-browser-sso-and-lob-crash.md)
- **Network printer goes Offline when DNS hostname resolution or static IP/WSD breaks:** [prt-001 — Print Spooler Stuck, Offline Printer, and RPC Print Error 0x0000011b](../05_Printers_Devices/prt-001-spooler-and-0x0000011b.md)
- **Branch resources over corporate WAN fail because Site-to-Site IPsec VPN tunnel dropped:** [net-005 — Site-to-Site IPsec VPN Tunnel Down (IKE Phase 1/2 Mismatch & DPD Timeouts)](./net-005-site-to-site-ipsec-vpn-tunnel-down.md)

## Useful Links & External Tools
- **[IPv4 CIDR Subnet Calculator (ipcalc)](https://jodies.de/ipcalc)** — Quickly verify subnet masks, broadcast addresses, and overlapping VPN vs. LAN CIDR blocks.
- **[Hurricane Electric BGP Toolkit](https://bgp.he.net/)** — Look up ISP ASN ownership, reverse PTR DNS, and announced routes during WAN troubleshooting.
- **[Downdetector](https://downdetector.com/)** — Check regional ISP or cloud carrier outage spikes before deep endpoint debugging.

## Client Update Snippets (EN / FR)
- **EN:** We refreshed the network and DNS routing configuration on `PC-LAB-01` and verified both internet and VPN internal connectivity. Please test loading your sites and network drives now.
- **FR:** Nous avons actualisé la configuration réseau et le routage DNS sur `PC-LAB-01`, et validé l'accès Internet ainsi que les ressources internes via VPN. Pouvez-vous tester vos sites et lecteurs réseau maintenant ?
