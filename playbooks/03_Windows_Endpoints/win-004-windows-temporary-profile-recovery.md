---
id: win-004
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: profiles_audio_av
title: Windows Temporary User Profile Recovery (Event ID 1511 / 1515)
tier: L2
keywords_en:
  - temporary profile
  - desktop icons disappeared
  - we can't sign into your account
  - profile corruption windows
  - missing user files after login
keywords_fr:
  - profil temporaire
  - bureau vide
  - icones disparues
  - impossible de se connecter au compte windows
  - profil utilisateur temporaire
error_codes:
  - "1511"
  - "1515"
tags:
  - temp_profile
  - profile_corruption
os:
  - windows
environment:
  - local_endpoint
  - hybrid_ad
  - on_prem_ad
tools:
  - Registry Editor
  - PowerShell
  - Event Viewer
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-004
  - id-005
  - win-006
---

## Fast Triage (Under 2 Minutes)
- **WARN THE USER IMMEDIATELY:** Tell `jsmith@example.com` **NOT** to save new files onto the Desktop or Documents while logged into the Temporary Profile (`C:\Users\TEMP`), because Windows **deletes temporary profile folders on sign-out**!
- Confirm the banner **`"We can't sign into your account"`** appeared and verify that the user's real profile folder (`C:\Users\jsmith`) is still intact on disk.
- Check whether `C:` is critically low on free disk space or an AV/backup lock prevented loading `NTUSER.DAT`.

## Read-Only Diagnostics (L1-L2)
1. **Verify Profile Folders & `Event ID 1511 / 1515` in Application Log (read-only):**
   ```powershell
   Get-ChildItem "C:\Users" | Select-Object Name, LastWriteTime
   Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1511, 1515; StartTime = (Get-Date).AddDays(-2) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, Message
   ```
2. **Inspect `ProfileList` Registry Keys for `.bak` Suffix (read-only):**
   ```powershell
   Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList" |
       ForEach-Object {
           $p = Get-ItemProperty $_.PSPath
           [PSCustomObject]@{
               Key              = $_.PSChildName
               ProfileImagePath = $p.ProfileImagePath
               State            = $p.State
               RefCount         = $p.RefCount
           }
       } | Format-Table -AutoSize
   ```
   Look for TWO keys for the same SID: one without `.bak` pointing to `C:\Users\TEMP` and one ending in **`.bak`** pointing to `C:\Users\jsmith`!

## Deep-Dive Investigation (L3)
1. **File Lock / `NTUSER.DAT` Corruption:** Check whether `C:\Users\jsmith\NTUSER.DAT` has NTFS permission damage, file-system errors (`chkdsk C: /scan`), or a lingering user registry hive lock caused by an interrupted Windows Update or hung background service holding a file handle during sign-in.
2. **FSLogix / Roaming Profile Conflicts (RDS/AVD):** If this occurs on a multi-session RDS host rather than a physical laptop, inspect FSLogix profile container logs (`C:\ProgramData\FSLogix\Logs`) for VHDX lock conflicts before editing local `ProfileList` keys.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Sign `jsmith@example.com` completely **out** of the Temporary Profile session (save any temporary downloads elsewhere first!), then sign into `PC-LAB-01` using a **separate local/domain administrator account** and **reboot once** to release any hung hive locks.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Export a safety backup of `ProfileList` BEFORE modifying the registry:
   ```cmd
   reg export "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList" C:\Windows\Temp\ProfileList_backup.reg /y
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** In `regedit.exe` under `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList` (ONLY when `.bak` points to the intact `C:\Users\jsmith` and the non-`.bak` key points to `C:\Users\TEMP`):
   - Delete the temporary non-`.bak` SID key pointing to `TEMP`.
   - Rename the `.bak` key by removing `.bak`.
   - Set **`State`** (`DWORD`) = `0` and **`RefCount`** (`DWORD`) = `0` on the restored SID key.
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `NTUSER.DAT` itself is irreparably damaged and the restored profile still falls back to `TEMP`, create a clean new profile (remove the broken SID key + rename `C:\Users\jsmith` to `C:\Users\jsmith.old`), sign in as `jsmith@example.com` to generate a fresh profile, and copy Desktop/Documents/Favorites safely from `C:\Users\jsmith.old`.

## Verification & Post-Fix Checks
1. Sign back in as `jsmith@example.com` on `PC-LAB-01` and confirm `$env:USERPROFILE` resolves to `C:\Users\jsmith` (not `TEMP`).
2. Confirm Desktop icons, Documents, and OneDrive folders appear normally and no new `Event ID 1511 / 1515` entries appear in `Application`.

## Cross-Subject Escalation & Pivot Links
- **Folder Redirection or roaming profile UNC share is unreachable over SMB/VPN:** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)
- **Broken domain secure channel (5722) prevents domain profile SID verification:** [id-005 — Windows Domain Trust Relationship Failed (Event ID 5722 / 3210 / 0xC000018B)](../01_Identity_AD_Entra/id-005-windows-domain-trust-relationship-failed.md)
- **System drive at 100% full prevents NTUSER.DAT registry hive load cleanly:** [win-006 — Windows High CPU, 100% Disk Usage, and Memory Leak Triage (Event 129 / 153 / 2004)](./win-006-windows-high-cpu-100-disk-and-memory-leak.md)

## Client Update Snippets (EN / FR)
- **EN:** We resolved the Windows temporary profile issue on `PC-LAB-01` and restored your normal user profile (`C:\Users\jsmith`). Please sign back in and confirm your Desktop files and settings are intact.
- **FR:** Nous avons corrigé le problème de profil temporaire Windows sur `PC-LAB-01` et rétabli votre profil utilisateur normal. Veuillez ouvrir une nouvelle session et confirmer que votre Bureau et vos documents sont revenus.
