---
id: srv-010
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: datacenter_hardware_boot
title: Data Center Rack Power (A/B PSU), Thermal Trips, and SFP+/Fiber Optical Diagnostics
tier: L2
keywords_en:
  - sfp optical rx power
  - fiber link down datacenter
  - server psu failed thermal trip
  - rack power redundancy lost
  - ethtool sfp dom dbm
keywords_fr:
  - puissance optique sfp faible
  - lien fibre optique coupe datacenter
  - panne alimentation thermique baie
  - perte redondance alimentation serveur
  - diagnostic fibre sfp ethtool
error_codes:
  - PSU_FAIL
  - THERMAL_TRIP
  - DOM_RX_LOW
tags:
  - datacenter_power_thermal
  - datacenter_sfp_optical
os:
  - linux
  - cross_platform
environment:
  - datacenter
  - network
tools:
  - ipmitool
  - ethtool
  - lm-sensors
  - Optical Power Meter
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-009
  - srv-007
  - net-005
---

## Fast Triage (Under 2 Minutes)
- **Power / Thermal (`PSU_FAIL` / `THERMAL_TRIP`):** Confirm whether BOTH **A-side and B-side rack PDUs** are live (a common rack cabling mistake plugs BOTH server PSUs into the SAME A-side PDU strip!). Check front/rear PSU LEDs (solid green = OK; blinking/amber = PSU fault or missing AC feed).
- **Fiber / SFP+ Link Down (`DOM_RX_LOW`):** Check switch & NIC port LEDs (`off` vs `solid` vs `amber`), verify **SMF (Yellow, Single-Mode 1310nm LR)** vs **MMF (Aqua/Magenta, Multi-Mode 850nm SR)** cable-to-optic match — **never mix SMF and MMF optics/cables**!

## Read-Only Diagnostics (L1-L2)
1. **Inspect PSU Voltages, Wattage, Fan RPM, and Inlet/CPU Temperatures via IPMI (read-only):**
   ```bash
   sudo ipmitool sensor | grep -iE 'pwr|ps|volt|fan|temp'
   sensors 2>/dev/null || true
   ```
2. **Read SFP+/QSFP28 Transceiver DOM Optical Power (`ethtool -m`, read-only):**
   ```bash
   sudo ethtool -m <iface>
   ```
   *(Check `Laser output power` [Tx] and `Receiver signal average optical power` [Rx] in **`dBm`** against `Rx power low alarm/warning` thresholds! Typical healthy 10G-SR/LR Rx is roughly `-1 dBm` to `-10 dBm`; `-40 dBm` / `-inf` means dark fiber / no Tx from far end or broken/dirty patch cord!)*
3. **Check NIC Link & Transceiver Type (`ethtool <iface>`, read-only):**
   ```bash
   sudo ethtool <iface>
   ```

## Deep-Dive Investigation (L3)
1. **LC Fiber Polarity Reversal (Tx ↔ Rx):** If NIC sees `0` Rx light (`-40 dBm`) while switch sees Rx light OR both ends fail to link on new duplex LC patch runs, one end's Tx must mate to the far end's Rx — swap the duplex LC clip polarity (or test with a known-good loopback/power meter).
2. **Dirty Fiber Ferrules & Bend Radius (`DOM_RX_LOW` + CRC Errors):** Dust on an uncapped LC connector or tight zip-ties crushing fiber in vertical cable managers attenuates light just enough to cause `rx_crc_errors` (`ethtool -S`) and intermittent LACP flaps!
3. **Hot-Aisle / Cold-Aisle Airflow Short-Circuit (`THERMAL_TRIP`):** Missing **1U/2U blanking panels** above/below rack servers or servers accidentally mounted backward recirculate hot exhaust air back into front intakes, tripping `THERMAL_TRIP` on dense 1U nodes.
4. **SFP+ Vendor Coding Lock:** Certain switches/NICs reject third-party uncoded optics (`unsupported SFP+ module`) unless coded properly or `allow_unsupported_sfp` is enabled per vendor docs.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Restore A/B Power Redundancy (`PSU_FAIL`):** Verify PDU breaker/outlet telemetry first, confirm PSU 1 connects to **PDU-A** and PSU 2 connects to **PDU-B** on independent rack circuits, and hot-swap a failed redundant PSU one unit at a time (while verifying the surviving PSU carries load stably!).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Clean & Re-Patch Fiber Safely:**
   - **Eye Safety:** NEVER look directly into an active fiber ferrule or transceiver port!
   - Clean both fiber patch LC ends and transceiver sleeves using a calibrated **1.25mm LC one-click fiber cleaner**, inspect polarity (Tx→Rx), ensure gentle cable bend radius (use Velcro, never tight plastic zip-ties on fiber!), and replace suspect patch cords or mismatched SR/LR optics.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Correct Rack Thermal Flow:** Clear blocked perforated rack doors, replace failed hot-swap fan modules, and install missing **blanking panels** across open rack U-slots.

## Verification & Post-Fix Checks
1. Confirm `ethtool -m <iface>` shows Rx/Tx dBm comfortably inside normal thresholds (`> Rx low warning`) and `ethtool <iface>` reports `Link detected: yes` with zero rising CRC errors (`ethtool -S <iface>`).
2. Confirm `ipmitool sensor` reports both `PS1` and `PS2` OK, healthy fan RPMs, and CPU/inlet temps well below warning thresholds.

## Cross-Subject Escalation & Pivot Links
- **Chassis sensor, PSU voltage, fan RPM, and storage health inspection via IPMI/iDRAC/iLO:** [srv-009 — Data Center IPMI/iDRAC/iLO, RAID Degraded, SMART Disk, and ECC/MCE Hardware Triage](./srv-009-datacenter-ipmi-raid-smart-and-ecc-hardware.md)
- **SFP+ link flap or CRC errors degrade bonded Linux NIC throughput (ethtool):** [srv-007 — Linux Network Interfaces, LACP Bonding, DNS, and Firewall (nftables/ufw/firewalld)](./srv-007-linux-network-nic-bonding-and-firewall.md)
- **Physical WAN fiber degradation causes firewall IPsec tunnel DPD timeouts:** [net-005 — Site-to-Site IPsec VPN Tunnel Down (IKE Phase 1/2 Mismatch & DPD Timeouts)](../04_Network_VPN_VoIP/net-005-site-to-site-ipsec-vpn-tunnel-down.md)

## Client Update Snippets (EN / FR)
- **EN:** We completed physical Data Center diagnostics on the rack power / thermal / SFP+ fiber link (`ethtool -m` optical levels and IPMI telemetry), corrected the faulted feed / optic patch, and verified full redundancy and clean link stability.
- **FR:** Nous avons effectué les diagnostics physiques en centre de données sur l'alimentation / refroidissement / lien fibre SFP+ (niveaux optiques `ethtool -m` et télémétrie IPMI), corrigé l'élément défaillant et validé la redondance complète.
