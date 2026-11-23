---
id: m365-013
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: email_exchange_mailflow
title: Outlook Emails Stuck in Outbox and Won't Send (Work Offline, Large Attachment, or OST Sync Lock)
tier: L1
keywords_en:
  - outlook email stuck in outbox
  - outlook won't send email
  - email stays stuck in outbox
  - outlook outbox not sending
  - outlook work offline stuck
  - outlook send receive error
keywords_fr:
  - courriel bloque boite d'envoi
  - courriel bloque boite envoi outlook
  - outlook n'envoie pas les courriels
  - email reste bloque dans boite d'envoi
  - outlook travaille hors connexion
  - erreur envoi reception outlook
error_codes:
  - "0x8004010F"
  - "0x80040115"
  - "0x800CCC0E"
  - OUTBOX_STUCK
  - WORK_OFFLINE
tags:
  - outlook_outbox_stuck
  - outlook_wont_send
os:
  - windows
  - macos
environment:
  - m365
  - local_endpoint
tools:
  - Microsoft Outlook
  - Outlook on the Web (OWA)
  - PowerShell
  - Exchange Admin Center
risk_level: low
requires_admin: false
last_verified: 2026-11-23
related_ids:
  - m365-001
  - m365-006
  - m365-008
  - m365-009
  - app-002
linked_scripts:
  - 03_M365/Get-OutlookAddins.ps1
  - 03_M365/Get-EntraRegistrationStatus.ps1
  - 03_M365/Get-MailDNSRecords.ps1
  - 03_M365/Clear-OutlookCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are **ALL outgoing emails** sitting in the **Outbox**, or is **one large email (attachment > 25–35 MB)** sitting at the top of the Outbox blocking everything queued behind it?
2. Look at the **bottom-right status bar** of Outlook: does it show **`Working Offline`**, **`Disconnected`**, **`Trying to connect...`**, **`Need Password`**, or **`Connected to: Microsoft Exchange`**?
3. Can `jsmith@example.com` send a quick plain-text test email from **Outlook on the Web ([Outlook on the Web](https://outlook.office.com/))**? *(Instantly unblocks urgent work AND separates a local Outlook desktop problem from an Exchange Online account/quota block!)*
4. Is the user using **Classic Outlook (`OUTLOOK.EXE`)** or **New Outlook for Windows (`olk.exe`)**, and sending from their **primary mailbox** or a **Shared Mailbox / Send-As alias**?

### Initial Scope & Classification
- **Web ([Outlook on the Web](https://outlook.office.com/)) sends fine, Desktop Outbox stuck:** Local Outlook issue — usually **Work Offline** toggled on, an **oversized attachment (> 25 MB)**, an Outbox message **opened while queued** (loses italicized queued status), a **COM add-in** hooking `ItemSend`, or a **corrupted `.ost` / 50 GB OST ceiling**.
- **Both Web AND Desktop fail to send:** Server-side Exchange Online issue — mailbox full (`554 5.2.2` -> `[m365-008]`), outbound spam restriction / NDR bounce (`[m365-006]`), missing `Send As` permission on a Shared Mailbox, or Entra password/auth block (`[m365-001]`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI, Fixes ~80% of Calls!)
1. **Check `Work Offline` Toggle & Status Bar:**
   - Open the **`Send / Receive`** tab in Classic Outlook -> check if **`Work Offline`** is highlighted/shaded (or bottom status bar shows **`Working Offline`**).
   - If status bar shows **`Need Password`** or **`Disconnected`**, pivot to `[m365-001]` for Modern Auth recovery.
2. **Inspect the `Outbox` Folder Visually:**
   - Check the **size of the oldest message** at the top of the Outbox: Exchange Online defaults to **25–35 MB** max message size (with ~33% Base64 encoding overhead, a 22 MB PDF can exceed a 25 MB limit!).
   - Check whether the stuck message subject is **italicized** vs **regular (non-italic) text**: opening/double-clicking an email while it sits in the Outbox removes the queued italic flag so Outlook will **never** try to send it until opened and clicked **Send** again.
3. **Inspect Send/Receive Error Details & `Sync Issues` Folder:**
   - Click **`Send / Receive -> Show Progress`** (or press `Shift+F9`) and record any exact error code (`0x8004010F`, `0x80040115`, `0x800CCC0E`, `554 5.2.2`).
   - Switch to **Folders view (`Ctrl+6`)** -> inspect **`Sync Issues`** and **`Local Failures`** for recent red rejection timestamps and server error codes.
4. **Check Delayed Delivery / Outgoing Rules:**
   - Open the stuck email (after going Offline in Remediation) or check **`File -> Manage Rules & Alerts`** to verify no client-side rule delays sending by X minutes (`defer delivery by a number of minutes`).

### L2 Technical Diagnostics
1. **Audit Outlook Process, `.ost` File Size (50 GB Ceiling), COM Add-ins & Exchange Endpoint Connectivity on `PC-LAB-01` (read-only):**
   ```powershell
   # Check running Outlook clients and local .ost mailbox cache sizes (near 50 GB blocks sends!)
   Get-Process -Name OUTLOOK, olk -ErrorAction SilentlyContinue | Select-Object Name, Id, WorkingSet64
   Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Outlook" -Filter "*.ost" -ErrorAction SilentlyContinue |
       Select-Object Name, @{N='SizeGB';E={[math]::Round($_.Length/1GB,2)}}, LastWriteTime

   # Check Classic Outlook Offline / MAPI add-ins (read-only)
   Get-ChildItem "HKCU:\Software\Microsoft\Office\Outlook\Addins" -ErrorAction SilentlyContinue |
       ForEach-Object { Get-ItemProperty $_.PSPath } |
       Select-Object PSChildName, FriendlyName, LoadBehavior

   # Verify HTTPS connectivity to Exchange Online front door
   Test-NetConnection -ComputerName "outlook.office365.com" -Port 443 |
       Select-Object ComputerName, RemoteAddress, TcpTestSucceeded
   ```
   *(You can also run the linked `Get-OutlookAddins.ps1`, `Get-EntraRegistrationStatus.ps1`, and `Get-MailDNSRecords.ps1` scripts directly from PowerShellStore.)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm whether **Outlook on the Web** sends cleanly, Classic vs New Outlook, exact status bar state, exact Send/Receive error code (`0x8004010F` / `0x800CCC0E` / `554 5.2.2`), largest Outbox attachment size, and local `.ost` size in GB.

## Deep-Dive Investigation (L3)
1. **50 GB `.ost` File Size Ceiling & Corrupted MAPI Store (`0x8004010F`):** Classic Outlook enforces a default **50 GB** limit (`MaxLargeFileSize` / `WarnLargeFileSize`) on `.ost` files. Once the `.ost` approaches 47–50 GB or its MAPI Outbox table corrupts (`0x8004010F` — *"Outlook data file cannot be accessed"*), messages queue locally in the Outbox and silently stall.
2. **Third-Party COM Add-ins & Antivirus Mail Shields (`0x800CCC0E`):** DLP, PDF, CRM, encryption, or endpoint antivirus Outlook add-ins that hook the `Application.ItemSend` event can hang silently, leaving items permanently in the Outbox. Testing with `outlook.exe /safe` isolates COM add-ins immediately.
3. **Exchange Online Quotas, Message Size Limits, & Outbound Spam Blocks (read-only EXO PowerShell):**
   ```powershell
   # Run in Exchange Online PowerShell (read-only) when Web OWA also fails to send
   Get-Mailbox -Identity "jsmith@example.com" | Select-Object DisplayName, MaxSendSize, MaxReceiveSize
   Get-MailboxStatistics -Identity "jsmith@example.com" | Select-Object TotalItemSize, TotalDeletedItemSize
   Get-BlockedSenderAddress -SenderAddress "jsmith@example.com"
   ```

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Never delete an unsent Outbox message or rename an `.ost` file without first moving/saving any important unsent email text and attachments to **Drafts** (or saving attachments to disk) so user work is never lost!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Unstick Outbox & Oversized Attachment — Fixes Most Cases!)**
   - In Classic Outlook, click **`Send / Receive -> Work Offline`** (toggle **ON** so Outlook stops locking the stuck item).
   - Open the **`Outbox`** folder and **drag the stuck message(s) into `Drafts`** (if Outlook says *"Outlook has already begun transmitting this message"*, close Outlook completely, confirm `OUTLOOK.EXE` is gone in Task Manager, reopen Outlook offline, then drag it to **Drafts**).
   - If the email has an attachment over **20–25 MB**, save the file to **OneDrive / SharePoint**, delete the attachment from the draft, and paste a sharing link instead.
   - Click **`Send / Receive -> Work Offline`** (toggle **OFF** so status bar shows **`Connected to: Microsoft Exchange`**).
   - Open the draft in **`Drafts`** and click **`Send`** again so it enters the Outbox properly queued.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Isolate COM Add-in Blocking `ItemSend`)**
   - Close Outlook completely and launch Safe Mode from `Win + R`:
     ```cmd
     outlook.exe /safe
     ```
   - Send a small test email to `jsmith@example.com`. If it leaves the Outbox immediately in Safe Mode, open **`File -> Options -> Add-ins -> Manage: COM Add-ins -> Go...`** and uncheck recently added CRM/PDF/antivirus add-ins one by one.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Clear Outlook Cache or Create Clean MAPI Profile for `0x8004010F`)**
   - First copy/move any unsent Outbox emails into **Drafts** or save their content externally, close Outlook, and run the linked `03_M365/Clear-OutlookCache.ps1` script.
   - If `0x8004010F` or `.ost` corruption persists, open **`Control Panel -> Mail (Microsoft Outlook) -> Show Profiles -> Add...`** to create a fresh Outlook profile (or rename the `.ost` to `.ost.bak` after verifying zero local-only folders exist) and set the new profile as default.

## Verification & Post-Fix Checks
1. Confirm Outlook's bottom-right status bar reads **`Connected to: Microsoft Exchange`** (not `Working Offline` or `Disconnected`).
2. Send a small test email to `jsmith@example.com` (and an external test recipient if applicable) and confirm the **`Outbox`** count drops to **`0`** and the message appears in **`Sent Items`** within 10–30 seconds.
3. Verify the message also appears in **`Sent Items`** on **Outlook on the Web ([Outlook on the Web](https://outlook.office.com/))** to confirm full Exchange Online sync.

## Cross-Subject Escalation & Pivot Links
- **Status bar shows `Need Password` or `Disconnected` (Modern Auth token failure `0x80040115`):** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](./m365-001-outlook-auth-loop.md)
- **Email leaves Outbox but bounces back with a 550 NDR or gets blocked in Quarantine:** [m365-006 — Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping](./m365-006-exchange-ndr-550-and-shared-mailbox-missing.md)
- **Sending fails in both Desktop and Web because mailbox quota is 100% full (`554 5.2.2`):** [m365-008 — Exchange Online Mailbox Full (554 5.2.2) & Online Archive Not Moving Mail](./m365-008-exchange-mailbox-full-and-online-archive-stuck.md)
- **Corrupted local `.ost` file (`0x80040119`) also breaks Outlook search indexing:** [m365-009 — Outlook Search Not Returning Results, Indexing Broken, or OST File Corrupted](./m365-009-outlook-search-not-working-indexing-and-ost-repair.md)
- **Outlook freezes on send/open due to broken COM add-in conflict:** [app-002 — Excel/Word Freezing on Open, COM Add-in Conflict, and PDF Previewer Failure](../09_Apps_LOB/app-002-office-addins-crash-and-pdf-preview-failure.md)

## Useful Links & External Tools
- **[Microsoft 365 Service Health Status](https://status.cloud.microsoft/)** — Rule out active Exchange Online mail submission or client connectivity outages.
- **[Microsoft Remote Connectivity Analyzer](https://testconnectivity.microsoft.com/)** — Test Outlook Autodiscover, Exchange Online connectivity, and outbound SMTP health.
- **[Exchange Admin Center](https://admin.exchange.microsoft.com/)** — Run Message Trace or verify mailbox send limits and outbound spam blocks if Web OWA also fails.
- **[Microsoft 365 Apps Update History](https://learn.microsoft.com/en-us/officeupdates/update-history-microsoft365-apps-by-date)** — Check for patched Classic/New Outlook Outbox sync bugs in the user's Office Click-to-Run build.
- **[Microsoft 365 Apps Admin Center](https://config.office.com/)** — Verify Office Click-to-Run update channels and Outlook client build health.

## Client Update Snippets (EN / FR)
- **EN:** We cleared the stuck Outbox queue in Outlook on `PC-LAB-01`, confirmed Outlook is online and connected to Microsoft Exchange, and verified that outgoing messages now send normally and appear in Sent Items. Could you please send a quick test email to confirm everything is working properly on your side?
- **FR:** Nous avons débloqué la boîte d'envoi d'Outlook sur `PC-LAB-01`, confirmé que le mode hors connexion est désactivé et vérifié que les courriels partent normalement vers les Éléments envoyés. Pouvez-vous envoyer un courriel test pour confirmer que tout fonctionne bien de votre côté ?
