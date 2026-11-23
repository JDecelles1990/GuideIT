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
linked_scripts:
  - 02_Network/Get-WiFiDiagnostics.ps1
  - 02_Network/Get-NetworkSnapshot.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is the Wi-Fi dropping for **only you (`PC-LAB-01`)**, or for **everyone nearby in the office**?
2. Which Wi-Fi network (`SSID`) are you connecting to (**Corporate Wi-Fi**, **Guest Wi-Fi**, or **Home Wi-Fi**), and did you recently **change your Windows/M365 password** (for 802.1X Enterprise Wi-Fi)?
3. Does it show **"Connected, no internet"**, **`Can't connect to this network`**, or randomly drop right after waking the laptop from sleep?
4. Look at the physical Wi-Fi icon in the taskbar: is **Airplane Mode** off, and are there 1–2 signal bars (weak distance / concrete wall)?

### Initial Scope & Classification
- Distinguish **Radio / Weak Signal / Sleep Power Saving drops** from **Wrong Password / Expired 802.1X Certificate** (`Can't connect`) and **IP / DHCP / Captive Portal block** (`Connected, no internet` -> `[net-001]`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Basic Connectivity & Airplane Mode / Captive Portal Check:** Verify Airplane Mode is Off, toggle Wi-Fi Off -> Wait 5s -> On, move closer to an Access Point if signal <= 1 bar, or plug in Ethernet temporarily if urgent. If on Hotel/Guest Wi-Fi showing `Connected, no internet`, open browser to `http://neverssl.com` to force the captive login portal!
2. **Test Alternate Network (Mobile Hotspot Check):** Connect briefly to a phone Wi-Fi hotspot — if `PC-LAB-01` stays rock-solid on hotspot while dropping on office Wi-Fi, the laptop Wi-Fi card is fine and the issue is office AP/802.1X/DHCP!
3. **Look Visually at Wi-Fi Properties (`Settings -> Network & internet -> Wi-Fi -> Hardware properties`):** Note the **Protocol (`Wi-Fi 5/6`)**, **Network band (`2.4 GHz` vs `5 GHz`)**, and **IPv4 address** (`169.254.x.x` = DHCP fail -> `[net-001]`).

### L2 Technical Diagnostics
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


## Useful Links & External Tools
- **[Downdetector](https://downdetector.com/)** — Rule out regional ISP/carrier outages when Wi-Fi connects without internet.
- **[DNS Checker (Global Propagation)](https://dnschecker.org/)** — Verify external DNS resolution if internal vs public DNS behaves inconsistently.
## Client Update Snippets (EN / FR)
- **EN:** We refreshed the wireless profile, adjusted adapter power/roaming settings, and verified stable Wi-Fi connectivity on `PC-LAB-01`. Please monitor the connection over the next hour and let us know if any drops return.
- **FR:** Nous avons réinitialisé le profil Wi-Fi, ajusté les paramètres d'alimentation de la carte sans fil et vérifié la stabilité de la connexion sur `PC-LAB-01`. Veuillez surveiller la connexion aujourd'hui et nous aviser si les coupures reviennent.
