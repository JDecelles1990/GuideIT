---
id: srv-017
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: windows_server_sql
title: Windows File Server Shared Folder Access Denied (NTFS vs Share Permissions & File Locks)
tier: L2
keywords_en:
  - shared folder access denied
  - ntfs permissions vs share permissions
  - file in use by another user file server
  - user cannot open network folder
  - smb share access denied 0x80070005
keywords_fr:
  - acces refuse dossier partage serveur
  - permissions ntfs et partage windows server
  - fichier verrouille sur serveur fichiers
  - utilisateur ne peut pas acceder dossier reseau
  - erreur 0x80070005 dossier partage
error_codes:
  - "0x80070005"
  - ERROR_ACCESS_DENIED
  - SMB_FILE_LOCK
tags:
  - file_server_access_denied
  - ntfs_share_permissions
os:
  - windows
environment:
  - on_prem_ad
  - hybrid_ad
tools:
  - Active Directory Users and Computers
  - File Server Computer Management (fsmgmt.msc)
  - PowerShell
  - icacls
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-004
  - id-001
  - m365-002
  - srv-001
linked_scripts:
  - 07_Servers_Infra/Get-SMBSharesAndSessions.ps1
  - 06_AD_Identity/Get-KerberosTicketStatus.ps1
  - 07_Servers_Infra/Get-ServerAutoServices.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Can you **open the shared folder (`\\SRV-FILE-01\Share`) at all** (shows `"Windows cannot access ... Access is denied"` / `0x80070005`), or can you open the folder yet **cannot save/edit one specific file (`File is in use` / `SMB_FILE_LOCK`)**?
2. Were you **just added to a security group** for this folder within the last few hours? *(Windows ONLY refreshes new AD security group tokens on **sign-out / lock-unlock won't update Kerberos ticket** — user MUST log off/reboot or run `klist purge` + reconnect!)*
3. Does the mapped drive have a **red X / Network path not found (`0x80070035`)** (`[net-004]`), or specifically **`Access is denied`**?

### Initial Scope & Classification
- Separate **Missing Group Token Refresh** (user added to AD group yet never logged off/on!), **Share vs NTFS Permissions mismatch** (Remember: Windows applies the **most restrictive** combination of Share Permissions AND NTFS Security Permissions!), and **Stale SMB Open File Handle (`SMB_FILE_LOCK`)** on `SRV-FILE-01`.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Check AD Group Membership & Sign-Out Timing (Saves Most Escalations!):** Open **ADUC -> `jsmith` -> Member Of**.
   - If the user was added to the folder's AD Security Group (`SG-Finance-RW`) earlier today and never logged off Windows (`PC-LAB-01`), their Kerberos token doesn't have that group yet!
2. **Check Who Locked a Specific File (`fsmgmt.msc` GUI on `SRV-FILE-01`):** Open `fsmgmt.msc` -> **Open Files** (shows which `ClientUserName` holds the lock!) or ask if a coworker left the file open in **File Explorer Preview Pane (`Alt+P`)** (`[m365-002]`)!
3. **Rule Out Unreachable Network Path (`[net-004]`):** If the user gets `"Network path not found"` (`0x80070035`) instead of `"Access is denied"`, pivot to `[net-004]`.

### L2 Technical Diagnostics
1. **Check User Group Token & Effective NTFS/Share Permissions on `SRV-FILE-01` (read-only):**
   ```powershell
   # On PC-LAB-01 (as user): inspect active AD security groups in the current Kerberos logon token!
   whoami /groups | findstr /i "Finance HR Accounting SG-"
   ```
   ```powershell
   # On SRV-FILE-01 (read-only): compare Share ACLs vs NTFS ACLs on the target path
   Get-SmbShareAccess -Name "Share" | Format-Table -AutoSize
   icacls "D:\Shares\Finance"
   ```
   *(Best practice: keep Share Permissions = `Authenticated Users: Full Control` or `Change`, and enforce granular access via NTFS Security groups! An explicit **`Deny`** ACE anywhere overrides ALL `Allow` permissions!)*
2. **Inspect Open SMB File Locks (`SRV-FILE-01`, read-only):**
   ```powershell
   Get-SmbOpenFile | Where-Object { $_.Path -like "*TargetFileName*" } |
       Select-Object FileId, ClientUserName, ClientComputerName, Path | Format-Table -AutoSize
   ```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact UNC path (`\\SRV-FILE-01\Share\Subfolder`), affected user (`jsmith@example.com`), exact error (`0x80070005 Access Denied` vs `File Locked`), `whoami /groups` output, and manager/data-owner approval for access change.

## Deep-Dive Investigation (L3)
1. **Broken Inheritance / Folder Moved Inside NTFS Volume:** Moving a folder *within the same NTFS volume* preserves its old restrictive ACLs rather than inheriting the destination folder's permissions (unlike Copy!). Inspect **Security -> Advanced** for disabled inheritance or explicit `Deny` entries.
2. **Access-Based Enumeration (ABE) Hiding Folder Completely:** When ABE is enabled on the SMB share (`Get-SmbShare | Select Name, FolderEnumerationMode`), users without at least `Read` NTFS permissions cannot even see the subfolder exists!

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER grant `Everyone` or `Authenticated Users` Modify access broadly on confidential HR/Finance folders, and NEVER close an active SMB file lock before confirming the holding user closed the application (prevents corrupted `.xlsx`/`.pst` saves!). Obtain data-owner/manager approval before modifying AD group memberships or NTFS ACLs.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Token Refresh)** After confirming `jsmith` is in the approved AD security group: instruct `jsmith@example.com` to save open work, **Sign out** of Windows completely (not just Lock!), and **Sign back in** (while connected to LAN or VPN so Kerberos fetches fresh group SIDs!).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Close Confirmed Orphaned SMB File Lock on `SRV-FILE-01`)** Verify the listed user disconnected/closed the app first, then close ONLY the orphaned handle:
   ```powershell
   Close-SmbOpenFile -FileId <FileIdFromGetSmbOpenFile> -Force
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Scoped AD Group / NTFS Permission Update)** With written folder-owner approval, add `jsmith` to the approved AD security group (`Add-ADGroupMember`) — prefer group-based NTFS ACLs over direct per-user ACLs on folders!

## Verification & Post-Fix Checks
1. Confirm `whoami /groups` on `PC-LAB-01` shows the newly added security group SID.
2. Have `jsmith@example.com` open the target share/subfolder in File Explorer (`\\SRV-FILE-01\Share`), create a small test text file (and delete it if Read/Write), and verify expected permissions work.

## Cross-Subject Escalation & Pivot Links
- **Mapped drive shows red X or 0x80070035 / Error 1219 rather than NTFS Access Denied:** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)
- **Repeated failed SMB auth attempts locked out user account (4740):** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)
- **Shared Excel workbook lock conflict on SMB file server or SharePoint:** [m365-002 — Shared Excel Workbook Cannot Be Modified, Read-Only, or Locked for Editing](../02_M365_Email_Collab/m365-002-excel-shared-workbook-locked-readonly.md)
- **File server disk is 100% full causing access/save failures and VSS backup errors:** [srv-001 — Windows Server Disk Space Exhaustion and VSS Shadow Copy Backup Failure](./srv-001-vss-backup-and-disk-triage.md)


## Useful Links & External Tools
- **[Microsoft Entra Admin Center](https://entra.microsoft.com/)** — Verify hybrid AD group sync if cloud/VPN identity tokens are involved.
## Client Update Snippets (EN / FR)
- **EN:** With folder-owner approval, we verified your security group membership / NTFS share permissions (or cleared the orphaned file lock) on `SRV-FILE-01`. Could you sign out/in once (if newly added to a group) and confirm you can open and save in the shared folder?
- **FR:** Avec l'approbation du responsable du dossier, nous avons vérifié vos accès groupe/NTFS (ou levé le verrou de fichier orphelin) sur `SRV-FILE-01`. Pouvez-vous fermer/rouvrir votre session si un groupe vient d'être ajouté et confirmer l'accès au dossier partagé ?
