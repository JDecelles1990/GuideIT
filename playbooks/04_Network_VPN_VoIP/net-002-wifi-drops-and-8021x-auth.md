---
id: net-002
domain: 04_Network_VPN_VoIP
subject: "Network, VPN & VoIP"
subcategory: dns_dhcp_wifi_voip
title: Wi-Fi Random Disconnects, Connected Without Internet, and 802.1X Auth Triage
tier: L1
keywords_en:
  - wifi keeps disconnecting
  - connected no internet
  - wifi won't connect
  - wifi drops randomly
  - 802.1x wifi failure
keywords_fr:
  - wifi se deconnecte
  - connecte sans internet
  - probleme wifi
  - coupures wifi frequentes
  - wifi impossible de se connecter
error_codes:
  - "8002"
  - "11004"
tags:
  - wifi_disconnect
  - wifi_8021x_auth
os:
  - windows
  - macos
environment:
  - network
  - local_endpoint
tools:
  - PowerShell
  - netsh
  - Event Viewer
  - Terminal
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - net-001
  - sec-003
  - mdm-001
---

## Fast Triage (Under 2 Minutes)
- Does the Wi-Fi drop occur for one endpoint (`PC-LAB-01`) or all colleagues connected to the same office SSID / access point?
- Does it happen specifically when `PC-LAB-01` wakes from sleep, switches between `2.4 GHz` / `5 GHz` / `6 GHz`, or docks via Ethernet?
- Is the SSID using **WPA2/WPA3-PSK** (pre-shared key) or **WPA2/WPA3-Enterprise (802.1X RADIUS)**?

## Read-Only Diagnostics (L1-L2)
1. **On Windows**, inspect live Wi-Fi signal strength, radio band, channel, and adapter link details (read-only):
   ```cmd
   netsh wlan show interfaces
   ```
   ```powershell
   Get-NetAdapter -Name "Wi-Fi*" | Select-Object Name, InterfaceDescription, Status, LinkSpeed, DriverVersion
   ```
2. **Generate and inspect Windows WLAN Diagnostic Report & `WLAN-AutoConfig` logs (read-only):**
   ```powershell
   Get-WinEvent -LogName "Microsoft-Windows-WLAN-AutoConfig/Operational" -MaxEvents 15 |
       Select-Object TimeCreated, Id, LevelDisplayName, Message
   ```
   *(To generate the full HTML timeline report for deep analysis: `netsh wlan show wlanreport` as admin -> `C:\ProgramData\Microsoft\Windows\WlanReport\wlan-report-latest.html`.)*
3. **On macOS**, inspect current Wi-Fi RSSI, noise, BSSID, and MCS index: Option-click the Wi-Fi menu bar icon or run `wdutil info` (sudo) / `system_profiler SPAirPortDataType`.

## Deep-Dive Investigation (L3)
1. **802.1X / RADIUS Certificate Auth Failures (`Event ID 11004` / `8002`):** Check `certlm.msc` (Computer Certificates -> Personal) and `certmgr.msc` to ensure the Wi-Fi machine/user SCEP/PKCS certificate pushed by ADCS or Intune is not expired or missing its trusted root CA.
2. **Aggressive Roaming / Power Saving / Band Steering:** Review adapter advanced properties (`Roaming Aggressiveness`, `Preferred Band`, `U-APSD`, and `Allow the computer to turn off this device to save power`) and correlate disconnect timestamps with AP logs on the wireless controller (UniFi / Meraki / Aruba).
3. **IP/DNS Failure vs. Layer 2 Radio Drop:** If `netsh wlan show interfaces` stays `Connected` with strong Signal (>70%) while `"Connected, no internet"` shows, follow `[net-001]` for DHCP/DNS/Captive Portal triage.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Forget and re-join the problematic SSID cleanly so stale PSK/EAP credentials or corrupted WLAN profiles are rebuilt:
   ```cmd
   netsh wlan delete profile name="<SSID_NAME>"
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Disable aggressive USB/PCIe Wi-Fi power saving (requires admin) in **Device Manager -> Network adapters -> `<Wi-Fi Adapter>` -> Power Management -> uncheck "Allow the computer to turn off this device to save power"**, and update to the latest OEM-verified Wi-Fi driver (`Intel` / `Qualcomm` / `MediaTek`).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **802.1X** machine/user certificate expired, trigger an Intune sync (`[mdm-001]`) or Group Policy / `certutil -pulse` refresh on corporate LAN/VPN to renew the SCEP/ADCS certificate.

## Verification & Post-Fix Checks
1. Confirm `netsh wlan show interfaces` reports `State : connected` on `5 GHz` / `6 GHz` with healthy signal (`> 70%`) and stable throughput.
2. Verify sustained connectivity across sleep/wake and continuous `ping -n 30 1.1.1.1` with `0%` packet loss.

## Cross-Subject Escalation & Pivot Links
- **Wi-Fi associates cleanly yet shows No Internet due to DHCP/DNS or captive portal:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](./net-001-dns-apipa-vpn-triage.md)
- **802.1X EAP-TLS rejects client due to expired NPS RADIUS or SCEP device certificate:** [sec-003 — TLS/SSL Certificate Expired, Missing Intermediate Chain, and Untrusted Root CA](../06_Security_Access/sec-003-tls-ssl-certificate-expired-and-untrusted-ca.md)
- **Intune Wi-Fi/SCEP profile missing or device Non-Compliant blocks wireless access:** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](../07_macOS_Mobile_MDM/mdm-001-intune-compliance-sync.md)

## Client Update Snippets (EN / FR)
- **EN:** We refreshed the wireless profile, adjusted adapter power/roaming settings, and verified stable Wi-Fi connectivity on `PC-LAB-01`. Please monitor the connection over the next hour and let us know if any drops return.
- **FR:** Nous avons réinitialisé le profil Wi-Fi, ajusté les paramètres d'alimentation de la carte sans fil et vérifié la stabilité de la connexion sur `PC-LAB-01`. Veuillez surveiller la connexion aujourd'hui et nous aviser si les coupures reviennent.
