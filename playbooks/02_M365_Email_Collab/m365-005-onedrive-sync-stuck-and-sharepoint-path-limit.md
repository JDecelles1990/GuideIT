---
id: m365-005
domain: 02_M365_Email_Collab
subject: "Microsoft 365 / Email & Collaboration"
subcategory: docs_onedrive_teams
title: OneDrive Sync Stuck Processing Changes and SharePoint Path Limit Errors
tier: L2
keywords_en:
  - onedrive stuck processing changes
  - onedrive red x
  - onedrive not syncing
  - sharepoint path too long
  - sync pending forever
keywords_fr:
  - onedrive bloque
  - synchronisation onedrive echouee
  - chemin trop long sharepoint
  - onedrive croix rouge
  - fichiers en attente de synchronisation
error_codes:
  - "0x8004de40"
  - "0x8007016a"
  - "0x8004def7"
tags:
  - onedrive_sync_stuck
  - sharepoint_path_limit
os:
  - windows
  - macos
environment:
  - m365
  - local_endpoint
tools:
  - OneDrive
  - PowerShell
  - SharePoint Online
  - Terminal
risk_level: medium
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - net-001
  - m365-002
  - m365-003
  - mdm-007
linked_scripts:
  - 03_M365/Reset-OneDriveSync.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Look at the blue **OneDrive cloud icon** near the clock: is it **gray/crossed out (`Not signed in` / `Paused`)**, showing a **red `X`**, or spinning forever on **`Processing X changes`**?
2. Click the cloud icon: does **View sync problems** list a specific file/folder (e.g., invalid character `# % * : < > ? / \ |`, `.pst` file, `"Path too long"`, or `"File is open in another app"`)?
3. Did you recently click **Sync** on a massive company **SharePoint Teams library** (`100,000+` files) or run low on `C:` drive space (`[win-011]`)?

### Initial Scope & Classification
- Microsoft's practical sync ceiling is **300,000 items** across all synced libraries! Note SharePoint Web (`Open in SharePoint`) always provides immediate access even while local sync catches up.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Inspect OneDrive Tray Icon (`Click Cloud -> View sync problems / Pause / Settings`):**
   - Check if OneDrive was accidentally **Paused** (`Resume syncing`) or signed out (`Sign in` -> `0x8004de40`).
   - Check **OneDrive -> View sync problems**: if 1 specific `.tmp`, `.pst`, or weird filename (`Report?.xlsx`) is jamming the whole queue, renaming/closing that file unblocks everything!
   - Open **OneDrive Settings -> Account** to check how many huge SharePoint libraries are synced locally and whether M365 storage quota (`0x8004def7`) is full!
2. **Verify Local Disk Free Space:** Check `This PC` -> ensure `C:` isn't full (if `C:` is full -> `[win-011]`).

### L2 Technical Diagnostics
1. **Check OneDrive client status, local sync root item counts, and long paths on `PC-LAB-01` (read-only):**
   ```powershell
   Get-Process OneDrive -ErrorAction SilentlyContinue | Select-Object ProcessName, Id, StartTime
   $odRoot = $env:OneDriveCommercial
   if ($odRoot -and (Test-Path $odRoot)) {
       $items = Get-ChildItem -Path $odRoot -Recurse -Force -ErrorAction SilentlyContinue
       [PSCustomObject]@{
           SyncRoot       = $odRoot
           TotalItems     = $items.Count
           LongPathsOver250 = ($items | Where-Object { $_.FullName.Length -gt 250 }).Count
       }
   }
   ```
2. **Check Windows Cloud Files (`cldflt`) service and `0x8007016a` (Cloud file provider is not running) state (read-only):**
   ```powershell
   Get-Service cldflt -ErrorAction SilentlyContinue | Select-Object Name, Status, StartType
   ```
3. **Check OneDrive Logs & Quota:**
   - Open **OneDrive Settings -> Account** to check synced SharePoint libraries and storage bar (`0x8004def7` = OneDrive quota full or account unlicensed).
   - Inspect `$env:LOCALAPPDATA\Microsoft\OneDrive\logs\Business1` for repeating sync error codes.

## Deep-Dive Investigation (L3)
1. **Library Sync Bloat (>300,000 files):** Users who clicked **Sync** on the top-level SharePoint document library instead of **Add shortcut to OneDrive** (or syncing only needed subfolders) starve the OneDrive sync engine CPU/SQLite metadata database.
2. **Blocked File Extensions / `.pst` / Open Locks:** Local Outlook `.pst` files, `.tmp` database locks, or files open exclusively in LOB apps stall the queue indefinitely.
3. **TLS / Proxy / Modern Auth Failure (`0x8004de40`):** Confirm TLS 1.2 is enabled and check `[m365-001]` if OneDrive cannot acquire an Entra token via WAM (`Microsoft.AAD.BrokerPlugin`).

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Resolve invalid filenames, shorten deeply nested SharePoint folder paths (< 400 characters decoded URL), or pause sync before relocating `.pst` files outside OneDrive.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If OneDrive sync metadata is wedged on Windows (does **not** delete cloud or local synced files, though it re-scans all libraries), run a clean **OneDrive Reset**:
   ```cmd
   "%LOCALAPPDATA%\Microsoft\OneDrive\OneDrive.exe" /reset
   ```
   *(Wait 2 minutes; if OneDrive does not relaunch automatically, start `"%LOCALAPPDATA%\Microsoft\OneDrive\OneDrive.exe"` manually.)*
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** On macOS, run `/Applications/OneDrive.app/Contents/Resources/ResetOneDriveApp.command` (or `ResetOneDriveAppStandalone.command` for standalone builds) and re-select synced folders.
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If total synced items exceed ~200,000–300,000, click **Stop sync** on massive SharePoint libraries in **OneDrive Settings -> Account** (verify no unsynced local changes first!) and transition the user to **Add shortcut to OneDrive** on targeted folders or SharePoint Web.

## Verification & Post-Fix Checks
1. Confirm the OneDrive tray/menu bar icon turns clean **Up to date** (no red X or stuck pending counter).
2. Create a small test file inside OneDrive on `PC-LAB-01` and verify it appears in OneDrive Web within 30 seconds.

## Cross-Subject Escalation & Pivot Links
- **DNS, proxy TLS inspection, or VPN blocks OneDrive cloud sync (0x8004de40):** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Stalled OneDrive sync keeps shared Excel workbooks locked or read-only:** [m365-002 — Shared Excel Workbook Cannot Be Modified, Read-Only, or Locked for Editing](./m365-002-excel-shared-workbook-locked-readonly.md)
- **Local sync backlog risks lost Word/Excel modifications requiring Version History recovery:** [m365-003 — Lost Modifications on a Word or Excel Document Recovery](./m365-003-word-excel-lost-modifications-recovery.md)
- **macOS Finder SMB share or OneDrive FileProvider cache desyncs on Mac:** [mdm-007 — Beginner macOS Finder SMB Network Share, DNS Flush, and Office Mac Licensing](../07_macOS_Mobile_MDM/mdm-007-macos-finder-smb-share-and-office-licensing.md)


## Useful Links & External Tools
- **[Microsoft 365 Service Health Status](https://status.cloud.microsoft/)** — Rule out tenant or global SharePoint/OneDrive outages before resetting local sync.
- **[Microsoft 365 Network Connectivity Test](https://connectivity.office.com/)** — Measure SharePoint/OneDrive endpoint latency and proxy/VPN bottlenecks from the user's PC.
- **[Microsoft 365 Admin Center](https://admin.microsoft.com/)** — Check user OneDrive storage quota and active license assignment.
## Client Update Snippets (EN / FR)
- **EN:** We cleared the stalled OneDrive sync queue on `PC-LAB-01` and addressed the conflicting file paths / library size issue. OneDrive now reports **Up to date** — please verify your latest files are syncing normally.
- **FR:** Nous avons réinitialisé la file de synchronisation OneDrive bloquée sur `PC-LAB-01` et corrigé les chemins de fichiers problématiques. OneDrive affiche maintenant **À jour** ; veuillez vérifier que vos derniers fichiers se synchronisent bien.
