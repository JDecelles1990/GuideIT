---
id: prt-004
domain: 05_Printers_Devices
subject: "Printers & Peripherals"
subcategory: printers_spooler_scan
title: Printer Scan-to-Email SMTP Relay Failure (535 5.7.139 / 550 5.7.64)
tier: L2
keywords_en:
  - scan to email failed
  - printer cannot send email
  - smtp relay error m365
  - scanner smtp auth failed
  - mfp scan to email blocked
keywords_fr:
  - numerisation vers courriel echouee
  - scan vers email ne fonctionne pas
  - erreur smtp imprimante
  - scanner n'envoie plus de courriels
  - relais smtp bloque
error_codes:
  - "535 5.7.139"
  - "550 5.7.64"
  - "530 5.7.57"
tags:
  - scan_to_email
  - smtp_relay_auth
os:
  - cross_platform
environment:
  - m365
  - network
  - on_prem_ad
tools:
  - Exchange Admin Center
  - Printer Web UI
  - PowerShell
  - Test-NetConnection
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - m365-006
  - sec-003
  - id-003
linked_scripts:
  - 03_M365/Get-MailDNSRecords.ps1
  - 02_Network/Test-PortConnectivity.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Can users still **print** normally to this multifunction printer (`10.0.10.50`), and does **Scan-to-Email fail for ALL recipients** or ONLY **external recipients** (key clue pointing to Option 2 Direct Send restriction!)?
2. Does the printer touch-screen or printed error sheet show an exact message (`Authentication failed / 535 5.7.139`, `Connection timeout`, `Relay denied / 550 5.7.64`)?
3. Did anything change recently (**M365 password reset**, **MFA / Security Defaults enabled**, **printer swapped**, or **office ISP / static public IP changed**)?
4. Is Scan-to-Folder (`SMB`) still working or needed as a temporary backup so users aren't blocked?

### Initial Scope & Classification
- Inspect the MFP printer's Web UI (`http://10.0.10.50`) scan job log for the exact SMTP code (`535 5.7.139` = Auth unsuccessful; `530 5.7.57` = STARTTLS required; `550 5.7.64` = Relay / IP connector mismatch) across M365 Options 1 (**SMTP AUTH**), 2 (**Direct Send**), or 3 (**Inbound Connector**).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Printer Web UI & Basic Network)
1. **Open Printer Web Admin Console (`http://10.0.10.50`) Read-Only:**
   - Log into the copier Web UI -> **Scan / Email / SMTP Settings** + **Job History / Log** -> screenshot the exact SMTP server name (`smtp.office365.com` vs `*.mail.protection.outlook.com`), port (`587` vs `25`), `From:` address (`scanner@contoso.com`), and latest failed scan error code!
   - Test sending a scan to an **internal `@contoso.com`** address vs an **external address** to classify Direct Send vs Auth failure immediately.
2. **Verify Dedicated Service Account / ISP Static IP Hasn't Changed:** Check Entra Sign-in Logs for `scanner@contoso.com` (did MFA/Security Defaults/password change block it?) and check the office public WAN IP (`https://ifconfig.me` from onsite) vs `contoso.com`'s SPF TXT record!

### L2 Technical Diagnostics
1. **Verify outbound SMTP port reachability from the printer's subnet (`10.0.10.x`, read-only):**
   ```powershell
   Test-NetConnection -ComputerName "smtp.office365.com" -Port 587 | Select-Object ComputerName, TcpTestSucceeded
   Test-NetConnection -ComputerName "contoso-com.mail.protection.outlook.com" -Port 25 | Select-Object ComputerName, TcpTestSucceeded
   ```
   *(Note: Many ISPs block outbound `TCP 25`, breaking Direct Send unless an M365 connector or authenticated `TCP 587` is used!)*
2. **Check Exchange Online Tenant & Mailbox SMTP AUTH Settings (read-only):**
   ```powershell
   Connect-ExchangeOnline -ShowBanner:$false
   Get-TransportConfig | Select-Object SmtpClientAuthenticationDisabled
   Get-CASMailbox -Identity "scanner@contoso.com" | Select-Object SmtpClientAuthenticationDisabled
   ```
3. **Check Public SPF Record (`Resolve-DnsName contoso.com -Type TXT`):** If using Direct Send or a connector from WAN IP `198.51.100.10`, that static WAN IP MUST be listed in `contoso.com`'s SPF record (`ip4:198.51.100.10`).

## Deep-Dive Investigation (L3)
1. **TLS 1.0/1.1 Deprecation on Legacy Printers:** Exchange Online enforces **TLS 1.2**; older MFPs running outdated firmware fail with `TLS handshake failed` or `530 5.7.57` until printer firmware is updated or routed via a modern internal SMTP relay (e.g., Postfix / approved relay service).
2. **Security Defaults / Conditional Access Blocking `scanner@contoso.com` (`535 5.7.139`):** Microsoft Security Defaults disables **SMTP AUTH** tenant-wide! In Conditional Access tenants, ensure an exclusion ONLY for `scanner@contoso.com` if legacy SMTP AUTH is strictly required (scoped to the office static WAN IP `198.51.100.10`), OR migrate to **Exchange Inbound Connector** (Option 3) / **Azure Communication Services / High Volume Email** so `scanner@contoso.com` needs no legacy auth password.
3. **DNS on Printer (`10.0.10.50`):** Confirm the printer's static IP settings include reachable DNS servers and an accurate NTP clock.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If using scoped **SMTP AUTH** on a Conditional Access tenant (never enable tenant-wide needlessly): enable SMTP AUTH solely on the dedicated service mailbox `scanner@contoso.com`:
   ```powershell
   Set-CASMailbox -Identity "scanner@contoso.com" -SmtpClientAuthenticationDisabled $false
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If switching to **M365 Direct Send** (no password required; internal `contoso.com` recipients only) or **Inbound Connector** (internal + external):
   - Add `ip4:198.51.100.10` to `contoso.com`'s public SPF TXT record.
   - Configure the printer SMTP server to `contoso-com.mail.protection.outlook.com`, port `25`, STARTTLS enabled, Authentication = Off, From = `scanner@contoso.com`.
   - For external recipients, configure an **Exchange Admin Center -> Mail flow -> Connectors -> Your organization's email server to Office 365** matching static WAN IP `198.51.100.10`.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Update printer firmware if TLS 1.2 is missing and ensure `From:` address matches `scanner@contoso.com`.

## Verification & Post-Fix Checks
1. Scan a 1-page test document to `jsmith@example.com` and verify the printer job log shows **`Sent / Completed`**.
2. Confirm `Get-MessageTrace` shows delivery and headers pass SPF (`spf=pass`).

## Cross-Subject Escalation & Pivot Links
- **MFP cannot resolve smtp.office365.com or internal relay IP due to DNS/VLAN firewall:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Scan-to-Email messages bounce with 550 5.7.1 / SPF alignment failure in Exchange Online:** [m365-006 — Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping](../02_M365_Email_Collab/m365-006-exchange-ndr-550-and-shared-mailbox-missing.md)
- **Legacy MFP firmware fails TLS 1.2+ certificate handshake on SMTP port 587:** [sec-003 — TLS/SSL Certificate Expired, Missing Intermediate Chain, and Untrusted Root CA](../06_Security_Access/sec-003-tls-ssl-certificate-expired-and-untrusted-ca.md)
- **Printer service mailbox fails SMTP AUTH (535 5.7.139) due to MFA/Security Defaults:** [id-003 — Entra ID MFA New Phone, Lost Authenticator, and Temporary Access Pass Recovery](../01_Identity_AD_Entra/id-003-entra-mfa-new-phone-and-tap-recovery.md)

## Useful Links & External Tools
- **[MXToolbox SuperTool](https://mxtoolbox.com/SuperTool.aspx)** — Verify `spf:contoso.com` includes `ip4:198.51.100.10` (within 10 DNS lookups) and check `mx:contoso.com` for Direct Send hostname.
- **[Microsoft Remote Connectivity Analyzer](https://testconnectivity.microsoft.com/)** — Test **Inbound SMTP Email** delivery and TLS negotiation to the tenant MX endpoint.

## Client Update Snippets (EN / FR)
- **EN:** We updated the printer's SMTP relay / Exchange authentication configuration on `PRT-FIN-01` and tested a live scan delivery. Could you try scanning a test page to your email and confirm you receive it?
- **FR:** Nous avons corrigé la configuration du relais SMTP / authentification Exchange sur l'imprimante `PRT-FIN-01` et validé l'envoi d'un test. Pouvez-vous numériser une page vers votre courriel et confirmer sa réception ?
