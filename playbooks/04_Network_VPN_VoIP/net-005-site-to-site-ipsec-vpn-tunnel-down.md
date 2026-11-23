---
id: net-005
domain: 04_Network_VPN_VoIP
subject: Network, VPN & VoIP
subcategory: smb_vpn_tunnels
title: Site-to-Site IPsec VPN Tunnel Down (IKE Phase 1/2 Mismatch & DPD Timeouts)
tier: L3
keywords_en:
  - site to site vpn down
  - ipsec tunnel phase 1 mismatch
  - ike phase 2 no proposal chosen
  - azure vpn gateway disconnected
  - branch tunnel flapping
  - dpd timeout ipsec
keywords_fr:
  - tunnel vpn site a site tombe
  - erreur phase 1 ipsec ike
  - tunnel vpn passerelle deconnecte
  - perte paquets mtu tunnel ipsec
  - negociation ike echouee
error_codes:
  - NO_PROPOSAL_CHOSEN
  - IKE_PHASE1_FAIL
  - DPD_TIMEOUT
tags:
  - ipsec_vpn_tunnel
  - ike_phase_mismatch
os:
  - cross_platform
environment:
  - network
  - datacenter
  - azure
  - cloud_infra
tools:
  - Firewall / VPN Gateway Logs (FortiGate / SonicWall / Meraki)
  - Azure CLI (az)
  - PowerShell (Test-NetConnection)
  - strongSwan / ipsec CLI
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - srv-013
  - srv-010
---

## Fast Triage (Under 2 Minutes)
- **Confirm scope:** Is the entire site-to-site tunnel down (Phase 1 / IKE SA dead), or are only SOME branch subnets unreachable while others pass traffic (Phase 2 Proxy ID / Traffic Selector / Routing issue)?
- **Check ISP & peer WAN changes:** Verify both WAN interfaces (`198.51.100.10` HQ <-> `203.0.113.20` Branch/Azure) have stable internet connectivity and neither ISP changed a dynamic WAN IP or placed the modem in double-NAT without port forwarding UDP `500`/`4500`.
- **Check recent config or firmware changes:** Ask whether firmware updates, Pre-Shared Key (PSK) rotation, new VLANs/subnets, or Azure VPN Gateway SKU changes occurred prior to the drop.
- **Check Azure Service Health / Gateway Status:** If terminating on an Azure Virtual Network Gateway, verify whether Gateway maintenance or BGP peer flap is active.

## Read-Only Diagnostics (L1-L2)
Collect peer reachability, packet loss, and current tunnel SA state cleanly from an endpoint or gateway management shell without resetting active tunnels first:

```powershell
# From an inside host/jumpbox, verify local subnet to remote subnet reachability and path MTU
Test-NetConnection -ComputerName 10.20.0.10 -Port 445 -InformationLevel Detailed
ping -f -l 1350 10.20.0.10
```

On Azure VPN Gateway (read-only status & BGP peer inspection):

```bash
# Inspect Site-to-Site connection state and ingress/egress byte counters
az network vpn-connection show --resource-group <rg-name> --name <connection-name> --query "{status:connectionStatus,egress:egressBytesTransferred,ingress:ingressBytesTransferred,protocol:connectionProtocol}"

# Inspect BGP peers if route-based BGP is enabled
az network vnet-gateway list-bgp-peer-status --resource-group <rg-name> --name <gateway-name> --output table
```

On Linux VPN appliances (`strongSwan` / `libreswan` firewalls):

```bash
# Read-only Phase 1 (IKE SA) and Phase 2 (CHILD SA) status
ipsec statusall
swanctl --list-sas
journalctl -u strongswan -n 100 --no-pager
```

## Deep-Dive Investigation (L3)
Correlate firewall IKE/IPsec debug logs across **both** tunnel endpoints by phase:

1. **Phase 1 Failure (`IKE_PHASE1_FAIL` / `NO_PROPOSAL_CHOSEN` on IKE_SA_INIT):**
   - Mismatched **IKE version** (IKEv1 vs IKEv2) or Mode (Main vs Aggressive).
   - Mismatched **Encryption / Integrity / PRF / DH Group** (e.g., AES-256-GCM vs AES-256-CBC, SHA-256 vs SHA-1, DH Group 14 vs Group 2/19/20) or IKE SA lifetime mismatch.
   - Wrong **Pre-Shared Key (PSK)** or **Local/Remote IKE ID** (especially when one firewall sits behind NAT and sends private RFC 1918 WAN IP as its IKE identity instead of its public WAN IP).
   - Upstream ISP firewall dropping **UDP 500**, **UDP 4500 (NAT-T)**, or IP Protocol **50 (ESP)**.
2. **Phase 2 Failure (`NO_PROPOSAL_CHOSEN` on CREATE_CHILD_SA / Quick Mode):**
   - Mismatched **PFS (Perfect Forward Secrecy)** DH group (enabled on one side, disabled on the other) or Phase 2 crypto proposal / lifetime.
   - **Policy-Based vs Route-Based Traffic Selector mismatch:** Policy-based firewalls negotiate exact local/remote CIDR pairs (`10.10.0.0/16` <-> `10.20.0.0/16`), whereas Route-Based Azure VPN / VTI requires `0.0.0.0/0` <-> `0.0.0.0/0` unless policy-based traffic selectors are explicitly enabled (`usePolicyBasedTrafficSelectors`).
3. **Tunnel Connects Then Flaps (`DPD_TIMEOUT`) or Passes Ping Only (`MTU/MSS`):**
   - `DPD_TIMEOUT` indicates ISP packet loss, asymmetric routing, or one side blocking Keepalive/DPD probes.
   - If `ping` works yet SMB/RDP/HTTPS stalls, TCP packets exceed the IPsec encapsulation overhead (~1400 bytes) — verify **TCP MSS clamping (`1350`–`1360`)** and confirm ICMP Fragmentation Needed isn't blocked.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Clearing or modifying an IPsec tunnel drops ALL traffic across the site link (and may impact VoIP phones, file shares, and AD replication). Coordinate changes across both firewall administrators during an approved window, and export firewall configurations before modifying Phase 1/2 proposals or routing.

1. **Align Phase 1 & Phase 2 Proposals Cleanly (No Legacy Weak Crypto):**
   - Scope: Match IKEv2, AES-256 (or AES-GCM), SHA-256, DH Group 14+ (or ECP-256 / Group 19), and identical PFS/Lifetime settings on **both** peers (avoid downgrading to insecure 3DES/MD5/DH2 unless temporarily mandated by legacy hardware with documented risk acceptance).
2. **Fix NAT-T / IKE Peer ID & Traffic Selectors:**
   - Ensure Peer WAN behind NAT sets Local IKE ID explicitly to its public IP or FQDN and passes **UDP 500** + **UDP 4500** unblocked.
   - Align Phase 2 CIDR selectors cleanly (or configure Route-Based VTI + BGP / static routes matching both sides).
3. **Apply TCP MSS Clamping (`1350`–`1360`) for Stalled Apps:**
   - Clamp TCP MSS to `1350`–`1360` on the tunnel interface on firewalls where SMB/RDP hangs over the VPN despite ICMP ping succeeding.
4. **Controlled Tunnel Bounce (Only After Matching Config):**
   - Flush and re-initiate the single affected Phase 2 SA / IPsec connection rather than rebooting the entire firewall.

## Verification & Post-Fix Checks
- Verify Phase 1 IKE SA and Phase 2 Child SA show `ESTABLISHED` / `UP` on **both** gateways with bi-directional `ingressBytesTransferred` and `egressBytesTransferred` counters incrementing (never zero bytes in one direction!).
- Confirm TCP application connectivity (`Test-NetConnection -Port 445 / 389 / 443`) and large payload file transfer succeed without stalls across subnets.
- Monitor tunnel stability over 30–60 minutes (or through one full Phase 2 rekey interval, typically 3600s) to verify `DPD_TIMEOUT` does not reoccur.

## Cross-Subject Escalation & Pivot Links
- **IPsec tunnel is up yet remote subnets stall on internal DNS resolution or TCP MSS/MTU:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](./net-001-dns-apipa-vpn-triage.md)
- **Remote endpoint sits in an Azure VNet with an unreachable VM or NSG block:** [srv-013 — Azure VM Boot Failures, RDP/SSH Unreachable, NSG & Serial Console Triage](../08_Servers_Cloud_Infra/srv-013-azure-vm-boot-rdp-ssh-and-serial-console.md)
- **WAN fiber link flap traces to degraded SFP+ optical transceiver RX power:** [srv-010 — Data Center Rack Power (A/B PSU), Thermal Trips, and SFP+/Fiber Optical Diagnostics](../08_Servers_Cloud_Infra/srv-010-datacenter-rack-power-thermal-and-sfp-optics.md)

## Useful Links & External Tools
- [Microsoft Azure Portal](https://portal.azure.com/) — Inspect Azure Virtual Network Gateway connection health, Connection Troubleshoot, and IPsec diagnostic logs.
- [Visual Subnet Calculator](https://www.davidc.net/sites/default/subnets/subnets.html) — Verify non-overlapping CIDR blocks for Phase 2 Proxy IDs and VNet address spaces.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we investigated the site-to-site IPsec VPN outage between `<Site-A>` and `<Site-B>`. A mismatch / interruption in `<IKE Phase 1/Phase 2 proposals / Peer WAN / Routing / MSS>` prevented traffic from passing cleanly. After aligning both gateways, the tunnel is up with bi-directional traffic verified. Please confirm branch access is restored.
- **FR:** Bonjour `<user>`, nous avons diagnostiqué la panne du tunnel VPN IPsec site-à-site entre `<Site-A>` et `<Site-B>`. Un décalage ou une coupure (`<Phase 1/Phase 2 / IP WAN / routage / MTU-MSS>`) bloquait les paquets. Après alignement des deux passerelles, le tunnel est rétabli et bidirectionnel. Merci de confirmer l'accès depuis la succursale.
