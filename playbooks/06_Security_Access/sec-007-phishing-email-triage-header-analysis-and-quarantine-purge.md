---
id: sec-007
domain: 06_Security_Access
subject: "Security & Access"
subcategory: phishing_ir_containment
title: Phishing Email Triage, Header Auth Analysis (SPF/DKIM/DMARC), and Quarantine Purge
tier: L2
keywords_en:
  - phishing email header analysis
  - release email from quarantine defender
  - purge phishing email all mailboxes
  - spoofed email failed spf dkim dmarc
  - check suspicious email link safe
keywords_fr:
  - analyse entete courriel hameconnage
  - liberer courriel en quarantaine defender
  - supprimer courriel hameconnage boites
  - courriel usurpe spf dkim dmarc echoue
  - verifier lien courriel suspect
error_codes:
  - SPF_SOFTFAIL
  - DMARC_FAIL
  - BCL_HIGH
  - ZAP_QUARANTINE
  - PHISHING_REPORTED
tags:
  - phishing_header_triage
  - quarantine_message_purge
  - email_spoofing_dmarc
os:
  - cross_platform
environment:
  - m365
  - google_workspace
  - saas
tools:
  - Microsoft Defender Portal
  - Microsoft Message Header Analyzer
  - Exchange Online PowerShell
  - URLScan.io
risk_level: high
requires_admin: true
last_verified: 2026-11-23
related_ids:
  - sec-001
  - sec-008
  - m365-006
  - id-003
linked_scripts:
  - 03_M365/Get-MailDNSRecords.ps1
  - 05_Security_Defender/Get-PersistenceAndConnectionsAudit.ps1
  - 05_Security_Defender/Get-DefenderStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Did `jsmith@example.com` **only receive** the suspicious message, OR did they **click any link, open/enable an attachment macro, scan a QR code, or enter their password/MFA code**? *(If clicked or credentials entered -> IMMEDIATELY pivot to P1 containment in `[sec-001]` / `[sec-008]`!)*
2. Is this a **false-positive legitimate invoice/vendor email stuck in Defender Quarantine** requesting release, OR a **confirmed phishing / executive spoofing campaign** hitting multiple users at `contoso.com`?
3. Ask the user to **forward the suspicious message as an `.eml` attachment** (or copy **View message details** headers) — NEVER ask them to forward normally or click links to "test" them!
4. How many users received the same **Subject / Sender IP / Internet Message-ID** across the organization?

### Initial Scope & Classification
- **User clicked & typed credentials or approved MFA:** Do NOT stop at deleting the email — execute session revocation & password reset (`[sec-001]`) and endpoint audit (`[sec-008]`) immediately!
- **Suspect phishing campaign delivered to inbox:** Triage sanitized SMTP headers in **[Microsoft Message Header Analyzer](https://mha.azurewebsites.net/)** or **[Google Admin Toolbox](https://toolbox.googleapps.com/apps/main/)**, detonate stripped URLs in Private/Unlisted mode on **[URLScan.io](https://urlscan.io/)**, check sender domain SPF/DKIM/DMARC via `03_M365/Get-MailDNSRecords.ps1`, and purge across all tenant mailboxes via **[Microsoft Defender Portal](https://security.microsoft.com/)** Explorer / Content Search.
- **Legitimate message blocked in Quarantine (`ZAP_QUARANTINE` / `BCL_HIGH`):** Verify **true sender alignment** (`SPF=pass` + `DKIM=pass` + `DMARC=pass`) and confirm callback/out-of-band voice verification for any wire/invoice/bank-detail changes before releasing!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Safe Inspection, Never Open Live Links!)
1. **Export Sanitized Email Headers & Detonate Links Safely:**
   - Have the user (or admin via Explorer preview) save headers via **Outlook on the Web -> `... -> View -> View message details`** (or Classic Outlook **`File -> Properties -> Internet headers`**).
   - Paste sanitized headers into **[Microsoft Message Header Analyzer](https://mha.azurewebsites.net/)** and inspect:
     - `Authentication-Results` (`spf=`, `dkim=`, `dmarc=`, `compauth=`)
     - `Return-Path` vs Display `From:` (Lookalike domain typosquatting like `c0ntoso.com` vs compromised partner tenant!)
     - `X-Forefront-Antispam-Report` (`SCL`, `BCL`, `SFV:SPM`/`PHSH`)
   - Copy suspicious URLs WITHOUT clicking them (strip `?email=` / tracking tokens first!) and run a **Private/Unlisted** scan in **[URLScan.io](https://urlscan.io/)**.
2. **Inspect Quarantined Messages & Threat Submissions in [Microsoft Defender Portal](https://security.microsoft.com/):**
   - Navigate to **Email & collaboration -> Review -> Quarantine** -> preview **Header + Plain-Text Body** + **Quarantine Reason** (`Phishing`, `High confidence phish`, `Bulk`, `Spoof`, `Malware`).

### L2 Technical Diagnostics
1. **Trace Scope Across Exchange Online & Audit Sender Domain Mail DNS (read-only):**
   ```powershell
   # Check sender domain SPF, DMARC & DKIM posture locally (PowerShellStore: 03_M365/Get-MailDNSRecords.ps1)
   Resolve-DnsName -Name "example.com" -Type TXT | Select-Object Strings
   Resolve-DnsName -Name "_dmarc.example.com" -Type TXT | Select-Object Strings

   # Connect to Exchange Online PowerShell (read-only trace of blast radius over last 48h)
   # Connect-ExchangeOnline
   Get-MessageTrace -SenderAddress "suspect@example.org" -StartDate (Get-Date).AddHours(-48) -EndDate (Get-Date) |
       Select-Object Received, SenderAddress, RecipientAddress, Subject, Status |
       Format-Table -AutoSize

   # Check Defender Quarantine queue read-only for the targeted recipient
   Get-QuarantineMessage -RecipientAddress "jsmith@example.com" -PageSize 50 |
       Select-Object ReceivedTime, SenderAddress, Subject, Type, QuarantineTypes, ReleaseStatus
   ```
   - If the user opened a suspect attachment or macro on `PC-LAB-01`, immediately run `05_Security_Defender/Get-PersistenceAndConnectionsAudit.ps1` and `05_Security_Defender/Get-DefenderStatus.ps1` to verify zero active persistence or malicious outbound connections.

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- `InternetMessageId` (`<...>`), sender address/IP (`198.51.100.10`), full sanitized `Authentication-Results`, count of affected internal mailboxes from **Message Trace**, URLScan report link (Private/Unlisted), and whether ANY user clicked links or opened attachments.

## Deep-Dive Investigation (L3)
1. **Compromised Vendor Tenant vs. Lookalike Domain vs. Direct Spoof:**
   - When `SPF=pass`, `DKIM=pass`, `DMARC=pass` holds cleanly yet the content demands urgent wire transfers, gift cards, or a suspicious SharePoint/DocuSign PDF link -> **a legitimate external business partner's mailbox is likely compromised!** Phone-verify with the partner out-of-band using a known trusted directory number (NEVER reply to the email thread!).
2. **Thread Hijacking & Tenant Allow/Block Audit (`[Exchange Admin Center](https://admin.exchange.microsoft.com/)`):** Check Exchange Mail Flow Rules (`Get-TransportRule`) and Tenant Allow/Block Lists (TABL) in **[Microsoft Defender Portal](https://security.microsoft.com/)** to confirm old permissive `BypassSpamFiltering` allow rules didn't bypass Defender EOP filtering.
3. **Purview Content Search & Compliance Purge Scope (`ZAP` vs `New-ComplianceSearchAction -Purge`):** If Defender **Zero-hour Auto Purge (ZAP)** is disabled or failed on an older on-prem/POP/IMAP client, prepare an exact `Subject + From + Received` query scoped strictly to the confirmed phishing `InternetMessageId` before soft-deleting across mailboxes.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Verify identity and `SPF/DKIM/DMARC` alignment BEFORE releasing any message from Defender Quarantine, and double-check the exact search query / hit count before hard-purging emails from all user mailboxes!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Block Malicious Sender/URL in Defender Tenant Allow/Block List & Quarantine Release)**
   - **Confirmed Phishing / Malicious:** In **[Microsoft Defender Portal](https://security.microsoft.com/) -> Policies & rules -> Threat policies -> Tenant Allow/Block Lists**, block the malicious **Sender domain/email**, **URL**, and **File SHA-256 hash**.
   - **Verified False Positive Only:** In **Review -> Quarantine**, select the verified clean message -> click **Release message** (do **NOT** check *"Submit to Microsoft"* or *"Add sender to tenant allow list"* permanently if `SPF`/`DMARC` failed — ask the legitimate sender to fix their DNS!).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Soft-Delete Phishing Campaign Across All Tenant Mailboxes)**
   - Via **[Microsoft Defender Portal](https://security.microsoft.com/) -> Email & collaboration -> Explorer** (Defender for Office 365 P1/P2): filter by `InternetMessageId` -> **Actions -> Move to deleted items / Soft delete**.
   - Or via Security & Compliance PowerShell (`Connect-IPPSSession` with Search And Purge role — verify `Get-ComplianceSearch` results FIRST!):
   ```powershell
   # Verify exact hit count before running Purge!
   New-ComplianceSearch -Name "PhishPurge_TicketExample" -ExchangeLocation All `
       -ContentMatchQuery '(InternetMessageId:"<example-msg-id@example.org>")'
   Start-ComplianceSearch -Identity "PhishPurge_TicketExample"
   # Wait until Status = Completed and review Items count via Get-ComplianceSearch
   New-ComplianceSearchAction -SearchName "PhishPurge_TicketExample" -Purge -PurgeType SoftDelete
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 User Clicked or Opened Attachment)**
   - Immediately revoke Entra sessions, reset password + review MFA (`[sec-001]` / `[id-003]`), and isolate/scan `PC-LAB-01` (`[sec-008]`).

## Verification & Post-Fix Checks
1. Re-run **Message Trace** in **[Exchange Admin Center](https://admin.exchange.microsoft.com/)** and **Quarantine / Threat Explorer** in **[Microsoft Defender Portal](https://security.microsoft.com/)** to verify `0` copies remain delivered in user inboxes and the malicious sender/URL is blocked tenant-wide.
2. Confirm with `jsmith@example.com` (and affected recipients) that the phishing message has disappeared from Inbox/Junk and remind users to report future suspicious mail with the Outlook **Report Phishing** button.

## Cross-Subject Escalation & Pivot Links
- **User clicked phishing link, entered password, or approved MFA prompt (P1 BEC):** [sec-001 — Suspected Business Email Compromise and Session Token Theft](./sec-001-bec-token-compromise.md)
- **User triggered Entra Risky Sign-In or opened malicious payload on workstation:** [sec-008 — Entra Risky Sign-In Alert, Impossible Travel, and Endpoint Malware Containment](./sec-008-entra-risky-signin-impossible-travel-and-malware-containment.md)
- **Legitimate email bounces (`550 5.7.1`) or DMARC/SPF configuration needed on client domain:** [m365-006 — Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping](../02_M365_Email_Collab/m365-006-exchange-ndr-550-and-shared-mailbox-missing.md)
- **User requires MFA reset or Temporary Access Pass after phishing compromise:** [id-003 — Entra ID MFA New Phone, Lost Authenticator, and Temporary Access Pass Recovery](../01_Identity_AD_Entra/id-003-entra-mfa-new-phone-and-tap-recovery.md)

## Useful Links & External Tools
- **[Microsoft Defender Portal](https://security.microsoft.com/)** — Quarantine review, Threat Explorer campaign purge, Anti-Phishing policies, and Tenant Allow/Block Lists.
- **[Exchange Admin Center](https://admin.exchange.microsoft.com/)** — Message Trace for recipient blast radius and Mail Flow Transport Rule audit.
- **[Microsoft Message Header Analyzer](https://mha.azurewebsites.net/)** — Decode Outlook/Exchange SMTP headers, hop delays, SCL/BCL spam scores, and `Authentication-Results`.
- **[Google Admin Toolbox (Dig & Messageheader)](https://toolbox.googleapps.com/apps/main/)** — Alternative header & DNS dig analyzer for Google Workspace / Gmail incidents.
- **[URLScan.io](https://urlscan.io/)** — Safely inspect phishing landing pages, redirect chains, and screenshots in Private/Unlisted mode without touching endpoints.
- **[MXToolbox SuperTool](https://mxtoolbox.com/SuperTool.aspx)** — Inspect external sender SPF/DKIM/DMARC records and sending IP blacklists.

## Client Update Snippets (EN / FR)
- **EN:** We completed our security header and link analysis of the suspicious email, blocked the sender/URL across the organization, and removed remaining copies from mailboxes (or verified authentication alignment before releasing a false positive). Remember never to click unexpected links or approve surprise MFA prompts — please contact us immediately if anyone interacted with the message.
- **FR:** Nous avons terminé l'analyse de sécurité des en-têtes et des liens du courriel suspect, bloqué l'expéditeur/URL à l'échelle de l'organisation et nettoyé les boîtes de réception (ou validé l'authenticité avant libération de quarantaine). N'hésitez pas à nous aviser immédiatement si quelqu'un a cliqué sur un lien ou saisi un mot de passe.
