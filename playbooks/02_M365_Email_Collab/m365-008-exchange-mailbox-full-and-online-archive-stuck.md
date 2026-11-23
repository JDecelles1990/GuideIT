---
id: m365-008
domain: 02_M365_Email_Collab
subject: Microsoft 365 / Email & Collaboration
subcategory: email_exchange_mailflow
title: Exchange Online Mailbox Full (554 5.2.2) & Online Archive Not Moving Mail
tier: L2
keywords_en:
  - mailbox full
  - cannot send or receive email
  - recoverable items folder full
  - online archive stuck
  - exchange quota exceeded
  - managed folder assistant
keywords_fr:
  - boite courriel pleine
  - archive en ligne exchange bloquee
  - quota depasse courriel
  - elements recuperables pleins
  - impossible envoyer recevoir courriel
error_codes:
  - 554 5.2.2
  - MAILBOX_FULL
tags:
  - mailbox_full_quota
  - online_archive_stuck
os:
  - cross_platform
environment:
  - m365
tools:
  - PowerShell (ExchangeOnlineManagement)
  - Exchange Admin Center
  - Microsoft Purview Portal
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - m365-006
  - m365-001
  - sec-004
linked_scripts:
  - 03_M365/Get-OutlookAddins.ps1
  - 03_M365/Clear-OutlookCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is the user **blocked from sending/receiving email (`554 5.2.2 mailbox full`)**, OR does Outlook just warn **"Your mailbox is almost full"** while **Online Archive isn't clearing older items**?
2. When trying to delete old big emails + empty **Deleted Items**, does Outlook still show 99–100% full (classic sign that hidden **`Recoverable Items`** folder hit 100 GB under Retention/Litigation Hold!)?
3. Is this an **unlicensed Shared Mailbox (`50 GB` cap!)** vs a **User Mailbox**, and what M365 license (`Business Basic` 50 GB vs `Business Premium / E3` 50 GB / `Exchange Plan 2` 100 GB) is assigned?

### Initial Scope & Classification
- Verify license/quota limits (`50 GB` vs `100 GB`), whether **In-Place Online Archive** is already enabled, and whether **Litigation Hold** or a **Purview Retention Policy** prevents purging deleted mail!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — User Outlook & EAC GUI)
1. **Check Mailbox Storage Breakdown in Outlook Web ([Outlook on the Web](https://outlook.office.com/) -> Settings (`Gear`) -> Account -> Storage):**
   - Look visually at WHICH folder consumes the 50/100 GB (**Deleted Items**, **Sent Items**, large attachment mail, or **Empty Deleted Items** -> also check **Recover items deleted from this folder**!).
   - Have the user verify they actually want old Deleted Items/Sent Items emptied vs archived before deleting anything!
2. **Check M365 License & Archive Status in Admin Centers ([Microsoft 365 Admin Center](https://admin.microsoft.com/) & [Exchange Admin Center](https://admin.exchange.microsoft.com/)):**
   - Verify whether `jsmith@contoso.com` holds **Exchange Plan 2 / E3 / E5 / Business Premium** (required for **In-Place Archive**!).
   - In **Exchange Admin Center -> Recipients -> Mailboxes -> `jsmith@contoso.com` -> Others -> Manage mailbox archive**: verify whether **Mailbox archive status** is `Disabled` vs `Enabled`, and view current primary vs archive GB bars!

### L2 Technical Diagnostics
Connect to Exchange Online PowerShell (`EXO` v3 REST cmdlets) to inspect mailbox quotas, primary + archive usage, and the `Recoverable Items` folders:

```powershell
Connect-ExchangeOnline

$upn = "jsmith@contoso.com"

# 1. Inspect mailbox quotas, Archive state, and Hold flags
Get-EXOMailbox -Identity $upn -Properties ProhibitSendQuota, ProhibitSendReceiveQuota, IssueWarningQuota, ArchiveStatus, ArchiveState, AutoExpandingArchiveEnabled, RetentionPolicy, LitigationHoldEnabled, InPlaceHolds, RetainDeletedItemsFor |
  Format-List DisplayName, ProhibitSendQuota, ProhibitSendReceiveQuota, ArchiveStatus, ArchiveState, AutoExpandingArchiveEnabled, RetentionPolicy, LitigationHoldEnabled, InPlaceHolds

# 2. Primary mailbox size vs. Archive mailbox size
Get-EXOMailboxStatistics -Identity $upn | Select-Object DisplayName, TotalItemSize, TotalDeletedItemSize, ItemCount, StorageLimitStatus
Get-EXOMailboxStatistics -Identity $upn -Archive -ErrorAction SilentlyContinue | Select-Object DisplayName, TotalItemSize, ItemCount
```

Check `Recoverable Items` breakdown (where `Deletions`, `Versions`, `DiscoveryHolds`, or `Purges` frequently hit 100 GB silently):

```powershell
Get-EXOMailboxFolderStatistics -Identity $upn -FolderScope RecoverableItems |
  Select-Object FolderPath, ItemsInFolder, FolderSize, FolderAndSubfolderSize | Format-Table -AutoSize
```

## Deep-Dive Investigation (L3)
When Online Archive is enabled (`ArchiveStatus: Active`) yet items from 2+ years ago remain stuck in the primary mailbox, inspect the **Managed Folder Assistant (ELC)** diagnostic logs and retention tags:

```powershell
# Check when Managed Folder Assistant (ELC) last processed the mailbox and why it skipped
$elc = Export-MailboxDiagnosticLogs -Identity $upn -ExtendedProperties
$elc.MailboxLog
([xml]($elc.MailboxLog)).Properties.MailboxTable.Property |
  Where-Object { $_.Name -like "*ELC*" -or $_.Name -like "*Retention*" -or $_.Name -like "*Hold*" } |
  Format-Table Name, Value -AutoSize

# Inspect the Retention Policy and linked tags (Move to Archive / Delete)
$policyName = (Get-EXOMailbox -Identity $upn -Properties RetentionPolicy).RetentionPolicy
Get-RetentionPolicy $policyName | Format-List Name, RetentionPolicyTagLinks
```

Key root causes to distinguish:
1. **`Recoverable Items` >= 98 GB under Hold:** With `LitigationHoldEnabled` or a Purview Retention Policy active, user deletions go to `DiscoveryHolds` until `Recoverable Items` hits 100 GB (or 110 GB with Auto-Expanding Archive).
2. **`ElcLastRunTotalProcessingTime` stale or `RetentionPolicy` has no Archive Tag:** Managed Folder Assistant runs on an ~7-day cycle, or the assigned `RetentionPolicy` lacks a "Move to Archive" tag (e.g., `Default 2 Year Move to Archive`), or user enabled **Delay Hold Applied** (`DelayHoldApplied` / `DelayReleaseHoldApplied`).
3. **50 GB cap on Plan 1 / Unlicensed Shared Mailbox:** Mailbox hit 50 GB ProhibitSendReceive quota with no Archive enabled.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER disable Litigation Hold, Retention Policies, or purge `Recoverable Items` without written compliance/legal approval — doing so can permanently destroy regulated audit/eDiscovery data. Confirm license assignments and retention targets with the client first.

1. **Enable Online Archive (Requires Valid License — e.g., Exchange Online Plan 2 / Business Premium):**
   - Scope: Target mailbox `<user-upn>`.
   ```powershell
   # Enables cloud In-Place Archive for the user
   Enable-Mailbox -Identity "jsmith@contoso.com" -Archive
   ```
2. **Assign Archive Retention Policy & Trigger Managed Folder Assistant:**
   - Ensure the assigned `RetentionPolicy` includes an active **Move to Archive** tag (for example moving mail older than 1 or 2 years), then wake Managed Folder Assistant:
   ```powershell
   # Confirm approved RetentionPolicy name before applying
   Set-Mailbox -Identity "jsmith@contoso.com" -RetentionPolicy "<Approved-Archive-Policy>"
   Start-ManagedFolderAssistant -Identity "jsmith@contoso.com"
   ```
3. **Mitigate Full `Recoverable Items` Under Approved Hold (`AutoExpandingArchive`):**
   - **[REMEDIATION — CONFIRM BEFORE RUNNING]** Auto-expanding archive adds incremental archive storage automatically once enabled and **cannot be turned off later**.
   ```powershell
   Enable-Mailbox -Identity "jsmith@contoso.com" -AutoExpandingArchive
   Start-ManagedFolderAssistant -Identity "jsmith@contoso.com"
   ```
   - Note: Moving held `Recoverable Items` into an Auto-Expanding Archive or upgrading from Exchange Plan 1 to Plan 2 requires up to **24–72 hours** of background Exchange processing after triggering Managed Folder Assistant.

## Verification & Post-Fix Checks
- Re-run `Get-EXOMailboxStatistics -Identity <user-upn>` and `Get-EXOMailboxStatistics -Identity <user-upn> -Archive` to verify primary mailbox size drops below `IssueWarningQuota` and `StorageLimitStatus` returns to `BelowLimit`.
- Inspect `Export-MailboxDiagnosticLogs -ExtendedProperties` to confirm `ELCLastSuccessTimestamp` updated recently after `Start-ManagedFolderAssistant`.
- Send a test internal/external message to confirm `554 5.2.2` NDRs have stopped and the user can both delete and send messages in Outlook/OWA.

## Cross-Subject Escalation & Pivot Links
- **Full mailbox quota generates inbound 554 5.2.2 NDR bounces for external senders:** [m365-006 — Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping](./m365-006-exchange-ndr-550-and-shared-mailbox-missing.md)
- **Mailbox quota exhaustion and bloated OST trigger Outlook disconnect / auth loops (0x80040115):** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](./m365-001-outlook-auth-loop.md)
- **Purview Retention Policy or Litigation Hold fills Recoverable Items (100 GB) blocking deletes:** [sec-004 — Microsoft Purview DLP Policy Blocks & Sensitivity Label Encryption Denied](../06_Security_Access/sec-004-purview-dlp-block-and-sensitivity-labels.md)

## Useful Links & External Tools
- [Microsoft 365 Admin Center](https://admin.microsoft.com/) — Verify Exchange Online Plan 1 vs Plan 2 / Business Premium license assignments before enabling Archive.
- [Microsoft Exchange Admin Center](https://admin.exchange.microsoft.com/) — Monitor mailbox usage gauges, Archive status, and message traces.
- **[Microsoft Purview Compliance Portal](https://purview.microsoft.com/)** — Check Litigation Hold / Retention policies locking `Recoverable Items` at 100 GB.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, your mailbox reached its storage limit (`554 5.2.2`), causing new emails to bounce and preventing sending/deleting. We verified your retention/archive configuration (`<Archive enabled / Managed Folder Assistant triggered / license updated>`). Please allow up to 24 hours for background archiving to free space in your primary mailbox, and let us know if sending resumes normally.
- **FR:** Bonjour `<user>`, votre boîte courriel a atteint son quota maximal (`554 5.2.2`), bloquant l'envoi et la réception. Nous avons vérifié la stratégie de rétention et activé/relancé l'archivage en ligne (`Managed Folder Assistant`). L'archivage en arrière-plan peut prendre jusqu'à 24 heures pour libérer la boîte principale; merci de confirmer que la messagerie redevient fonctionnelle.
