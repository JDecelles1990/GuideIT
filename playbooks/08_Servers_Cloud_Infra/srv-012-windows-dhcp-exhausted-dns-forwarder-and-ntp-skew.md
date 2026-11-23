---
id: srv-012
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: windows_server_sql
title: Windows Server DHCP Scope Exhausted, DNS AD Load Failure, and Kerberos Time Skew
tier: L3
keywords_en:
  - dhcp scope full
  - dns forwarder failing server
  - kerberos clock skew
  - event 1020 dhcp exhausted
  - dns event 4013 ad integrated
keywords_fr:
  - plage dhcp saturee
  - decalage horaire kerberos ntp
  - serveur dhcp plein 1020
  - erreur dns ad 4013
  - synchronisation heure controleur domaine
error_codes:
  - "1020"
  - "1342"
  - "4013"
  - KRB_AP_ERR_SKEW
tags:
  - dhcp_scope_exhausted
  - kerberos_ntp_skew
os:
  - windows
environment:
  - on_prem_ad
  - hybrid_ad
  - network
tools:
  - PowerShell
  - DHCP Console
  - DNS Manager
  - w32tm
  - Event Viewer
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - id-004
  - id-005
  - prt-001
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are **all/many devices on an entire office floor or Wi-Fi VLAN** suddenly getting `No Internet` / `169.254.x.x` (`DHCP` scope exhaustion), or is **only one PC (`PC-LAB-01`)** affected (`[net-001]`)?
2. Do users see **`There are currently no logon servers available`** / Kerberos errors, and is the **system clock/time wrong** on workstations or servers (`KRB_AP_ERR_SKEW`)?
3. Did a **Domain Controller (`DC01.domain.local`) just reboot** after updates or a power outage (`4013` DNS waiting for AD)?

### Initial Scope & Classification
- **DHCP Scope Full (`1020` / `1342`):** Endpoints suddenly get `169.254.x.x` (`[net-001]`) while DHCP Server logs `Event ID 1020` (scope `>= 80%`/`100%` full) or `1342` (no free leases left in scope).
- **AD-Integrated DNS Stalled (`Event ID 4013`):** After rebooting an isolated/first Domain Controller (`DC01.domain.local`), DNS waits for AD replication before loading zones, blocking AD logon and DNS queries!
- **Kerberos Clock Skew (`KRB_AP_ERR_SKEW` / `Event ID 36`):** Clients/servers > **5 minutes** out of sync with the **PDC Emulator** (`DC01.domain.local`) fail Kerberos authentication, SSO, and GPO/SMB access!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Check Windows Services on `DC01.domain.local` / DHCP Server (`services.msc` GUI):** Confirm **`DHCP Server`**, **`DNS Server`**, **`Windows Time` (`w32time`)**, and **`Active Directory Domain Services`** are all **Running**!
2. **Visually Inspect DHCP Scope Percentage in DHCP Console (`dhcpmgmt.msc`):** Expand **IPv4 -> Target Scope -> Address Leases** and check **Display Statistics**: is the scope at **99–100% Used** (especially full of expired phones or `BAD_ADDRESS` blue-pencil icons!)?
3. **Compare Clocks (`PC-LAB-01` vs `DC01.domain.local`):** Glance at the taskbar time on `PC-LAB-01` vs `DC01.domain.local` — if either clock is off by **more than 5 minutes** (or wrong time zone / AM vs PM!), flag `KRB_AP_ERR_SKEW` immediately!

### L2 Technical Diagnostics
1. **Check Windows Server DHCP Scope Utilization & Failover State (read-only on DHCP server):**
   ```powershell
   Get-DhcpServerv4Scope | Select-Object ScopeId, Name, SubnetMask, StartRange, EndRange, LeaseDuration, State
   Get-DhcpServerv4ScopeStatistics | Select-Object ScopeId, AddressesFree, AddressesInUse, PercentageInUse
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-DHCP-Server'; Id = 1020, 1063, 1342; StartTime = (Get-Date).AddDays(-2) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, Message
   ```
2. **Check Windows DNS Server Forwarders, Zone Health, and `Event ID 4013` (read-only on `DC01.domain.local`):**
   ```powershell
   Get-DnsServerForwarder
   Get-DnsServerZone | Select-Object ZoneName, ZoneType, IsDsIntegrated, IsPaused
   Get-WinEvent -FilterHashtable @{ LogName = 'DNS Server'; Id = 4013, 4015, 5504; StartTime = (Get-Date).AddDays(-2) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, Message
   ```
3. **Check AD Domain Time Hierarchy & NTP Sync Drift across all DCs (read-only):**
   ```cmd
   w32tm /monitor
   w32tm /query /status
   w32tm /query /configuration
   ```
   *(Only the **PDC Emulator** should sync from an external NTP source like `pool.ntp.org` / `time.windows.com`; all other DCs and member workstations MUST use `NT5DS` AD hierarchy! Also disable hypervisor Host-to-Guest Time Sync on virtual DCs if the hypervisor clock drifts!)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Number of affected endpoints (`1` vs entire VLAN), `Get-DhcpServerv4ScopeStatistics` output, clock difference vs actual internet time, and any `1020 / 1342 / 4013` event logs.

## Deep-Dive Investigation (L3)
1. **Rogue DHCP or Long 8-Day Guest Wi-Fi Leases (`1342`):** Smartphones/BYOD devices joining a corporate VLAN with 8-day lease duration quickly exhaust `/24` scopes (`254` IPs); also check `BAD_ADDRESS` entries (conflict detection grabbing IPs when static devices aren't excluded!).
2. **DNS Island / Chicken-and-Egg `4013`:** If every DC points its primary NIC DNS solely to another rebooted DC (or only to `127.0.0.1` without peering), `repadmin` and AD-integrated DNS deadlock after power outages! Always set Primary DNS = partner DC IP, Secondary DNS = own LAN IP (and avoid listing external public DNS like `1.1.1.1` on AD domain-joined endpoints/DC NICs!).
3. **Hypervisor VM Host Time Overwriting PDC Emulator (`KRB_AP_ERR_SKEW`):** Hyper-V **Time Synchronization Integration Service** or VMware Tools periodic host-time sync often snaps virtual `DC01` back to an unsynced host clock.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Start Stopped DHCP/DNS Service & Re-Sync Single Workstation Time)** If `DHCP Server` or `DNS Server` is `Stopped` in `services.msc`, start it cleanly. For a single workstation off by >5 minutes (`KRB_AP_ERR_SKEW`) while `DC01` is healthy, resync time on `PC-LAB-01` (`w32tm /resync /force`) and refresh lease (`ipconfig /release && ipconfig /renew`).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Relieve Exhausted DHCP Scope `1020` / `1342`)**
   - Inspect and remove confirmed stale `BAD_ADDRESS` or expired BYOD leases, reduce overly long lease durations on high-churn Wi-Fi/VPN VLANs (e.g., 8 days -> 8–24 hours), or expand scope range/superscope per approved IP plan (and run **Reconcile** if database inconsistencies exist).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L3 Fix PDC Emulator NTP Sync `KRB_AP_ERR_SKEW`)** Run ONLY on the **PDC Emulator** (`DC01.domain.local`, requires UDP `123` outbound to NTP peers):
   ```cmd
   w32tm /config /manualpeerlist:"0.pool.ntp.org,0x8 1.pool.ntp.org,0x8" /syncfromflags:manual /reliable:YES /update
   net stop w32time && net start w32time
   w32tm /resync /rediscover
   ```
   *(Then on member servers/clients: `w32tm /config /syncfromflags:domhier /update && w32tm /resync /force`.)*
4. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L3 Resolve `Event ID 4013` DNS Startup)** Verify AD replication (`repadmin /replsummary`) and NIC DNS order on `DC01.domain.local`, then restart `DNS` service if zones failed initial load (`Restart-Service DNS`).

## Verification & Post-Fix Checks
1. Confirm `Get-DhcpServerv4ScopeStatistics` shows `< 80%` utilization and endpoints renew valid DHCP leases without APIPA (`169.254.x.x`).
2. Confirm `w32tm /monitor` reports `< 1s` offset across all DCs and `dcdiag /test:dns` passes cleanly.

## Cross-Subject Escalation & Pivot Links
- **Client symptoms (169.254 APIPA / NXDOMAIN) confirm scope of DHCP/DNS server issue:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Broken AD DNS _msdcs SRV records or clock drift block Group Policy application (1055/1058):** [id-004 — Active Directory GPO Not Applying, SYSVOL Permissions, and DFSR Replication Errors](../01_Identity_AD_Entra/id-004-ad-gpo-not-applying-replication-and-dfsr.md)
- **NTP time skew >5 min (KRB_AP_ERR_SKEW) breaks computer domain trust (5722):** [id-005 — Windows Domain Trust Relationship Failed (Event ID 5722 / 3210 / 0xC000018B)](../01_Identity_AD_Entra/id-005-windows-domain-trust-relationship-failed.md)
- **DHCP pool exhaustion or lease conflict knocks TCP/IP office printers offline:** [prt-001 — Print Spooler Stuck, Offline Printer, and RPC Print Error 0x0000011b](../05_Printers_Devices/prt-001-spooler-and-0x0000011b.md)

## Useful Links & External Tools
- **[IPv4 CIDR Subnet Calculator (ipcalc)](https://jodies.de/ipcalc)** — Calculate exact host ranges and broadcast masks before expanding DHCP scopes.
- **[Visual Subnet Calculator](https://www.davidc.net/sites/default/subnets/subnets.html)** — Carve and split VLAN / DHCP ranges without overlapping existing static infrastructure.

## Client Update Snippets (EN / FR)
- **EN:** We cleared the Windows Server DHCP scope exhaustion / DNS / NTP time-skew fault on `DC01.domain.local` and verified domain authentication and lease assignment are healthy. Could affected users reconnect or run `ipconfig /renew` and confirm connectivity?
- **FR:** Nous avons résolu le problème de saturation DHCP / DNS / décalage horaire NTP sur `DC01.domain.local` et validé la reprise normale des baux IP et de l'authentification Kerberos. Les utilisateurs concernés peuvent-ils tester de nouveau leur connexion ?
