---
id: sec-006
domain: 06_Security_Access
subject: "Security & Access"
subcategory: bec_defender_threats
title: Windows Defender Firewall Blocking App, Inbound Port, or Listening Port Conflict
tier: L1
keywords_en:
  - windows firewall blocking app
  - port blocked by firewall windows
  - port already in use windows
  - cannot reach service port windows
  - listening ports audit windows
keywords_fr:
  - pare-feu windows bloque application
  - port bloque par pare-feu windows
  - port deja utilise windows
  - verifier ports ecoute windows
  - pare-feu bloque rdp sql
error_codes:
  - WSAEADDRINUSE
  - 0x80072740
  - FIREWALL_BLOCK
  - "5152"
tags:
  - windows_firewall_block
  - listening_port_conflict
os:
  - windows
environment:
  - local_endpoint
  - hybrid_ad
  - on_prem_ad
  - network
tools:
  - Windows Defender Firewall (wf.msc)
  - PowerShell
  - netstat
  - Test-NetConnection
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-003
  - srv-016
  - net-001
  - sec-002
  - srv-015
linked_scripts:
  - 07_Servers_Infra/Get-FirewallAndListeningPorts.ps1
  - 05_Security_Defender/Get-FirewallStatus.ps1
  - 02_Network/Get-ListeningPorts.ps1
  - 02_Network/Test-PortConnectivity.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is a client PC (`PC-LAB-01`) **unable to connect inbound** to an application/RDP/SQL/printer port on a host (`FIREWALL_BLOCK`), OR does an application fail to start locally with **`Address already in use` (`WSAEADDRINUSE` / `0x80072740`)**?
2. Which **exact TCP/UDP port and application executable** are affected (e.g., RDP `3389`, SQL `1433`, SMB `445`, HTTP/HTTPS `8080/8443`, printer `9100`), and is the issue happening **over VPN / Office LAN**?
3. Did Windows recently switch the network connection from **Domain / Private** to **`Public network`** (very common on laptops or after VPN/NIC resets — causing Windows Firewall to silently drop LAN/RDP/file sharing)?
4. Is the client running **only Windows Defender Firewall**, or also a third-party endpoint firewall (Bitdefender, Sophos, SentinelOne, Norton, McAfee)?

### Initial Scope & Classification
- Separate three classic causes quickly:
  1. **Service Isn't Actually Listening:** No process bound on the port (no firewall change will fix a stopped service!).
  2. **Windows Firewall Network Profile (`Public` vs `Domain`/`Private`) or Rule Block (`FIREWALL_BLOCK`):** Service is listening, but Defender Firewall drops inbound connections cleanly.
  3. **Listening Port Conflict (`WSAEADDRINUSE` / `0x80072740`):** Another PID (IIS, Skype/Teams, Hyper-V NAT, or stale background service) already owns the target port.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — GUI Network Profile & Firewall Status)
1. **Check Network Profile (`Public` vs `Domain` / `Private`) in Windows Settings (Zero CLI!):**
   - Open **Settings -> Network & internet -> Ethernet / Wi-Fi -> Properties**: if **Network profile type** switched to **`Public network (Recommended)`** inside a trusted office LAN, Defender Firewall applies strict public blocks!
2. **Inspect Firewall Status & Active Listening Ports with Built-in Safe Scripts:**
   - Run **`psstore://05_Security_Defender/Get-FirewallStatus.ps1`** to verify whether Domain/Private/Public firewall profiles are enabled, default inbound action is `Block`, and whether Intune/GPO overrides local rules.
   - Run **`psstore://02_Network/Get-ListeningPorts.ps1`** on the host to verify **which exact PID/executable owns the port** (or whether nothing is listening on that port at all!).
   - Run **`psstore://02_Network/Test-PortConnectivity.ps1`** from a second workstation or admin terminal against `10.0.10.25` to verify TCP reachability.
3. **Inspect Windows Defender Firewall GUI (`wf.msc`):** Open `wf.msc` -> **Inbound Rules** -> sort by **Enabled = Yes** and **Action = Block**, looking for conflicting **Block** rules (note: Windows Firewall explicit `Block` rules always override `Allow` rules!).

### L2 Technical Diagnostics
1. **Inspect Network Profile, Active Firewall Profiles, and Matching Inbound Rules (read-only PowerShell):**
   ```powershell
   Get-NetConnectionProfile | Select-Object InterfaceAlias, NetworkCategory, IPv4Connectivity
   Get-NetFirewallProfile | Select-Object Name, Enabled, DefaultInboundAction, DefaultOutboundAction, AllowLocalFirewallRules
   Get-NetFirewallRule -Direction Inbound -Enabled True |
       Where-Object { $_.DisplayName -match "SQL|Remote Desktop|SMB|LOB|8080" } |
       Select-Object DisplayName, Profile, Action, Direction | Format-Table -AutoSize
   ```
2. **Verify Port Ownership & Conflict PID + Remote Port Reachability (read-only):**
   ```powershell
   Get-NetTCPConnection -LocalPort 3389,1433,8080 -State Listen -ErrorAction SilentlyContinue |
       Select-Object LocalAddress, LocalPort, State, OwningProcess, @{N='Process';E={(Get-Process -Id $_.OwningProcess -ErrorAction SilentlyContinue).ProcessName}}
   Test-NetConnection -ComputerName 10.0.10.25 -Port 1433
   ```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact target TCP/UDP port, `Get-NetConnectionProfile` category (`Domain`/`Private`/`Public`), output from `Get-ListeningPorts.ps1` (listening PID or missing listener), `Test-PortConnectivity.ps1` result, and whether GPO/Intune manages `AllowLocalFirewallRules`.

## Deep-Dive Investigation (L3)
1. **Windows Filtering Platform (WFP) Drop Auditing (`Event ID 5152` / `5157`):** If `wf.msc` rules appear allowed yet traffic drops silently, enable/inspect **Security Log** for **`Event ID 5152`** (`The Windows Filtering Platform has blocked a packet`) to see exact **Source/Dest Port, Filter Run-Time ID, and Application Path**.
2. **GPO / Intune CSP Override (`AllowLocalFirewallRules = False`):** On Domain/Intune-managed servers (`[id-004]`), locally added `New-NetFirewallRule` entries are ignored unless merged with Group Policy / Intune Endpoint Security Firewall policies (`MDMWinsOverGP`).
3. **Windows Dynamic Ephemeral / Hyper-V Port Reservation (`netsh int ipv4 show excludedportrange`):** Docker/WSL2/Hyper-V (`[srv-015]`) can reserve dynamic TCP blocks (`WSAEADDRINUSE` / `0x80072740`) before an app binds its configured port even when `netstat` shows nothing listening!

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER turn off Windows Defender Firewall completely (`Set-NetFirewallProfile -Enabled False`) as a permanent fix! Always create a tightly scoped **port + executable + source-subnet + Domain/Private profile** rule after confirming change approval.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Resolve Port Conflict `WSAEADDRINUSE` / Wrong Profile)**
   - If `Get-ListeningPorts.ps1` shows an orphaned/rogue process holding the port, close or restart that conflicting service cleanly (or re-bind the target app's port if approved).
   - If an unmanaged NIC is stuck on `Public`, switch verified trusted adapters back to `Private` (`Set-NetConnectionProfile -InterfaceIndex <Idx> -NetworkCategory Private`); on Domain PCs experiencing failed NLA domain detection, verify DC connectivity/DNS (`[net-001]` / `[id-005]`).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Add Tightly Scoped Windows Firewall Inbound Allow Rule)** Replace port, program path, and approved internal subnet (`10.0.10.0/24`) cleanly (or deploy via Intune/GPO if centrally managed):
   ```powershell
   New-NetFirewallRule -DisplayName "Allow-ApprovedLOB-TCP8080" `
       -Direction Inbound `
       -Protocol TCP `
       -LocalPort 8080 `
       -RemoteAddress "10.0.10.0/24" `
       -Profile Domain,Private `
       -Action Allow
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Resolve GPO / WFP Conflicts)** Remove any overriding explicit `Block` rule for the verified business executable in `wf.msc` / Intune Endpoint Security -> Firewall, or adjust Windows NAT excluded port ranges if `0x80072740` hits Hyper-V/Docker exclusions.

## Verification & Post-Fix Checks
1. Re-run **`psstore://05_Security_Defender/Get-FirewallStatus.ps1`** and confirm all three profiles (`Domain`, `Private`, `Public`) remain **Enabled** while the new scoped rule is active.
2. Re-run **`psstore://02_Network/Get-ListeningPorts.ps1`** on the host and **`psstore://02_Network/Test-PortConnectivity.ps1`** from a peer workstation to confirm `TcpTestSucceeded = True`.

## Cross-Subject Escalation & Pivot Links
- **RDP fails NLA or port 3389 unreachable on Windows Server:** [srv-003 — Remote Desktop (RDP) Refused, CredSSP Encryption Oracle, and NLA Failure](../08_Servers_Cloud_Infra/srv-003-rdp-credssp-and-nla-connection-failed.md)
- **SQL Server port 1433/1434 unreachable or Login Failed 18456:** [srv-016 — SQL Server Login Failed (18456), Transaction Log Full (9002) & Deadlocks](../08_Servers_Cloud_Infra/srv-016-sql-server-login-18456-log-full-9002-and-blocking.md)
- **Local DNS, APIPA, or VPN routing blocks host reachability before hitting firewall:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Defender Antivirus / SmartScreen / ASR blocks the executable before it opens a socket:** [sec-002 — Microsoft Defender ASR Rule or Antivirus Blocking Legitimate LOB App or Macro](./sec-002-defender-asr-block-and-false-positive.md)
- **Container or service port binding collision (`EADDRINUSE`) on Linux/Docker hosts:** [srv-015 — Docker Container CrashLoopBackOff, Port Conflicts (EADDRINUSE) & Overlay2 Disk Full](../08_Servers_Cloud_Infra/srv-015-docker-container-crashloop-and-overlay-disk.md)


## Useful Links & External Tools
- **[IPv4 CIDR Subnet Calculator (ipcalc)](https://jodies.de/ipcalc)** — Verify trusted local subnet scopes when scoping Windows Firewall rules.
## Client Update Snippets (EN / FR)
- **EN:** We audited Windows Defender Firewall rules and active listening ports on `PC-LAB-01`, resolved the network profile / port rule block (without disabling endpoint firewall protection), and verified port connectivity. Could you test the application connection again and confirm it works normally?
- **FR:** Nous avons vérifié les règles du pare-feu Windows Defender et les ports d'écoute actifs sur `PC-LAB-01`, corrigé le blocage de profil ou de règle (sans désactiver le pare-feu) et validé la connectivité réseau. Pouvez-vous tester l'application et confirmer que la connexion fonctionne normalement ?
