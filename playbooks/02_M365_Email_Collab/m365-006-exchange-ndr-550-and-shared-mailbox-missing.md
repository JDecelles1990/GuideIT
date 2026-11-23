---
id: m365-006
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: email_exchange_mailflow
title: Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping
tier: L2
keywords_en:
  - email bounced back
  - missing shared mailbox
  - mail stuck in quarantine
  - ndr 550 bounce
  - shared mailbox not showing in outlook
keywords_fr:
  - courriel retourne en erreur
  - boite partagee manquante
  - courriel en quarantaine
  - rejet 550 exchange
  - boite aux lettres partagee invisible
error_codes:
  - "550 5.7.1"
  - "550 5.4.1"
  - "550 5.7.511"
tags:
  - exchange_ndr_bounce
  - shared_mailbox_missing
os:
  - cross_platform
  - windows
environment:
  - m365
  - entra_id
tools:
  - Exchange Admin Center
  - Exchange Online PowerShell
  - Microsoft Defender Quarantine
risk_level: low
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - prt-004
  - m365-008
  - sec-001
  - id-008
---

## Fast Triage (Under 2 Minutes)
- **For Bounce / NDR:** Collect the exact Non-Delivery Report code (`550 5.4.1` recipient address rejected / Directory-Based Edge Blocking, `550 5.7.1` policy/transport rule/blocklist reject, `550 5.7.511` banned sender/high spam score) and whether it affects internal or external mail.
- **For Missing Shared Mailbox:** Does `jsmith@example.com` see the shared mailbox (`sales@example.org`) in **Outlook on the Web (`Open another mailbox`)**, or only miss it in desktop Outlook?
- Remember Exchange Online Automapping propagation can take up to 60 minutes after permission assignment.

## Read-Only Diagnostics (L1-L2)
1. **Inspect Exchange Online Message Trace & Defender Quarantine (read-only):**
   ```powershell
   Connect-ExchangeOnline -ShowBanner:$false
   Get-MessageTrace -SenderAddress "jsmith@example.com" -StartDate (Get-Date).AddDays(-2) -EndDate (Get-Date) |
       Select-Object Received, RecipientAddress, Subject, Status | Format-Table -AutoSize
   ```
   Also check **Microsoft Defender Portal -> Review -> Quarantine** (`security.microsoft.com`) for held inbound/outbound messages.
2. **Check Shared Mailbox Permissions & Automapping State (read-only):**
   ```powershell
   Get-MailboxPermission -Identity "sales@example.org" |
       Where-Object { $_.User -like "*jsmith*" } |
       Select-Object Identity, User, AccessRights, IsInherited
   Get-Mailbox -Identity "sales@example.org" | Select-Object DisplayName, PrimarySmtpAddress, HiddenFromAddressListsEnabled
   ```
3. **Check Tenant Outbound Spam / Blocked Users:** Look in **Defender Portal -> Restricted entities** (`550 5.1.8` / `550 5.7.511` often means the sender was auto-restricted due to outbound spam -> pivot to `[sec-001]`!).

## Deep-Dive Investigation (L3)
1. **`550 5.4.1` (Access Denied / DBEB):** Confirm the destination recipient exists in Exchange Online, no misspelled proxyAddress exists, and external MX records (`Resolve-DnsName contoso.com -Type MX`) point directly to `*.mail.protection.outlook.com` (or the approved gateway).
2. **`550 5.7.1` (Transport Rule / Connector / IP Reputation):** Check **Exchange Admin Center -> Mail flow -> Rules** (`Get-TransportRule`) and Microsoft 365 **Tenant Allow/Block Lists**; inspect NDR headers (`Remote Server returned`) to see whether the *remote* recipient server rejected the mail (SPF/DKIM/DMARC or PTR issue).
3. **Shared Mailbox Granted via Security Group (No Automapping!):** Exchange Online **only** populates `msExchDelegateListLink` (Outlook Automapping) when **Full Access** is granted directly to the user rather than through a nested Security Group, OR when Outlook cached OST exceeds size / **Download shared folders** limit.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** To restore **Outlook Automapping** for a shared mailbox where permissions were granted via a group or `AutoMapping:$false`, remove and re-add explicit `FullAccess` with `-AutoMapping $true` (wait 15–60 minutes, then restart Outlook):
   ```powershell
   Remove-MailboxPermission -Identity "sales@example.org" -User "jsmith@example.com" -AccessRights FullAccess -Confirm:$false
   Add-MailboxPermission -Identity "sales@example.org" -User "jsmith@example.com" -AccessRights FullAccess -AutoMapping $true
   ```
   *(Alternative fast workaround: add manually in Outlook via **File -> Account Settings -> More Settings -> Advanced -> Add**, or **Right-click primary mailbox -> Add shared folder** in New Outlook/OWA.)*
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If a legitimate message is in **Defender Quarantine**, release it (and review why anti-spam/DLP flagged it before adding any broad allow entry).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `550 5.7.511` or Restricted Users alert triggered due to compromised mailbox activity, unblock ONLY after completing full BEC remediation (`[sec-001]`).

## Verification & Post-Fix Checks
1. Send a test email to/from `jsmith@example.com` and verify `Get-MessageTrace` reports **`Delivered`**.
2. Restart Outlook on `PC-LAB-01` and confirm `sales@example.org` appears in the left folder pane and loads new mail.

## Cross-Subject Escalation & Pivot Links
- **MX, SPF, DKIM, or Autodiscover DNS records fail lookup or point to stale hosts:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Multifunction printer Scan-to-Email relay generates 550/535 NDRs due to SPF or SMTP AUTH block:** [prt-004 — Printer Scan-to-Email SMTP Relay Failure (535 5.7.139 / 550 5.7.64)](../05_Printers_Devices/prt-004-scan-to-email-smtp-relay-failure.md)
- **Inbound bounce is actually 554 5.2.2 mailbox quota exhaustion rather than SPF/policy:** [m365-008 — Exchange Online Mailbox Full (554 5.2.2) & Online Archive Not Moving Mail](./m365-008-exchange-mailbox-full-and-online-archive-stuck.md)
- **Outbound 550 5.7.708 spam block signals compromised mailbox sending phishing:** [sec-001 — Suspected Business Email Compromise and Session Token Theft](../06_Security_Access/sec-001-bec-token-compromise.md)
- **550 5.4.1 recipient missing stems from failed Entra Connect directory sync:** [id-008 — Microsoft Entra Connect Sync Errors, Duplicate Attributes & PHS Stalls](../01_Identity_AD_Entra/id-008-entra-connect-sync-errors-and-duplicate-attributes.md)

## Useful Links & External Tools
- **[MXToolbox SuperTool](https://mxtoolbox.com/SuperTool.aspx)** — Run `mx:`, `spf:`, `dmarc:`, and `blacklist:` checks on sending domains/IPs when diagnosing `550 5.7.1` bounces.
- **[Microsoft Remote Connectivity Analyzer](https://testconnectivity.microsoft.com/)** — Run **Office 365 -> Outlook Connectivity** or **Inbound/Outbound SMTP** diagnostics for Autodiscover and TLS mail flow.
- **[Microsoft 365 Service Health Status](https://status.cloud.microsoft/)** — Check global Exchange Online / Outlook service advisories alongside Tenant Admin Center.

## Client Update Snippets (EN / FR)
- **EN:** We traced the Exchange Online mail delivery error / shared mailbox permission issue and applied the fix. Could you test sending a message or restart Outlook in 15 minutes to confirm everything works?
- **FR:** Nous avons analysé l'erreur de livraison Exchange Online / les droits de la boîte partagée et appliqué le correctif nécessaire. Pouvez-vous faire un nouvel essai d'envoi ou redémarrer Outlook dans 15 minutes pour confirmer que tout est en ordre ?
