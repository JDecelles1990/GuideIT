---
id: m365-012
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: docs_onedrive_teams
title: SharePoint and Teams Missing Files, Recycle Bin Restore, and Library Sync Delays
tier: L1
keywords_en:
  - missing files sharepoint
  - deleted folder teams files
  - restore file onedrive recycle bin
  - sharepoint library sync slow
  - who deleted sharepoint file
keywords_fr:
  - fichiers manquants sharepoint
  - dossier supprime teams sharepoint
  - restaurer corbeille sharepoint onedrive
  - bibliotheque sharepoint synchronisation lente
  - qui a supprime fichier sharepoint
error_codes:
  - SP_FILE_DELETED
  - SYNC_LIBRARY_LIMIT
tags:
  - sharepoint_files_missing
  - sharepoint_recycle_bin
os:
  - windows
  - macos
  - cross_platform
environment:
  - m365
tools:
  - SharePoint Online Web
  - Microsoft Teams
  - OneDrive
  - Microsoft Purview Audit
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - m365-005
  - m365-003
  - m365-002
linked_scripts:
  - 03_M365/Reset-OneDriveSync.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are the missing files gone for **only you in File Explorer / Finder** (`OneDrive` sync issue), or are they **also missing on SharePoint Web (`Open in SharePoint`)** for everyone?
2. Approximately **when** were the files last seen (`today`, `last week`, `over 90 days ago`) and what was the exact folder/filename?
3. Did someone recently **move/drag a folder accidentally**, delete a local synced folder in File Explorer (which syncs deletions to the cloud!), or rename a Teams channel?

### Initial Scope & Classification
- **Golden L1 Rule:** When files disappear from a synced folder on `PC-LAB-01`, **check SharePoint Online Web + Recycle Bin immediately**! Many "lost folder" tickets happen because someone accidentally dragged Folder A inside Folder B in File Explorer or deleted a local copy while thinking *"Stop syncing"* meant removing only the shortcut!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Check the Cloud Source First (Teams -> Files -> `Open in SharePoint`):**
   - Search in the SharePoint Web search bar at the top (searches moved folders inside the site!).
   - Click **Recycle Bin** in the left SharePoint menu! Remember Microsoft 365 keeps deleted SharePoint/OneDrive items for **93 days** across two stages:
     - **First-stage Recycle Bin** (deleted by user -> shows `Deleted By` name + `Original Location`!).
     - **Second-stage Recycle Bin** (scroll to the bottom of Recycle Bin -> *"Check the second-stage recycle bin"*!).
2. **Check Activity Feed (Who Moved or Deleted It?):** Click the **`(i)` Info pane** icon at the top-right of the SharePoint document library to view recent **Activity** (e.g., *"`jsmith@example.com` moved `Finance` to `Archive`"* or *"Deleted 240 items"*).
3. **Verify Sync Status (`SYNC_LIBRARY_LIMIT`):** If files exist on SharePoint Web yet don't show on `PC-LAB-01`, click the OneDrive tray icon -> **Settings -> Account** to verify that library is actually linked and not paused (`[m365-005]`).

### L2 Technical Diagnostics
1. **Check Microsoft Purview Audit Log / Version History (If Empty in Both Recycle Bins or Mass Rename/Delete):**
   - Inspect **Purview Audit Search** (`FileDeleted`, `FileMoved`, `FileRecycled`, `FileRenamed`) across the suspected 7-day window.
   - If a user synced a huge SharePoint library (>100,000 files) causing silent sync lag (`SYNC_LIBRARY_LIMIT`), switch from full **Sync** to **Add shortcut to OneDrive** on needed subfolders (`[m365-005]`).

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- SharePoint site URL, exact missing filename/folder path, whether found in 1st/2nd-stage Recycle Bin, Activity feed `Deleted By` user, and last-seen date/time.

## Deep-Dive Investigation (L3)
1. **Retention Hold / Preservation Hold Library:** If 93 days already passed AND the tenant enforces a M365 Purview Retention Policy for SharePoint, a Site Collection Admin can retrieve deleted versions from the hidden **`PreservationHoldLibrary`** (`/_layouts/15/viewlsts.aspx`).
2. **Renamed Teams Standard Channel Trap:** Renaming a channel in Teams does NOT automatically rename the underlying SharePoint folder until manually verified — files often still sit under the **old channel folder name** in SharePoint!

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Check where the restored files will land (`Original Location`) before restoring hundreds of items so you don't accidentally overwrite newer edited files (`m365-003`)!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Recycle Bin Restore)** In SharePoint / OneDrive **Recycle Bin** (1st or 2nd stage), select the confirmed deleted folder/files (`SP_FILE_DELETED`), verify they don't reflect intentional cleanup, and click **Restore** -> confirm they return to their **Original Location** cleanly.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Mass Accidental Deletion / Sync Rollback)** If thousands of files were dragged/deleted or corrupted in the last 30 days on **OneDrive** (or a **SharePoint Document Library**), use **OneDrive Settings -> Restore your OneDrive** (or SharePoint Library **Gear -> Restore this library**) to pick an exact pre-incident timestamp with SharePoint Site Admin & manager approval!
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Local Sync Missing Only)** If files exist safely on SharePoint Web yet miss locally, verify OneDrive sync (`[m365-005]`) and teach the user **NEVER** to delete synced folders locally to "free space" — use **Right-click -> Free up space** (Files On-Demand) or **Stop sync** safely in OneDrive Settings instead!

## Verification & Post-Fix Checks
1. Verify restored files/folders appear intact inside **SharePoint Web (`Open in SharePoint`)** and open cleanly without corruption.
2. Verify `jsmith@example.com` sees the restored items synced on `PC-LAB-01` (green checkmark / cloud icon).

## Cross-Subject Escalation & Pivot Links
- **Files exist in SharePoint Web yet OneDrive Desktop is stuck processing or over 300k limit:** [m365-005 — OneDrive Sync Stuck Processing Changes and SharePoint Path Limit Errors](./m365-005-onedrive-sync-stuck-and-sharepoint-path-limit.md)
- **File wasn't deleted, yet recent edits were overwritten (Version History rollback):** [m365-003 — Lost Modifications on a Word or Excel Document Recovery](./m365-003-word-excel-lost-modifications-recovery.md)
- **Restored workbook opens Read-Only or remains locked for co-authoring:** [m365-002 — Shared Excel Workbook Cannot Be Modified, Read-Only, or Locked for Editing](./m365-002-excel-shared-workbook-locked-readonly.md)


## Useful Links & External Tools
- **[Microsoft 365 Admin Center](https://admin.microsoft.com/)** — Verify SharePoint/OneDrive admin permissions and user storage status.
- **[Microsoft 365 Service Health Status](https://status.cloud.microsoft/)** — Check SharePoint Online and Teams file service status.
## Client Update Snippets (EN / FR)
- **EN:** We located the missing SharePoint / Teams files in the cloud Recycle Bin / library activity log and safely restored them back to their original folder. Could you refresh SharePoint or your synced OneDrive folder and confirm all expected documents are back?
- **FR:** Nous avons retrouvé les fichiers SharePoint / Teams manquants dans la corbeille infonuagique / journal d'activité et les avons restaurés à leur emplacement d'origine. Pouvez-vous actualiser SharePoint ou votre dossier OneDrive synchronisé et confirmer que vos documents sont bien revenus ?
