---
id: sec-001
domain: 06_Security_Access
subject: "Security & Access"
subcategory: bec_defender_threats
title: Suspected Business Email Compromise and Session Token Theft
tier: L3
keywords_en:
  - suspicious email
  - account compromised
  - forwarding rule
  - impossible travel
  - phishing click
  - session hijack
keywords_fr:
  - hameçonnage
  - hameconnage
  - courriel suspect
  - compte compromis
  - voyage impossible
  - règle de transfert
error_codes:
  - AADSTS50126
  - AADSTS50076
tags:
  - bec_compromise
  - token_theft
os:
  - cross_platform
environment:
  - entra_id
  - m365
  - saas
tools:
  - Microsoft Defender XDR
  - Entra Sign-in Logs
  - Exchange Online PowerShell
  - Microsoft Graph PowerShell
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - id-001
  - m365-006
  - id-003
  - id-007
---

## Fast Triage (Under 2 Minutes)
- Did `jsmith@example.com` click a phishing link, approve an unexpected MFA prompt, or trigger an impossible travel / anomalous token alert?
- Are external recipients receiving phishing emails from `jsmith@example.com` (`Sent Items` / `Deleted Items` activity)?
- Confirm escalation contact with the client's authorized security lead before disabling the account if executive/VIP impact exists.

## Read-Only Diagnostics (L1-L2)
1. Review **Entra ID Sign-in Logs** and **Audit Logs** for `jsmith@example.com` (last 7 days):
   - Look for unfamiliar ASNs, anonymous VPN/TOR exits, `AADSTS50126` spikes, unusual `UserAgent` strings (e.g., `BAV2ROPC`, Python/Go HTTP clients), and newly registered MFA methods or OAuth app consents.
2. Inspect Exchange Online mailbox for unauthorized forwarding or malicious inbox rules (read-only):
   ```powershell
   Connect-ExchangeOnline -ShowBanner:$false
   Get-Mailbox -Identity "jsmith@example.com" | Select-Object ForwardingAddress, ForwardingSmtpAddress, DeliverToMailboxAndForward
   Get-InboxRule -Mailbox "jsmith@example.com" -IncludeHidden |
       Select-Object Name, Enabled, Priority, MoveToFolder, DeleteMessage, ForwardTo, RedirectTo
   ```
3. Check local endpoint Defender detections if credential harvesting malware may have executed on `PC-LAB-01`:
   ```powershell
   Get-MpThreatDetection | Select-Object InitialDetectionTime, ThreatID, ActionSuccess, Resources
   ```

## Deep-Dive Investigation (L3)
1. Query **Unified Audit Log** (`Search-UnifiedAuditLog`) around the earliest suspicious sign-in timestamp (`198.51.100.10` placeholder) for `New-InboxRule`, `Set-InboxRule`, `MailItemsAccessed`, `Send`, and `Add-MailboxPermission`.
2. Export suspicious sign-in `CorrelationId` and `SessionId` values to determine whether a **primary refresh token / AitM session cookie** was stolen (which bypasses password resets unless sessions are explicitly revoked!).
3. Inspect Entra **Enterprise Applications -> User Consent** for illicit OAuth apps granted `Mail.Read` / `Mail.Send` permissions.
4. Check for internal lateral phishing (`Send` events to coworkers in `contoso.com`) and verify whether any MFA phone/authenticator method was added by the attacker.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Immediately revoke all active Entra ID refresh tokens & sessions and block/disable sign-in or reset password using a strong generated credential:
   ```powershell
   Connect-MgGraph -Scopes "User.ReadWrite.All", "UserAuthenticationMethod.ReadWrite.All"
   Revoke-MgUserSignInSession -UserId "jsmith@example.com"
   ```
   *(If ongoing AitM abuse is confirmed, also set `AccountEnabled = $false` temporarily until MFA methods and endpoint cleanliness are verified.)*
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Remove malicious Exchange inbox rules and unauthorized `ForwardingSmtpAddress` values:
   ```powershell
   Set-Mailbox -Identity "jsmith@example.com" -ForwardingSmtpAddress $null -DeliverToMailboxAndForward $false
   Remove-InboxRule -Mailbox "jsmith@example.com" -Identity "<MaliciousRuleIdentity>"
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Remove any attacker-added MFA methods and revoke unauthorized OAuth enterprise app grants in Entra ID.
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Purge outbound/inbound phishing copies across tenant mailboxes using Defender Threat Explorer / Content Search if lateral emails were sent.

## Verification & Post-Fix Checks
1. Confirm `Get-InboxRule -Mailbox "jsmith@example.com" -IncludeHidden` and `ForwardingSmtpAddress` show only legitimate entries.
2. Confirm no new sign-in events occur from suspicious IPs after token revocation and MFA re-verification, and run a full Defender Antivirus quick/full scan on `PC-LAB-01`.

## Cross-Subject Escalation & Pivot Links
- **Credential stuffing / password spray triggers AD Event 4740 or Entra Smart Lockout:** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)
- **Attacker inbox rule or phishing blast triggers 550 5.7.708 outbound spam block:** [m365-006 — Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping](../02_M365_Email_Collab/m365-006-exchange-ndr-550-and-shared-mailbox-missing.md)
- **Unauthorized MFA Authenticator method registered by attacker requires TAP/method reset:** [id-003 — Entra ID MFA New Phone, Lost Authenticator, and Temporary Access Pass Recovery](../01_Identity_AD_Entra/id-003-entra-mfa-new-phone-and-tap-recovery.md)
- **Unexpected foreign country sign-in reflects stolen session cookie bypassing Geo-Block:** [id-007 — Geo-Blocking Outside Canada, Conditional Access Named Locations & Travel Access](../01_Identity_AD_Entra/id-007-geo-blocking-outside-canada-travel-access.md)

## Useful Links & External Tools
- **[VirusTotal](https://www.virustotal.com/)** — Check suspicious attachments by **SHA-256 hash** or malicious links/IPs (**never** upload confidential client documents!).
- **[AbuseIPDB](https://www.abuseipdb.com/)** — Inspect unfamiliar sign-in IPs from Entra Sign-in Logs for known VPN/Tor exit nodes or brute-force reputation.
- **[URLScan.io](https://urlscan.io/)** — Safely inspect phishing URLs in an **Unlisted/Private** sandbox (strip any user token parameters first!).
- **[Have I Been Pwned](https://haveibeenpwned.com/)** & **[Entra Admin Center](https://entra.microsoft.com/)** — Check third-party breach exposure and manage Entra token revocation.

## Client Update Snippets (EN / FR)
- **EN:** We detected unauthorized sign-in activity on `jsmith@example.com`, revoked all active sessions, reset credentials, and removed unauthorized mailbox rules. Please contact our service desk by phone to complete secure MFA re-verification before signing back in.
- **FR:** Nous avons détecté une activité de connexion non autorisée sur `jsmith@example.com`, révoqué toutes les sessions actives, réinitialisé les accès et supprimé les règles de boîte aux lettres suspectes. Veuillez contacter notre centre de services par téléphone pour valider de nouveau votre MFA avant la reconnexion.
