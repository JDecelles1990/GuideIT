---
id: srv-007
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: linux_os_networking
title: Linux Network Interfaces, LACP Bonding, DNS, and Firewall (nftables/ufw/firewalld)
tier: L2
keywords_en:
  - linux interface no carrier
  - linux bond lacp down
  - linux firewall port blocked
  - linux network unreachable
  - linux ss tcpdump troubleshoot
keywords_fr:
  - interface reseau linux sans lien
  - pare feu linux bloque port
  - probleme reseau serveur linux
  - agregation lacp linux en panne
  - port bloque iptables nftables
error_codes:
  - NO-CARRIER
  - ECONNREFUSED
  - ETIMEDOUT
tags:
  - linux_network_bond
  - linux_firewall_nftables
os:
  - linux
environment:
  - datacenter
  - network
  - cloud_infra
tools:
  - ip
  - ethtool
  - ss
  - tcpdump
  - nft
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - srv-010
  - srv-008
  - srv-004
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is **one specific TCP port blocked** (`443` / `8080` -> `ECONNREFUSED` or `ETIMEDOUT`), OR is the **entire server unreachable from the network (`NO-CARRIER` / VM offline)**?
2. Did someone recently **change firewall rules (`ufw` / `firewalld` / `nftables`)**, edit **Netplan / NIC config**, or move a **rack patch cable / SFP+ module (`[srv-010]`)**?
3. Are other servers on the same VLAN/rack reachable right now?

### Initial Scope & Classification
- Distinguish **Physical / Layer 1 (`NO-CARRIER`)** vs **Service Not Listening (`ECONNREFUSED`)** vs **Firewall / Routing Drop (`ETIMEDOUT`)**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Hypervisor/Switch LED & Safe Read-Only Checks)
1. **Verify Hypervisor NIC "Connected" Checkbox or Onsite Rack Link LED:** If a VM lost networking suddenly, check VMware/Hyper-V/Proxmox VM settings first to make sure the virtual NIC didn't lose its **Connected** checkmark or get moved to the wrong VLAN port group! If physical rack server, check switch/NIC port link LED (`[srv-010]`).
2. **Capture Read-Only Network Snapshot via Out-of-Band Console:** Run **`ip -br addr`** and **`ping -c 3 <default_gateway>`** without changing anything and capture output for L2/L3!

### L2 Technical Diagnostics
1. **Inspect Link State, IP Addresses, Routing Table, and NIC Speed/Duplex (read-only):**
   ```bash
   ip -br link
   ip -br addr
   ip route
   ethtool <iface> 2>/dev/null | grep -iE 'speed|duplex|link detected' || true
   ```
2. **Check LACP / Bond Member Health in Data Center Servers (read-only):**
   ```bash
   cat /proc/net/bonding/bond0 2>/dev/null || true
   ```
   *(Verify `802.3ad` LACP partner aggregator ID and ensure every slave interface shows `MII Status: up`.)*
3. **Check Listening Sockets, DNS Resolvers, and Active Host Firewall Rules (read-only):**
   ```bash
   ss -tulpn
   cat /etc/resolv.conf
   resolvectl status 2>/dev/null | head -n 25 || true
   sudo nft list ruleset 2>/dev/null | head -n 60 || true
   sudo ufw status verbose 2>/dev/null || sudo firewall-cmd --list-all 2>/dev/null || true
   ```

## Deep-Dive Investigation (L3)
1. **Packet-Level Proof with `tcpdump`:** Verify whether inbound SYNs reach the NIC and whether SYN-ACKs leave (asymmetric routing / `rp_filter` drops multi-homed servers!):
   ```bash
   sudo tcpdump -ni <iface> host 198.51.100.10 and port 443 -c 20
   ```
2. **NIC Ring Drops & CRC Errors:** Inspect `ip -s link show <iface>` and `ethtool -S <iface>` for `rx_crc_errors` (bad fiber/patch cable/SFP -> `[srv-010]`) or `rx_dropped`.
3. **Netplan / NetworkManager Config Drift:** Check `/etc/netplan/*.yaml` (Ubuntu) or `/etc/NetworkManager/system-connections/` / `nmcli con show` (RHEL/Rocky) for duplicate default gateways across multiple NICs.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Always backup/use revert-safe timeouts when editing remote server network/firewall rules** (`netplan try --timeout 60` reverts automatically if you lose SSH!).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Open ONLY the required scoped service port/source subnet in the active firewall manager (example: `firewalld` or `ufw`):
   ```bash
   # RHEL/Rocky firewalld example (scoped port)
   sudo firewall-cmd --permanent --add-port=443/tcp
   sudo firewall-cmd --reload
   ```
   ```bash
   # Ubuntu UFW example (scoped source IP 10.0.10.25)
   sudo ufw allow from 10.0.10.25 to any port 443 proto tcp
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If a physical port shows `NO-CARRIER` in the rack, verify cable seating, SFP+ transceiver link (`[srv-010]`), and switch port `no shutdown` / LACP channel-group configuration with the network engineer before bringing the link up (`sudo ip link set <iface> up`).

## Verification & Post-Fix Checks
1. Confirm `ip -br link` shows `UP` (`Link detected: yes` in `ethtool`), `ss -tulpn` shows the expected bind address, and `ping -c 4 <gateway>` / remote `nc -vz 10.0.10.25 443` succeeds.
2. Confirm `/proc/net/bonding/bond0` reports all slave ports `up` with matching LACP partner state.

## Cross-Subject Escalation & Pivot Links
- **Isolate upstream VLAN DHCP, core DNS forwarders, or gateway routing issues:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **NO-CARRIER or LACP link flap traces to faulty SFP+ transceiver or dirty fiber patch:** [srv-010 — Data Center Rack Power (A/B PSU), Thermal Trips, and SFP+/Fiber Optical Diagnostics](./srv-010-datacenter-rack-power-thermal-and-sfp-optics.md)
- **Firewall rules (ufw/firewalld/nftables) block SSH TCP port 22 access:** [srv-008 — Linux SSH Permission Denied, Key Auth, Host Key Mismatch, and PAM Lockout](./srv-008-linux-ssh-permission-denied-and-pam-lockout.md)
- **systemd-networkd or NetworkManager daemon crashed after configuration edit:** [srv-004 — Linux systemd Service Crash, Exit Codes, and journalctl Diagnostics](./srv-004-linux-systemd-service-crash-and-journalctl.md)


## Useful Links & External Tools
- **[IPv4 CIDR Subnet Calculator (ipcalc)](https://jodies.de/ipcalc)** — Validate server CIDR masks, broadcast, and gateway IPs.
- **[Visual Subnet Calculator](https://www.davidc.net/sites/default/subnets/subnets.html)** — Plan non-overlapping VLAN/rack subnet splits.
- **[Hurricane Electric BGP Toolkit](https://bgp.he.net/)** — Verify upstream ASN and public prefix routing.
## Client Update Snippets (EN / FR)
- **EN:** We traced the Linux server network / bond / firewall fault (`NO-CARRIER` / routing / host firewall rule), applied the scoped configuration fix, and verified end-to-end reachability.
- **FR:** Nous avons diagnostiqué l'incident réseau / pare-feu / agrégation LACP sur le serveur Linux, appliqué le correctif ciblé et validé le rétablissement complet de la connectivité.
