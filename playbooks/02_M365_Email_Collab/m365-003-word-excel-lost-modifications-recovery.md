---
id: m365-003
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: docs_onedrive_teams
title: Lost Modifications on a Word or Excel Document Recovery
tier: L1
keywords_en:
  - lost modifications word
  - lost changes excel
  - unsaved word document
  - document reverted
  - recover previous version
keywords_fr:
  - modifications perdues word
  - modifications perdues excel
  - document non enregistre
  - recuperer version anterieure
  - fichier excel revenu en arriere
error_codes:
  - AUTOSAVE_OFF
  - SYNC_CONFLICT
tags:
  - lost_document_edits
  - office_autorecover
os:
  - windows
  - macos
environment:
  - m365
  - local_endpoint
tools:
  - Microsoft Word
  - Microsoft Excel
  - SharePoint Online
  - OneDrive
  - PowerShell
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - m365-005
  - m365-002
  - app-002
  - m365-007
---

## Fast Triage (Under 2 Minutes)
- **Stop overwriting immediately:** Ask `jsmith@example.com` NOT to repeatedly save or close/reopen the file while inspecting recovery locations.
- Where was the document stored: **OneDrive / SharePoint**, **local disk (`C:\`)**, **Windows SMB file server**, or opened directly from an **Outlook email attachment** (which saves edits to a hidden `INetCache\Content.Outlook` temp folder!)?
- Did Office crash, did **AutoSave** toggle off, or did another user overwrite edits concurrently?

## Read-Only Diagnostics (L1-L2)
1. **Check Cloud Version History first (OneDrive / SharePoint / Teams):**
   - Open the file in the browser or **File -> Info -> Version History** in Word/Excel. Inspect timestamped versions across the last 24–48 hours — minor/auto-saved versions often hold the missing edits!
   - Also check OneDrive **Recycle Bin** and **Second-stage recycle bin** if a sync conflict copy was deleted.
2. **Search local Office AutoRecover, UnsavedFiles, and Outlook Attachment temp folders on `PC-LAB-01` (read-only):**
   ```powershell
   $paths = @(
       "$env:APPDATA\Microsoft\Word",
       "$env:APPDATA\Microsoft\Excel",
       "$env:LOCALAPPDATA\Microsoft\Office\UnsavedFiles",
       "$env:LOCALAPPDATA\Microsoft\Windows\INetCache\Content.Outlook"
   )
   Get-ChildItem -Path $paths -Recurse -File -ErrorAction SilentlyContinue |
       Where-Object { $_.LastWriteTime -gt (Get-Date).AddDays(-7) } |
       Sort-Object LastWriteTime -Descending |
       Select-Object LastWriteTime, Length, FullName | Format-Table -AutoSize
   ```
   *(Look for `.asd`, `.wbk`, `.tmp`, `.xar`, or `Unsaved` copies.)*
3. **On macOS**, inspect Office AutoRecovery directories (read-only):
   ```bash
   ls -lt ~/Library/Containers/com.microsoft.Word/Data/Library/Preferences/AutoRecovery/ ~/Library/Containers/com.microsoft.Excel/Data/Library/Application\ Support/Microsoft/ 2>/dev/null
   ```
4. **If on a Windows SMB File Server**, right-click the parent folder -> **Properties -> Previous Versions** to see if Volume Shadow Copies captured an hourly snapshot before the overwrite.

## Deep-Dive Investigation (L3)
1. **OneDrive Sync Conflict / Forked Copy (`SYNC_CONFLICT`):** Check OneDrive activity center and the local folder for files suffixed with `-PC-LAB-01` or `"Copy"` created when two users or offline sessions diverged.
2. **Office Document Cache (`Upload Center` / `OfficeFileCache`):** Inspect **File -> Open -> Recover Unsaved Documents / Workbooks** or look in `$env:LOCALAPPDATA\Microsoft\Office\16.0\OfficeFileCache` (do not delete cache before extracting recoverable copies!).
3. **Why AutoSave Was Off (`AUTOSAVE_OFF`):** Local paths outside synced OneDrive/SharePoint libraries, legacy `.doc`/`.xls` formats, or Group Policy `DisableAutoSave` keep AutoSave disabled; verify **File -> Options -> Save -> Save AutoRecover information every N minutes** is set (e.g., 5–10 minutes).

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Always copy any recovered `.asd`, `.wbk`, `.tmp`, or Version History file to a **new timestamped copy** (e.g., `Document_RECOVERED_2026-11-22.docx`) before merging edits or restoring a previous cloud version over the live file.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** In OneDrive/SharePoint **Version History**, use **Download** to inspect the target revision first, or click **Restore** once confirmed it contains the lost work (SharePoint preserves the overwritten version as a prior history entry).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** To prevent recurrence: advise `jsmith@example.com` to always save Outlook attachments to OneDrive/SharePoint before editing, keep files in modern `.docx`/`.xlsx` format, and ensure OneDrive sync is green (`[m365-005]`).

## Verification & Post-Fix Checks
1. Have `jsmith@example.com` open the recovered copy and verify the missing sections/formulas are intact.
2. Confirm **AutoSave** shows **On** (for cloud files) or AutoRecover is active under **File -> Options -> Save** (`Save AutoRecover` checked).

## Cross-Subject Escalation & Pivot Links
- **Edits stayed local because OneDrive sync stalled or hit SharePoint path length limits:** [m365-005 — OneDrive Sync Stuck Processing Changes and SharePoint Path Limit Errors](./m365-005-onedrive-sync-stuck-and-sharepoint-path-limit.md)
- **Concurrent lock conflict left workbook read-only or split into a duplicate file:** [m365-002 — Shared Excel Workbook Cannot Be Modified, Read-Only, or Locked for Editing](./m365-002-excel-shared-workbook-locked-readonly.md)
- **COM add-in freeze crashed Word/Excel before AutoRecover flushed:** [app-002 — Excel/Word Freezing on Open, COM Add-in Conflict, and PDF Previewer Failure](../09_Apps_LOB/app-002-office-addins-crash-and-pdf-preview-failure.md)
- **External B2B guest collaborator lost Teams/SharePoint co-authoring access mid-session:** [m365-007 — Microsoft Teams External Federation & B2B Guest Access Blocked](./m365-007-teams-external-guest-access-and-federation.md)

## Client Update Snippets (EN / FR)
- **EN:** We located a prior version / AutoRecover copy of your document containing the missing changes and saved a safe recovered copy so nothing else is overwritten. Could you review the file and confirm your edits are back?
- **FR:** Nous avons retrouvé une version antérieure / copie de récupération automatique contenant vos modifications perdues et créé une copie sécurisée afin de ne rien écraser. Pouvez-vous vérifier le fichier et confirmer que vos changements sont bien présents ?
