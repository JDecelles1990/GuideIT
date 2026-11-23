---
id: srv-003
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: windows_server_sql
title: Remote Desktop (RDP) Refused, CredSSP Encryption Oracle, and NLA Failure
tier: L2
keywords_en:
  - rdp won't connect
  - remote desktop credssp
  - remote desktop nla error
  - rdp connection refused
  - cannot rdp to server
keywords_fr:
  - bureau a distance refuse
  - erreur rdp nla
  - connexion bureau a distance echouee
  - erreur credssp rdp
  - impossible de se connecter en rdp
error_codes:
  - "0x00000800"
  - CREDSSP
tags:
  - rdp_credssp_nla
  - remote_desktop_failed
os:
  - windows
environment:
  - on_prem_ad
  - hybrid_ad
  - cloud_infra
tools:
  - PowerShell
  - Test-NetConnection
  - Event Viewer
  - Group Policy
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - win-001
  - net-001
  - id-001
  - srv-013
linked_scripts:
  - 02_Network/Get-ListeningPorts.ps1
  - 02_Network/Test-PortConnectivity.ps1
  - 05_Security_Defender/Get-FirewallStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Does RDP fail for **only ONE user (`jsmith@example.com`)** (`Credentials did not work` / missing permissions) or for **EVERYONE** (`Remote Desktop can't connect to the remote computer` / `CredSSP`)?
2. Are you trying to connect **over corporate VPN** (verify VPN is actually Connected -> `[net-001]`) vs **inside the office LAN**?
3. Screenshot the exact popup (`CredSSP encryption oracle remediation`, `Network Level Authentication`, `Your account has been locked out`, or `Remote computer turned off`)!
4. Can you still access **shared folders (`\\SRV-FILE-01`)** or **RMM/hypervisor console** on `SRV-FILE-01` (checking if the server itself crashed/froze)?

### Initial Scope & Classification
- Verify caller isn't locked out (`[id-001]`), VPN is active, target server `SRV-FILE-01` is powered ON in hypervisor/Azure (`[srv-013]`), and caller belongs to **Remote Desktop Users**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic Server Health, Lockout & GUI Checks)
1. **Verify Server Is Online & User Account Isn't Locked:** Check RMM dashboard / hypervisor console (confirm `SRV-FILE-01` isn't frozen on Windows Update reboot or BitLocker!), verify `jsmith@example.com` isn't locked out (`[id-001]`), and test connecting with `DOMAIN\jsmith` username format!
2. **Check VPN & Windows RDP Service (`services.msc` + `System Properties -> Remote` via RMM):** Verify **`Remote Desktop Services` (`TermService`)** is `Running` and **`Remote Desktop Users`** group includes `jsmith` or their AD group (`lusrmgr.msc`).

### L2 Technical Diagnostics
1. **Test TCP `3389` reachability from client `PC-LAB-01` (read-only):**
   ```powershell
   Test-NetConnection -ComputerName "SRV-FILE-01" -Port 3389 | Select-Object ComputerName, RemoteAddress, TcpTestSucceeded
   ```
2. **On the target server (`SRV-FILE-01`, via RMM/console/WinRM), check `TermService`, listening port, NLA setting, and active sessions (read-only):**
   ```powershell
   Get-Service TermService, UmRdpService | Select-Object Name, Status, StartType
   Get-NetTCPConnection -LocalPort 3389 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, State
   Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp" -Name UserAuthentication, SecurityLayer
   Get-LocalGroupMember -Group "Remote Desktop Users" | Select-Object Name, ObjectClass
   ```
   ```cmd
   qwinsta
   ```
3. **Inspect TerminalServices Operational Logs on `SRV-FILE-01`:**
   - `Microsoft-Windows-TerminalServices-RemoteConnectionManager/Operational` and `LocalSessionManager/Operational` (check `Event ID 1149` / `21` / `25` or Windows Firewall drop logs).

## Deep-Dive Investigation (L3)
1. **CredSSP Encryption Oracle Remediation (`CREDSSP` / CVE-2018-0886):** Occurs when either `PC-LAB-01` or `SRV-FILE-01` is patched to `Force Updated Clients` while the peer server/client lacks CredSSP updates (`AllowEncryptionOracle` policy under `HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\CredSSP\Parameters`). **Always patch the out-of-date host rather than permanently weakening CredSSP!**
2. **NLA Failure Without Domain Controller Reachability:** When NLA (`UserAuthentication = 1`) is enabled, Kerberos/NTLM authentication occurs BEFORE a session opens; if `SRV-FILE-01` lost trust/connectivity to `DC01.domain.local`, domain RDP users fail even though local Administrator succeeds.
3. **RDP Session Exhaustion / Hung `rdpclip` or Stale Disconnected Sessions:** On RDS/servers allowing only 2 admin sessions, stale `Disc` sessions block new admins until cleanly logged off.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `jsmith@example.com` lacks authorization on `SRV-FILE-01`, add them (or their scoped AD security group) to **Remote Desktop Users** rather than granting full Local Administrators:
   ```powershell
   Add-LocalGroupMember -Group "Remote Desktop Users" -Member "DOMAIN\jsmith"
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `TermService` is stopped or Windows Firewall blocks `Remote Desktop (TCP-In)` on the Domain/Private profile (never expose `TCP 3389` directly to the public internet!):
   ```powershell
   Start-Service -Name TermService
   Enable-NetFirewallRule -DisplayGroup "Remote Desktop"
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **CredSSP** mismatch: install pending Windows Cumulative Updates on the unpatched host (`[win-001]`). Only use a temporary `Mitigated` policy setting during emergency patching maintenance, then revert immediately to `Force Updated Clients`.
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If all 2 admin sessions on `SRV-FILE-01` are hung in `Disc` state, log off a confirmed idle disconnected session (`logoff <SessionID>` from `qwinsta`).

## Verification & Post-Fix Checks
1. Connect via `mstsc.exe` from `PC-LAB-01` to `SRV-FILE-01` as `jsmith@example.com` and verify NLA authentication completes and desktop loads cleanly.
2. Confirm `Get-Service TermService` is `Running` and `TCP 3389` remains restricted to internal/VPN firewall profiles.

## Cross-Subject Escalation & Pivot Links
- **Client or server missing CredSSP Encryption Oracle Remediation KB patch:** [win-001 — Windows Update Failure and Component Store Corruption](../03_Windows_Endpoints/win-001-windows-update-corruption.md)
- **Port 3389 unreachable due to split-tunnel VPN DNS, routing, or Windows Firewall:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Valid RDP password fails NLA because AD account is locked out (4740):** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)
- **Target RDP server is an Azure VM requiring NSG review, Bastion, or Serial Console:** [srv-013 — Azure VM Boot Failures, RDP/SSH Unreachable, NSG & Serial Console Triage](./srv-013-azure-vm-boot-rdp-ssh-and-serial-console.md)

## Client Update Snippets (EN / FR)
- **EN:** We verified the Remote Desktop service, firewall rules, and NLA authentication configuration on `SRV-FILE-01` and restored RDP access. Please try connecting via Remote Desktop once more and let us know if you reach the desktop cleanly.
- **FR:** Nous avons vérifié le service Bureau à distance, les règles de pare-feu et l'authentification NLA sur `SRV-FILE-01`, et rétabli l'accès RDP. Pouvez-vous tester de nouveau la connexion Bureau à distance et nous confirmer que tout fonctionne ?
