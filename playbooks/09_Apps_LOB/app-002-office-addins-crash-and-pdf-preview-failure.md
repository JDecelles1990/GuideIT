---
id: app-002
domain: 09_Apps_LOB
subject: "Applications & LOB"
subcategory: office_pdf_adobe
title: Excel/Word Freezing on Open, COM Add-in Conflict, and PDF Previewer Failure
tier: L1
keywords_en:
  - excel freezes on open
  - word not responding
  - pdf preview not working
  - com addin crash
  - outlook pdf preview error
keywords_fr:
  - excel gele a l'ouverture
  - apercu pdf ne fonctionne pas
  - complement office plante
  - word ne repond pas
  - erreur apercu pdf outlook
error_codes:
  - PDF_PREVIEW
  - COM_ADDIN
tags:
  - office_addin_freeze
  - pdf_preview_broken
os:
  - windows
environment:
  - m365
  - local_endpoint
tools:
  - Microsoft Excel
  - Microsoft Word
  - Microsoft Outlook
  - PowerShell
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - m365-003
  - sec-002
  - app-003
  - srv-016
linked_scripts:
  - 03_M365/Get-OutlookAddins.ps1
  - 03_M365/Clear-OutlookCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is **Excel / Word freezing or crashing on launch (`COM_ADDIN`)**, OR is **PDF Attachment Preview in Outlook / File Explorer broken (`PDF_PREVIEW`)**?
2. Does Excel/Word freeze ONLY when opening **one specific workbook** (or does it freeze even on a **new blank document**)?
3. When launching Excel/Word in **Safe Mode (`Win + R -> excel /safe`)**, does it open smoothly right away? *(Safe Mode temporarily skips add-ins in 5 seconds!)*
4. For **PDF Preview**: does double-clicking the PDF open **Adobe Acrobat / Edge** normally (`[app-005]` / `[app-003]`), and is ONLY the inline preview pane broken?

### Initial Scope & Classification
- Isolate **Conflicting COM Add-in** (`excel /safe` passes!), **Offline Default Printer Slowdown**, **Word `Normal.dotm` Corruption**, or **Outlook / Adobe 32-vs-64-bit PDF Previewer mismatch**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Safe Mode & Outlook Attachment Settings GUI)
1. **Run Office Safe Mode (`Win + R -> excel.exe /safe` or `winword.exe /safe`):** Press `Win + R`, type `excel /safe`, press Enter! If it opens fast -> a COM Add-in (Acrobat PDFMaker, ERP/accounting add-in, Teams/CRM plugin) is freezing startup!
2. **Check Windows Default Printer (Surprising Excel Freeze Cause!):** Open **Settings -> Bluetooth & devices -> Printers & scanners**: if the default printer is a disconnected/offline office printer (`[prt-001]`), change Default temporarily to **`Microsoft Print to PDF`** and test opening Excel!
3. **Check Outlook PDF Previewer Setting:** Open **Outlook -> File -> Options -> Trust Center -> Trust Center Settings -> Attachment Handling** -> verify **Turn off Attachment Preview** is unchecked and check **Attachment and Document Previewers**!

### L2 Technical Diagnostics
1. **Inspect Installed Office COM Add-ins & PDF Preview Handler Registrations (read-only):**
   ```powershell
   Get-ChildItem "HKCU:\Software\Microsoft\Office\Excel\Addins", "HKLM:\SOFTWARE\Microsoft\Office\Excel\Addins" -ErrorAction SilentlyContinue |
       ForEach-Object { Get-ItemProperty $_.PSPath } |
       Select-Object PSChildName, FriendlyName, LoadBehavior
   Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\PreviewHandlers" -ErrorAction SilentlyContinue
   ```
3. **Check File Explorer / Outlook PDF Handler Association:**
   - Verify whether **Adobe Acrobat Reader**, **Foxit**, or **Microsoft Edge / PowerToys** owns `.pdf` default association (`Settings -> Apps -> Default apps -> .pdf`), and check **Outlook -> File -> Options -> Trust Center -> Trust Center Settings -> Attachment Handling** (`Turn off Attachment Preview` / `Attachment and Document Previewers`).

## Deep-Dive Investigation (L3)
1. **Offline Network Printer Slowdown in Excel:** Excel queries the default Windows printer on open/Page Layout view; if the default printer is an unreachable offline network printer (`[prt-001]`), Excel hangs for 30–60 seconds on launch!
2. **32-bit vs 64-bit Office vs PDF Previewer Mismatch (`PDF_PREVIEW`):** 64-bit Outlook/Office cannot load legacy 32-bit-only PDF preview handler DLLs (and vice versa); verify Adobe Reader bitness matches Office bitness or use Windows/Edge PDF handler (`Microsoft Edge PDF Preview Handler`).
3. **Corrupted `Normal.dotm` / `Excel15.xlb` Toolbar Cache:** Inspect `$env:APPDATA\Microsoft\Templates\Normal.dotm` and `$env:APPDATA\Microsoft\Excel` timestamps if Word/Excel hangs before reaching the ribbon.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Disable the offending third-party COM Add-in (`COM_ADDIN`) inside Excel/Word: **File -> Options -> Add-ins -> Manage: COM Add-ins -> Go...**, uncheck the suspect add-in, and test normal startup.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **Word** freezes on startup due to a damaged template, close Word and rename `Normal.dotm` cleanly so Word rebuilds a fresh default:
   ```powershell
   Rename-Item -Path "$env:APPDATA\Microsoft\Templates\Normal.dotm" -NewName "Normal.dotm.bak" -ErrorAction SilentlyContinue
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **PDF Preview broken** in Outlook/File Explorer:
   - In **Outlook -> File -> Options -> Trust Center -> Trust Center Settings -> Attachment Handling**, ensure **Turn off Attachment Preview** is unchecked and **PDF Preview Handler** is checked under **Attachment and Document Previewers**.
   - In **Adobe Acrobat Reader -> Edit -> Preferences -> General**, toggle **Enable PDF thumbnail previews in Windows Explorer** or repair the PDF reader installation (matching Office bitness).
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **Microsoft 365 Apps** core binaries are damaged, run **Quick Repair** first (followed by Online Repair if needed) under **Settings -> Apps -> Installed Apps -> Microsoft 365 Apps -> Modify**.

## Verification & Post-Fix Checks
1. Close and relaunch Excel/Word normally (without `/safe`) and confirm instantaneous startup and responsive scrolling.
2. Select a `.pdf` attachment in Outlook and a `.pdf` in File Explorer Preview Pane (`Alt+P`) to verify instant preview rendering.

## Cross-Subject Escalation & Pivot Links
- **Office add-in crash threatens unsaved edits — recover via AutoRecover / Version History:** [m365-003 — Lost Modifications on a Word or Excel Document Recovery](../02_M365_Email_Collab/m365-003-word-excel-lost-modifications-recovery.md)
- **Microsoft Defender ASR rule blocks Excel macro or COM add-in child process:** [sec-002 — Microsoft Defender ASR Rule or Antivirus Blocking Legitimate LOB App or Macro](../06_Security_Access/sec-002-defender-asr-block-and-false-positive.md)
- **Broken Outlook/Explorer PDF preview traces to Adobe Acrobat install or licensing error:** [app-003 — Adobe Acrobat and Creative Cloud Licensing Errors, Sign-In Loops, and Repair](./app-003-adobe-acrobat-creative-cloud-licensing-and-repair.md)
- **Excel/ERP reporting add-in freezes waiting on SQL Server deadlock (1205) or login 18456:** [srv-016 — SQL Server Login Failed (18456), Transaction Log Full (9002) & Deadlocks](../08_Servers_Cloud_Infra/srv-016-sql-server-login-18456-log-full-9002-and-blocking.md)

## Useful Links & External Tools
- **[Adobe Acrobat Cleaner Tool & Enterprise Docs](https://www.adobe.com/devnet-docs/acrobatetk/tools/Labs/cleaner.html)** — Clean up damaged Adobe Reader/Acrobat PDF previewer handlers when Outlook or File Explorer PDF preview fails.
- **[Adobe Admin Console](https://adminconsole.adobe.com/)** — Verify user Acrobat entitlements if repair prompts for licensing (`[app-003]`).

## Client Update Snippets (EN / FR)
- **EN:** We isolated the conflicting Office add-in / PDF preview handler on `PC-LAB-01` and restored normal application behavior. Please reopen Excel/Word or test previewing a PDF attachment and confirm everything works smoothly.
- **FR:** Nous avons isolé le complément Office / gestionnaire d'aperçu PDF problématique sur `PC-LAB-01` et rétabli le fonctionnement normal. Pouvez-vous rouvrir Excel/Word ou tester l'aperçu PDF et confirmer que tout est fluide ?
