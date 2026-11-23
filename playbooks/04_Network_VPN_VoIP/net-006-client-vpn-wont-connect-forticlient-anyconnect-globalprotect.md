---
id: net-006
domain: 04_Network_VPN_VoIP
subject: "Network, VPN & VoIP"
subcategory: smb_vpn_tunnels
title: Remote Client VPN Cannot Connect (FortiClient, GlobalProtect, AnyConnect, Windows VPN)
tier: L1
keywords_en:
  - vpn can't connect
  - vpn won't connect
  - vpn cannot connect
  - vpn not connecting
  - forticlient stuck connecting
  - globalprotect connection failed
  - anyconnect failed
  - windows vpn error 809
  - ssl vpn error 98
keywords_fr:
  - vpn ne se connecte pas
  - connexion vpn echouee
  - vpn bloque
  - client vpn ne fonctionne pas
  - forticlient bloque
  - erreur vpn 809
error_codes:
  - "809"
  - "789"
  - "691"
  - VPN_AUTH_FAILED
  - SSL_VPN_98
tags:
  - client_vpn_connect
  - vpn_auth_mfa
  - vpn_client_error
os:
  - windows
  - macos
environment:
  - network
  - hybrid_ad
  - entra_id
  - local_endpoint
tools:
  - FortiClient / GlobalProtect / AnyConnect / Windows VPN
  - PowerShell
  - Test-NetConnection
  - Event Viewer
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - net-001
  - net-005
  - id-001
  - id-003
  - id-007
linked_scripts:
  - 02_Network/Get-NetworkSnapshot.ps1
  - 02_Network/Test-PortConnectivity.ps1
  - 02_Network/Reset-NetworkStack.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is this affecting **only you** working remotely (`PC-LAB-01`), or is an **entire branch office** unable to reach HQ (if whole office -> `[net-005]`)?
2. Which VPN client are you using (**FortiClient**, **GlobalProtect**, **Cisco AnyConnect**, **SonicWall NetExtender**, or **Windows Built-in VPN**), and what exact percentage or error message does it stop at?
3. Does normal internet browsing (`https://www.microsoft.com`) work **before** turning on the VPN, or are you on a **hotel / airport / guest Wi-Fi** (captive portal)?
4. Did you recently **change your Windows/M365 password** or get a **new phone for MFA**, and did an MFA push prompt appear when clicking Connect?

### Initial Scope & Classification
- Almost all L1 remote client VPN failures fall into four quick checks — **no IPsec/IKE router CLI required**: (1) local internet / captive Wi-Fi portal, (2) wrong password / locked AD account / missed MFA prompt, (3) home ISP/hotel Wi-Fi blocking VPN ports (`UDP 500/4500`), or (4) hung local VPN tray client / virtual NIC.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
> Start with these simple checks first — most single-user VPN tickets are solved in under 5 minutes without touching firewall config!

1. **Test normal internet FIRST (with VPN disconnected):** Open a browser and visit a public HTTPS site (`https://example.com`). If hotel/airport Wi-Fi redirects to a terms page, accept the captive portal before connecting VPN.
2. **Isolate home router / ISP blocking via Mobile Hotspot test (fast 60-second test!):** Connect `PC-LAB-01` temporarily to the user's **phone Wi-Fi hotspot** and try clicking Connect in the VPN client. If it connects immediately on hotspot -> the home/hotel router is blocking VPN ports (`Error 809`) or has a `192.168.1.x` subnet conflict!
3. **Check Password, AD Lockout (`id-001`), and MFA Prompt (`id-003`):**
   - Did the VPN get stuck at ~`40%` or `98%` waiting for **Microsoft Authenticator** / Duo / FortiToken approval? Have the user check their phone lock screen!
   - Verify the user's AD/Entra account is not locked out (`[id-001]`) or recently expired.
4. **Verify VPN Portal / Profile Name & Disconnect Dual Sessions:** Confirm the user picked the right Gateway/Connection profile and isn't already connected through an old session or consumer VPN (Nord/ExpressVPN/iCloud Private Relay).

### L2 Technical Diagnostics
1. **Check DNS, Local Gateway, and VPN Gateway Port Reachability (`PC-LAB-01`, read-only):**
   ```powershell
   # Verify internet DNS & test SSL VPN portal reachability (replace vpn.contoso.com with client portal)
   Resolve-DnsName -Name "vpn.contoso.com" -ErrorAction SilentlyContinue
   Test-NetConnection -ComputerName "vpn.contoso.com" -Port 443 | Select-Object ComputerName, RemoteAddress, TcpTestSucceeded

   # Inspect Windows built-in VPN profiles & virtual VPN adapters
   Get-VpnConnection -AllUserConnection -ErrorAction SilentlyContinue | Select-Object Name, ServerAddress, TunnelType, ConnectionStatus
   Get-NetAdapter | Where-Object { $_.InterfaceDescription -match "Fortinet|PANGP|AnyConnect|TAP|WAN Miniport" } |
       Select-Object Name, InterfaceDescription, Status
   ```
2. **Check Recent VPN Client Events (`RasClient` / Vendor Logs, read-only):**
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'Application'; ProviderName = 'RasClient'; StartTime = (Get-Date).AddDays(-2) } -MaxEvents 10 -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, Message
   ```
   - **`Error 691` / `VPN_AUTH_FAILED`:** Wrong username/password, expired password, locked AD account, missed MFA push, or missing AD VPN security group (`Domain Users` vs `SG-VPN-Users`).
   - **`Error 809` / `789` (L2TP/IPsec):** Home router NAT-T/SIP firewall blocking `UDP 500 / 4500`, or client missing required IPsec L2TP registry setting / device certificate.
   - **`SSL_VPN_98` (FortiClient ~98% hang):** Corrupted virtual PPP/FortiSSL adapter, SAML embedded browser cache hung, or Windows TLS/certificate trust prompt (`sec-003`).

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm whether the Mobile Hotspot test worked or failed, exact VPN client name/version, exact error code (`809` / `691` / `%` hang), timestamp, and `jsmith@example.com` public IP (`ifconfig.me` / `WhatIsMyIP` check).

## Deep-Dive Investigation (L3)
1. **SAML / Entra ID Conditional Access Block on VPN App:** Check **Entra Sign-in Logs** for the VPN Enterprise Application (`FortiGate SSL VPN` / `GlobalProtect` / `Cisco AnyConnect`) — look for **Device Compliance required** (`mdm-001`) or **Geo-Block outside Canada** (`id-007`)!
2. **Windows `WAN Miniport` or Third-Party Virtual NIC Failure:** Inspect Device Manager -> Network adapters for disabled `Fortinet Virtual Ethernet Adapter`, `PANGP Virtual Ethernet Adapter`, or `WAN Miniport (IKEv2 / L2TP / IP)`.
3. **Gateway Quota / IP Pool Exhaustion:** If ALL remote users suddenly cannot connect at morning peak (`08:30–09:00`), check the firewall's SSL VPN client IP lease pool exhaustion or certificate expiry (`sec-003`).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Ask the user to confirm before disconnecting active network adapters or rebooting `PC-LAB-01`.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Quick Fix)** Completely quit and relaunch the VPN client from the system tray (right-click -> **Shutdown / Quit**, NOT just closing the window!), verify MFA push on phone, or reboot `PC-LAB-01` once cleanly.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Service & Network Cache Reset)** Restart the vendor VPN Windows service (if frozen) and flush local DNS/Winsock on `PC-LAB-01` (DNS flush is instant; Winsock reset requires reboot):
   ```powershell
   # Restart ONLY the installed VPN client service (check exact service name first)
   Get-Service -Name "*Forti*", "*PanGPS*", "*vpnagent*", "RasMan" -ErrorAction SilentlyContinue | Restart-Service -Force
   ipconfig /flushdns
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Virtual Adapter / Error 809 Fix)** If **FortiClient / GlobalProtect** virtual adapter is wedged, run the vendor app **Repair** in **Settings -> Installed Apps** (with local admin). For Windows built-in L2TP behind home NAT (`Error 809`) where policy allows, verify `AssumeUDPEncapsulationContextOnSendRule` (`DWORD = 2`) under `HKLM\SYSTEM\CurrentControlSet\Services\PolicyAgent` with L2/L3 approval + reboot.

## Verification & Post-Fix Checks
1. Confirm the VPN client shows **`Connected`** and stays stable for > 2 minutes.
2. Verify internal host/share reachability (`[net-001]`) works (`Resolve-DnsName DC01.domain.local` and mapped drive `net use`).

## Cross-Subject Escalation & Pivot Links
- **VPN connects cleanly yet internal sites, DNS, or mapped drives fail:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](./net-001-dns-apipa-vpn-triage.md)
- **An ENTIRE branch office (many users) cannot reach HQ servers or Azure:** [net-005 — Site-to-Site IPsec VPN Tunnel Down (IKE Phase 1/2 Mismatch & DPD Timeouts)](./net-005-site-to-site-ipsec-vpn-tunnel-down.md)
- **VPN fails with auth error 691 because AD password locked out:** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)
- **VPN stalls waiting for MFA approval after phone replacement:** [id-003 — Entra ID MFA New Phone, Lost Authenticator, and Temporary Access Pass Recovery](../01_Identity_AD_Entra/id-003-entra-mfa-new-phone-and-tap-recovery.md)
- **User is traveling outside Canada and SAML VPN fails Conditional Access:** [id-007 — Geo-Blocking Outside Canada, Conditional Access Named Locations & Travel Access](../01_Identity_AD_Entra/id-007-geo-blocking-outside-canada-travel-access.md)

## Client Update Snippets (EN / FR)
- **EN:** We isolated the remote VPN connection block on `PC-LAB-01` (client service / credentials & MFA prompt / local network path) and verified a stable VPN connection to corporate resources. Could you test your internal drive or application and confirm everything works?
- **FR:** Nous avons identifié la cause du blocage de connexion VPN sur `PC-LAB-01` (service client / authentification MFA / réseau local) et validé une connexion VPN stable. Pouvez-vous tester vos ressources internes et confirmer que tout fonctionne ?
