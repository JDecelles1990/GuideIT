---
id: m365-011
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: email_exchange_mailflow
title: Outlook Calendar Sharing, Delegate Permissions, and Meeting Room Booking Errors
tier: L1
keywords_en:
  - outlook calendar sharing permission
  - cannot open shared calendar
  - meeting room booking declined
  - outlook delegate access error
  - room calendar conflict double book
keywords_fr:
  - partage calendrier outlook erreur
  - impossible ouvrir calendrier partage
  - salle de reunion refusee outlook
  - permission delegue calendrier outlook
  - conflit reservation salle outlook
error_codes:
  - ROOM_DECLINED
  - CALENDAR_PERM_DENIED
tags:
  - outlook_calendar_sharing
  - room_booking_delegate
os:
  - windows
  - macos
  - cross_platform
environment:
  - m365
tools:
  - Exchange Admin Center
  - Exchange Online PowerShell
  - Microsoft Outlook / OWA
risk_level: low
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - m365-006
  - m365-001
  - m365-009
linked_scripts:
  - 03_M365/Get-OutlookAddins.ps1
  - 03_M365/Get-MailDNSRecords.ps1
  - 03_M365/Clear-OutlookCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you trying to **view/edit a coworker's calendar**, **manage meetings as a Delegate** (missing meeting invites/Send on Behalf), or **book a Conference Room (`Boardroom`)** that immediately declines?
2. Does the calendar or room work properly in **Outlook on the Web (`https://outlook.office.com`)**, or fail in both Outlook Web and Desktop?
3. Did the coworker grant permission **recently** (within the last hour) or is the user an **external partner** (`fabrikam.com`)?
4. When booking a Room, did the auto-decline message say **Conflict**, **Insufficient permissions**, or **No response** at all?

### Initial Scope & Classification
- Distinguish **user/delegate permission mismatch** (`Reviewer` vs `Editor` vs **Delegate**), **Outlook shared calendar sync lag** (fixable via `Outlook Web` or *Shared Calendar Improvements*), and **Exchange Room Resource booking policy** (`AutomateProcessing` / `BookInPolicy` / `AllBookInPolicy`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Test in Outlook on the Web (`outlook.office.com`) first:** Click **Calendar -> Add calendar -> Add from directory**, select the coworker/room, and compare behavior with desktop Outlook.
   - If **Outlook Web works** while **Desktop Outlook shows old/missing events** -> Desktop cached shared calendar state or `"Shared Calendar Improvements"` toggle needs a refresh!
2. **Verify Calendar Permission Level with Owner (GUI):** Have the calendar owner open **Outlook -> Calendar -> Share / Calendar Permissions** and verify `jsmith@example.com` is listed as **`Can edit`** / **`Delegate`** (not just *Can view when I'm busy*!).
3. **Check Room Busy Availability BEFORE Booking:** Open **Scheduling Assistant** in Outlook to verify another recurring meeting isn't genuinely occupying the room (including private/cancelled meetings!).

### L2 Technical Diagnostics
1. **Inspect Calendar Folder ACLs and Delegate State in Exchange Online PowerShell (read-only):**
   ```powershell
   Connect-ExchangeOnline -ShowBanner:$false
   # Inspect user calendar permissions
   Get-MailboxFolderPermission -Identity "owner@contoso.com:\Calendar" |
       Select-Object User, AccessRights, SharingPermissionFlags | Format-Table -AutoSize
   ```
   *(Note: Localized French mailboxes may use `owner@contoso.com:\Calendrier` instead of `:\Calendar` — inspect via `Get-MailboxFolderStatistics -FolderScope Calendar`!)*
2. **Inspect Conference Room Booking Settings (`Get-CalendarProcessing`, read-only):**
   ```powershell
   Get-CalendarProcessing -Identity "room-boardroom@contoso.com" |
       Select-Object AutomateProcessing, AllowConflicts, BookingWindowInDays, MaximumDurationInMinutes, AllBookInPolicy, BookInPolicy, ResourceDelegates |
       Format-List
   ```
   - `AutomateProcessing = None`: Room mailbox isn't set to `AutoAccept`, so requests sit unaccepted forever!
   - `AllBookInPolicy = False` + user missing from `BookInPolicy`: Room restricts who can book automatically -> immediately sends `ROOM_DECLINED`!

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact owner/room email address, requesting user (`jsmith@example.com`), required permission level (`View` / `Edit` / `Delegate`), whether Outlook Web works, and exact Room decline text.

## Deep-Dive Investigation (L3)
1. **Stale Corrupted Delegate Rule (`MAPI` Hidden Inbox Rules):** If a former assistant/delegate still receives meeting invites after removal, inspect hidden `Delegate` forwarding rules (`PR_RULE_MSG_PROVIDER: Schedule+ EMS Interface`) or use **MFCMAPI / `Remove-MailboxFolderPermission`** carefully with backup.
2. **External Federated Calendar Sharing Blocked (`SharingPolicy`):** Check `Get-SharingPolicy` if external contacts cannot view Free/Busy availability across organizations.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Confirm the calendar owner's or office manager's explicit approval before granting `Editor` or `Delegate` rights to someone else's personal mailbox!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Desktop Sync Refresh)** If shared calendar events work in Outlook Web yet lag in Desktop Outlook:
   - Remove the shared calendar from Classic Outlook's left pane (`Right-click -> Delete Calendar` — removes only the shortcut view!), wait 10 seconds, and re-add it cleanly. Verify **File -> Account Settings -> Account Settings -> Change -> More Settings -> Advanced -> Turn on shared calendar improvements** is enabled.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Update Calendar or Delegate Permission)** Only after owner approval:
   ```powershell
   # Add or update calendar permission cleanly (adjust folder name if localized)
   Add-MailboxFolderPermission -Identity "owner@contoso.com:\Calendar" -User "jsmith@example.com" -AccessRights Editor
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Fix Room Auto-Accept / Booking Policy)**
   ```powershell
   # Ensure conference room auto-processes requests for approved users
   Set-CalendarProcessing -Identity "room-boardroom@contoso.com" -AutomateProcessing AutoAccept -AllBookInPolicy $true
   ```

## Verification & Post-Fix Checks
1. Re-run `Get-MailboxFolderPermission` / `Get-CalendarProcessing` to confirm intended rights and `AutoAccept` status.
2. Have `jsmith@example.com` remove/re-add the shared calendar or book a 15-minute test meeting in the room (delete test meeting afterward) and verify instant acceptance + event visibility.

## Cross-Subject Escalation & Pivot Links
- **User also cannot see Shared Mailbox folders in Outlook sidebar (Automapping):** [m365-006 — Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping](./m365-006-exchange-ndr-550-and-shared-mailbox-missing.md)
- **Outlook Desktop fails to update any shared calendar due to broken Modern Auth token:** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](./m365-001-outlook-auth-loop.md)
- **Corrupted local Outlook OST cache hides calendar searches or throws errors:** [m365-009 — Outlook Search Not Working, Indexing Broken, or OST File Corrupted](./m365-009-outlook-search-not-working-indexing-and-ost-repair.md)

## Client Update Snippets (EN / FR)
- **EN:** With approval from the calendar / room owner, we updated the Exchange Online calendar permissions / auto-booking policy and refreshed your shared calendar sync. Please try viewing the calendar or booking the meeting room now and confirm it succeeds.
- **FR:** Avec l'approbation du propriétaire du calendrier / de la salle, nous avons mis à jour les permissions Exchange Online et rafraîchi la synchronisation du calendrier. Pouvez-vous vérifier l'affichage du calendrier ou tester la réservation de la salle ?
