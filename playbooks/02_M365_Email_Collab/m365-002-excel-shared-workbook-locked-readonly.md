---
id: m365-002
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: docs_onedrive_teams
title: Shared Excel Workbook Cannot Be Modified, Read-Only, or Locked for Editing
tier: L1
keywords_en:
  - can't modify shared excel
  - excel locked for editing
  - excel read only
  - sharepoint checkout
  - file in use by another user
keywords_fr:
  - impossible modifier excel partage
  - excel lecture seule
  - fichier verrouille par un autre utilisateur
  - extraction obligatoire sharepoint
  - excel verrouillé en écriture
error_codes:
  - READ_ONLY
  - LOCKED_FOR_EDITING
tags:
  - excel_shared_locked
  - file_readonly
os:
  - windows
  - macos
environment:
  - m365
  - local_endpoint
  - on_prem_ad
tools:
  - Microsoft Excel
  - SharePoint Online
  - PowerShell
  - OneDrive
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - m365-005
  - m365-003
  - net-004
  - sec-004
---

## Fast Triage (Under 2 Minutes)
- Where does the workbook live: **SharePoint / OneDrive / Teams**, or a **Windows SMB network share** (`\\SRV-FILE-01\Share`)?
- What is the file extension: modern **`.xlsx` / `.xlsm` / `.xlsb`** (supports M365 co-authoring) or legacy **`.xls` / `.csv`** (single-writer file lock only)?
- Does the yellow Excel banner say **`READ-ONLY`**, **`CHECKED OUT`**, **`PROTECTED VIEW`**, or **`File is locked for editing by <user>`**?

## Read-Only Diagnostics (L1-L2)
1. **If hosted in SharePoint / OneDrive / Teams:**
   - Test opening the same file in **Excel for the Web** (`Edit in Browser`) to separate client-side Office lock/auth issues from SharePoint permissions.
   - Verify the user (`jsmith@example.com`) holds **Edit / Contribute** permission rather than **Read** (Visitors group).
   - Check the SharePoint document library **Versioning Settings** for **`Require Check Out = Yes`** (which blocks simultaneous co-authoring and forces read-only until checked out).
   - Check whether the file has unsupported co-authoring features (legacy **Share Workbook** mode, strict workbook encryption password, or **IRM / Sensitivity Label** restricting `Edit` rights).
2. **If hosted on an on-prem Windows File Server (`SRV-FILE-01`):**
   - Query active SMB locks and hidden `~$*.xlsx` lock owner files without modifying data (read-only, run on file server):
     ```powershell
     Get-SmbOpenFile | Where-Object { $_.Path -like "*.xls*" } |
         Select-Object FileId, ClientUserName, ClientComputerName, Path | Format-Table -AutoSize
     ```
3. **Check local Office Protected View / Trust Center / Read-Only file attribute on `PC-LAB-01`:**
   ```powershell
   Get-ItemProperty -Path "C:\Path\To\SharedWorkbook.xlsx" -ErrorAction SilentlyContinue |
       Select-Object FullName, IsReadOnly, Attributes
   ```

## Deep-Dive Investigation (L3)
1. **Stuck OneDrive / SharePoint Co-Authoring Lock (10-minute ghost lock):** When Excel crashes on one user's workstation, SharePoint/OneDrive holds a short-lived edit lock or local `OfficeFileCache` token conflict until expired or until OneDrive sync resumes (`[m365-005]`).
2. **File Explorer Preview Pane Locking SMB Files:** On Windows SMB shares, enabling the File Explorer **Preview Pane** (`Alt+P`) can acquire a read/share lock on selected Excel files, causing `"Locked for editing"` even when nobody opened Excel!
3. **Legacy Shared Workbook Feature Conflict:** Under Excel **Review -> Unshare Workbook**, legacy `.xls`/Shared Workbooks disable M365 co-authoring and frequently corrupt locks across mapped drives.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** On SharePoint/OneDrive:
   - Convert legacy **`.xls`** files via **File -> Save As -> `.xlsx`** and disable legacy **Share Workbook** so M365 Co-Authoring works natively.
   - If **`Require Check Out`** is enabled unintentionally on a collaborative library, click **Check Out** to edit (and **Check In** when done), or ask the SharePoint Site Owner to disable **Require documents to be checked out before they can be edited**.
   - Confirm `jsmith@example.com` is in a SharePoint group with **Edit** rights and **AutoSave** is enabled.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **Protected View** or **Mark as Final** triggers read-only, verify file origin is trusted and click **Enable Editing** / **Edit Anyway**.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** On an SMB File Server (`SRV-FILE-01`), ONLY after confirming the holding user closed Excel (to avoid corrupting active saves!), close the orphaned SMB open file handle:
   ```powershell
   Close-SmbOpenFile -FileId <FileIdFromGetSmbOpenFile> -Force
   ```
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If Excel local cache is stuck on `PC-LAB-01`, close all Office apps and verify OneDrive sync is signed in and healthy (`[m365-005]`).

## Verification & Post-Fix Checks
1. Have `jsmith@example.com` open the workbook, edit a test cell, and verify the status shows **Saved** (or AutoSave **On** without `READ-ONLY` banner).
2. Confirm a second authorized teammate can open and co-author the `.xlsx` file simultaneously without lock errors.

## Cross-Subject Escalation & Pivot Links
- **OneDrive sync engine paused, conflicted copy queued, or SharePoint path limit blocks AutoSave:** [m365-005 — OneDrive Sync Stuck Processing Changes and SharePoint Path Limit Errors](./m365-005-onedrive-sync-stuck-and-sharepoint-path-limit.md)
- **Co-authoring lock conflict created forked edits or requires Version History rollback:** [m365-003 — Lost Modifications on a Word or Excel Document Recovery](./m365-003-word-excel-lost-modifications-recovery.md)
- **Excel file lives on an on-prem UNC/SMB mapped share (opportunistic lock) rather than SharePoint:** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)
- **Purview Sensitivity Label / IRM protection restricts workbook to Read-Only:** [sec-004 — Microsoft Purview DLP Policy Blocks & Sensitivity Label Encryption Denied](../06_Security_Access/sec-004-purview-dlp-block-and-sensitivity-labels.md)

## Client Update Snippets (EN / FR)
- **EN:** We cleared the file editing lock and verified permissions on the shared Excel workbook. Could you reopen the file and confirm you can edit and save changes normally?
- **FR:** Nous avons levé le verrou d'édition et vérifié les droits d'accès sur le fichier Excel partagé. Pouvez-vous rouvrir le classeur et confirmer que vous pouvez maintenant le modifier et enregistrer vos changements ?
