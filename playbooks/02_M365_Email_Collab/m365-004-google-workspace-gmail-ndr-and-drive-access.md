---
id: m365-004
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: email_exchange_mailflow
title: Google Workspace Gmail Delivery Bounce (550 5.7.26) and Shared Drive Access Triage
tier: L2
keywords_en:
  - gmail bounce back
  - google drive access denied
  - shared drive missing
  - google workspace email rejected
  - spf dkim dmarc gmail
keywords_fr:
  - courriel gmail rejete
  - acces refuse google drive
  - disque partage google
  - erreur livraison gmail
  - partage google drive bloque
error_codes:
  - "550 5.7.26"
  - "550 5.7.1"
tags:
  - google_gmail_ndr
  - google_drive_access
os:
  - cross_platform
environment:
  - google_workspace
  - saas
tools:
  - Google Admin Console
  - Email Log Search
  - PowerShell
  - dig
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - m365-006
  - id-002
---

## Fast Triage (Under 2 Minutes)
- Is the incident **outbound/inbound Gmail rejection** (`550 5.7.26` unauthenticated SPF/DKIM/DMARC, `550 5.7.1` policy/spam reject) or **Google Drive / Shared Drive permission denied**?
- For Drive access issues: verify `jsmith@example.com` is signed into the correct corporate Workspace account rather than a secondary personal browser profile.
- For email bounces: grab the full NDR header (`550 5.7.26`, `550 5.7.1`, `SMTP` error details) and recipient domain (`example.org`).

## Read-Only Diagnostics (L1-L2)
1. **Verify Public DNS Mail Authentication (SPF, DKIM, DMARC) for `contoso.com` (read-only):**
   ```powershell
   Resolve-DnsName -Name "contoso.com" -Type TXT | Select-Object Name, Strings
   Resolve-DnsName -Name "_dmarc.contoso.com" -Type TXT -ErrorAction SilentlyContinue | Select-Object Name, Strings
   Resolve-DnsName -Name "google._domainkey.contoso.com" -Type TXT -ErrorAction SilentlyContinue | Select-Object Name, Strings
   ```
   ```bash
   dig +short TXT contoso.com
   dig +short TXT _dmarc.contoso.com
   dig +short TXT google._domainkey.contoso.com
   ```
2. **Trace Email Delivery in Google Admin Console:**
   - Open **Reporting -> Email Log Search**, filter by sender/recipient (`jsmith@example.com`) and message ID, and check post-delivery status (**Delivered**, **Quarantined**, **Rejected**, or **Routing rule match**).
3. **Inspect Google Drive / Shared Drive Permissions & OU Policies:**
   - Check the Shared Drive's **Manage members** list (`Viewer`, `Commenter`, `Contributor`, `Content manager`, `Manager`).
   - In **Admin Console -> Apps -> Google Workspace -> Drive and Docs -> Sharing settings**, verify whether external sharing or Drive creation is blocked for the user's **Organizational Unit (OU)** or **Target Audience**.

## Deep-Dive Investigation (L3)
1. **`550 5.7.26` Bulk Sender / Strict DMARC Failure:** Verify third-party SaaS senders (CRM, ticketing, invoice tools, scan-to-email) sending as `contoso.com` are included in the SPF record (without exceeding the **10 DNS lookup limit**) and configured with their own custom DKIM selector.
2. **Drive DLP / Context-Aware Access Block:** If `jsmith@example.com` gets `"Access denied"` only outside the office or on unmanaged devices, inspect **Security -> Access and data control -> Context-Aware Access** and **Data protection (DLP)** rules blocking Drive downloads or external shares.
3. **Storage Quota Exhaustion:** Check **Admin Console -> Storage** — pooled Workspace storage hitting 100% makes Drive read-only and stalls Gmail attachments.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **`550 5.7.26`** missing authentication: generate/enable **DKIM** (`2048-bit` key under **Apps -> Google Workspace -> Gmail -> Authenticate email**), publish the TXT record in DNS, and click **Start authentication**; update SPF (`v=spf1 include:_spf.google.com ... ~all`) and DMARC (`_dmarc.contoso.com`).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **Shared Drive access denied**: have a **Manager** of the Shared Drive add `jsmith@example.com` (or their Google Group) with the approved role (`Contributor` or `Content manager`), or move the user into the OU allowed to access/share external Drive items.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Release false-positive quarantined messages from **Admin Console -> Apps -> Gmail -> Manage quarantines** after verifying message legitimacy.

## Verification & Post-Fix Checks
1. Confirm **Email Log Search** shows `Delivered` and email headers (`Authentication-Results`) report `spf=pass`, `dkim=pass`, `dmarc=pass`.
2. Have `jsmith@example.com` open the Google Drive folder / Shared Drive in an Incognito corporate session and verify read/edit access works as expected.

## Cross-Subject Escalation & Pivot Links
- **SPF, DKIM, DMARC, or MX TXT records fail public DNS resolution or propagation checks:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Cross-tenant mail bounce affects Exchange Online recipients or tenant MX routing:** [m365-006 — Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping](./m365-006-exchange-ndr-550-and-shared-mailbox-missing.md)
- **Suspended Workspace user or Admin Console 2SV/403 block prevents Drive permission updates:** [id-002 — Google Workspace Admin Console 2SV Lockout, Role 403, and Suspended User Recovery](../01_Identity_AD_Entra/id-002-google-workspace-admin-2sv-lockout.md)

## Useful Links & External Tools
- **[MXToolbox SuperTool](https://mxtoolbox.com/SuperTool.aspx)** — Run `mx:contoso.com`, `spf:contoso.com`, `dmarc:contoso.com`, and `blacklist:<ip>` to inspect mail routing, SPF lookup count (<= 10), and blocklists.
- **[Google Admin Toolbox (Dig & Messageheader)](https://toolbox.googleapps.com/apps/main/)** — Paste sanitized email headers into **Messageheader** to trace delay hops and `Authentication-Results`, or query public TXT/MX records with **Dig**.
- **[Google Workspace Status Dashboard](https://www.google.com/appsstatus/dashboard/)** — Confirm whether Gmail or Google Drive is experiencing an active vendor outage.

## Client Update Snippets (EN / FR)
- **EN:** We verified the Google Workspace mail authentication / Drive sharing configuration and updated the required permissions for `contoso.com`. Could you re-test sending the email or opening the Shared Drive and let us know if it succeeds?
- **FR:** Nous avons vérifié la configuration d'authentification courriel / partage Google Drive dans Google Workspace et ajusté les autorisations pour `contoso.com`. Pouvez-vous tester de nouveau l'envoi ou l'accès au disque partagé et nous confirmer le résultat ?
