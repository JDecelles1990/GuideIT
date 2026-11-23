---
id: m365-009
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: email_exchange_mailflow
title: Outlook Search Not Returning Results, Indexing Broken, or OST File Corrupted
tier: L1
keywords_en:
  - outlook search not working
  - outlook search no results
  - something went wrong search outlook
  - rebuild outlook search index
  - ost file corrupt outlook
keywords_fr:
  - recherche outlook ne fonctionne pas
  - outlook aucun resultat recherche
  - reindexer recherche outlook
  - fichier ost corrompu outlook
  - erreur recherche courriel outlook
error_codes:
  - "0x80040119"
  - WSEARCH_STOPPED
  - OST_CORRUPT
tags:
  - outlook_search_broken
  - outlook_ost_index
os:
  - windows
environment:
  - m365
  - local_endpoint
tools:
  - Microsoft Outlook
  - Windows Indexing Options
  - PowerShell
  - Services (WSearch)
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - m365-001
  - m365-008
  - app-002
linked_scripts:
  - 03_M365/Clear-OutlookCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Does Outlook return **zero results**, show **`Something went wrong and your search couldn't be completed`**, or only miss **older emails** (> 1 year old)?
2. Does searching inside **Outlook on the Web (`https://outlook.office.com`)** find the missing emails normally? *(Confirming Web works gives the user an instant workaround AND isolates the fault to `PC-LAB-01`!)*
3. Are you searching inside your **primary mailbox**, an **Online Archive**, or a **Shared Mailbox**?
4. Are you using **Classic Outlook (`OUTLOOK.EXE`)** or the **New Outlook for Windows (`olk.exe`)**?

### Initial Scope & Classification
- Distinguish **Windows Cached Exchange Mode Slider limit** (only last 3–12 months downloaded locally; older mail requires clicking *More* / Server Search or using OWA) from **Windows Search (`WSearch`) service stalled** or **corrupted local `.ost` index**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Verify Outlook Web Search & Mail-to-Keep-Offline Slider:**
   - Test the exact same search term in **Outlook on the Web (`outlook.office.com`)**.
   - In Classic Outlook: **File -> Account Settings -> Account Settings -> double-click account -> `Download email for the past:`** slider (if set to 3 or 6 months, emails older than that aren't in local search unless clicking *"Click here to view more on Microsoft Exchange"*).
2. **Check Indexing Status inside Classic Outlook:**
   - Click inside the Outlook Search bar -> **Search Tools -> Indexing Status**: does it show **`0 items remaining to be indexed`** or thousands stuck forever?
   - Check **Search Tools -> Locations to Search**: verify **Microsoft Outlook** and the target mailbox/archive are checked!
3. **Check Disk Space (`win-011`) & `WSearch` Service:** In `services.msc`, confirm **Windows Search (`WSearch`)** status is `Running` (Automatic Delayed Start) and `C:` drive isn't full (Windows pauses indexing automatically below ~10% free disk space!).

### L2 Technical Diagnostics
1. **Check `WSearch` Service, Outlook `.ost` Sizes, and Search Reg Keys on `PC-LAB-01` (read-only):**
   ```powershell
   Get-Service -Name WSearch | Select-Object Name, Status, StartType
   Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Outlook" -Filter "*.ost" -ErrorAction SilentlyContinue |
       Select-Object Name, @{N='SizeGB';E={[math]::Round($_.Length/1GB,2)}}, LastWriteTime
   Get-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search" -ErrorAction SilentlyContinue |
       Select-Object PreventIndexingOutlook
   ```
   *(If an `.ost` exceeds **40–50 GB**, search indexing and Outlook responsiveness degrade severely -> consider Archive/cleanup `[m365-008]` or disabling "Download shared folders" caching!)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Confirm Outlook Web search result, Classic vs New Outlook, Indexing Status item count, `.ost` file size in GB, and `WSearch` service status.

## Deep-Dive Investigation (L3)
1. **Classic Outlook vs Server-Assisted Search (`DisableServerAssistedSearch`):** In M365 Microsoft 365 Apps, Outlook uses Exchange server search alongside local `WSearch` unless broken by registry override (`DisableServerAssistedSearch = 1`) or corrupt WebView/MAPI auth (`[m365-001]`).
2. **Corrupted Shared Mailbox / `.ost` MAPI Store (`0x80040119`):** Running `SCANPST.EXE` works on `.pst` files; for Exchange/M365 **`.ost`** caches, never repair in-place endlessly — deleting/renaming the `.ost` cleanly rebuilds a fresh local sync copy from Exchange Online (as long as no local-only *"This computer only"* folders exist!).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Before renaming/rebuilding an `.ost` file, verify all folders sync to M365/Exchange Online (check `"Sync Issues"` and confirm no local-only `.pst` / unsent Outbox drafts exist) and close Outlook completely. Re-indexing large mailboxes can take 1–4 hours in the background.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Quick Fix)** Restart **Windows Search (`WSearch`)** cleanly (with local admin if needed) and verify **Microsoft Outlook** is included under **Control Panel -> Indexing Options -> Modify -> Microsoft Outlook**.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Index Rebuild via GUI or PowerShell)** If search index stays stuck at non-zero or misses indexed emails:
   - Open **Control Panel -> Indexing Options -> Advanced -> Rebuild -> OK** (rebuilds `Windows.edb` cleanly without closing email access, takes several hours).
   - If `"Microsoft Outlook"` is missing/unchecked or server search errors (`Something went wrong`), toggle **File -> Account Settings -> Account Settings -> Microsoft Exchange -> More Settings -> Advanced -> Turn on/off Download shared folders**, restart Outlook, or verify `PreventIndexingOutlook` isn't `1`.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Clean `.ost` Rebuild when `0x80040119` or Corrupt Cache)** Close Outlook completely, rename the `.ost` to `.ost.bak` (safe fallback!), and relaunch Outlook to pull a fresh cache from Exchange Online:
   ```powershell
   # Close OUTLOOK.EXE first and verify no "This computer only" local folders exist
   Stop-Process -Name OUTLOOK -Force -ErrorAction SilentlyContinue
   Get-ChildItem "$env:LOCALAPPDATA\Microsoft\Outlook\*.ost" | ForEach-Object {
       Rename-Item -Path $_.FullName -NewName ($_.Name + ".bak")
   }
   ```

## Verification & Post-Fix Checks
1. Confirm **Search Tools -> Indexing Status** counts down smoothly to **`0 items remaining to be indexed`**.
2. Run 2–3 searches in Outlook Desktop (by sender, subject, and attachment keyword) and verify expected recent + historical results appear cleanly.

## Cross-Subject Escalation & Pivot Links
- **Outlook search or sync fails because desktop auth token is broken (0x80040115):** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](./m365-001-outlook-auth-loop.md)
- **Bloated 50 GB+ .ost file requires Exchange Online Archive to slim primary mailbox:** [m365-008 — Exchange Online Mailbox Full (554 5.2.2) & Online Archive Not Moving Mail](./m365-008-exchange-mailbox-full-and-online-archive-stuck.md)
- **Outlook freezes completely while indexing or opening emails due to COM add-in conflict:** [app-002 — Excel/Word Freezing on Open, COM Add-in Conflict, and PDF Previewer Failure](../09_Apps_LOB/app-002-office-addins-crash-and-pdf-preview-failure.md)

## Client Update Snippets (EN / FR)
- **EN:** We restarted the Windows Search indexing service and rebuilt the corrupted Outlook search index / local mail cache on `PC-LAB-01`. Please allow indexing to finish in the background and confirm your Outlook search results appear normally (in the meantime, Outlook Web at `outlook.office.com` remains available).
- **FR:** Nous avons relancé le service d'indexation Windows Search et reconstruit l'index de recherche / cache Outlook sur `PC-LAB-01`. L'indexation complète peut prendre un peu de temps en arrière-plan ; merci de tester une recherche (Outlook Web sur `outlook.office.com` reste fonctionnel entre-temps).
