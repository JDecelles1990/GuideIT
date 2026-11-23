---
id: sec-005
domain: 06_Security_Access
subject: "Security & Access"
subcategory: bec_defender_threats
title: User Cannot Install Approved Software, UAC Admin Prompt, and Local Admin Audit
tier: L1
keywords_en:
  - uac admin prompt software install
  - user cannot install program
  - needs administrator approval windows
  - msi installer error 1603
  - audit local administrators windows
keywords_fr:
  - demande mot de passe administrateur uac
  - utilisateur ne peut pas installer logiciel
  - permission admin requise installation
  - erreur installation msi 1603
  - verifier administrateurs locaux windows
error_codes:
  - UAC_ELEVATION_REQUIRED
  - "1603"
  - ERROR_ELEVATION_REQUIRED
tags:
  - software_install_uac
  - local_admin_audit
os:
  - windows
environment:
  - local_endpoint
  - intune
  - hybrid_ad
  - entra_id
tools:
  - Company Portal / Winget
  - PowerShell
  - Windows LAPS / Entra LAPS
  - Microsoft Intune
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - sec-002
  - mdm-001
  - app-003
linked_scripts:
  - 05_Security_Defender/Get-LocalAdministrators.ps1
  - 05_Security_Defender/Get-DefenderStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. **What exact software** are you trying to install or update (app name, vendor, and where you downloaded it from)?
2. Are you trying to **install a new program**, or is an **already-installed work app (`Adobe`, `Chrome`, accounting tool)** popping up a **UAC Administrator password box (`UAC_ELEVATION_REQUIRED`)** just to run/auto-update?
3. Is this software **pre-approved for your company** (check **Company Portal / Software Center** first!), or a newly requested tool needing manager approval?
4. **Security Rule:** Never type your MSP Domain/Global Admin password blindly into a UAC prompt until verifying the publisher signature & hash!

### Initial Scope & Classification
- Standard corporate users rightly **do not** have permanent Local Administrator rights (least-privilege security!). L1 handles these requests cleanly via **Company Portal / Intune self-service**, **verified per-user installers**, **scoped RMM / LAPS elevation**, or flagging unapproved downloads (`[sec-002]`).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Check Intune Company Portal / Software Center FIRST:** Ask `jsmith@example.com` to open the Windows **Company Portal** app — approved apps (Adobe, Zoom, 7-Zip, Chrome, Office add-ins) install with **1 click without any UAC admin prompt**!
2. **Verify Vendor & Publisher Signature BEFORE Touching UAC:** On `PC-LAB-01`, check the installer URL / file properties (`Right-click installer -> Properties -> Digital Signatures`)! Look out for fake Google search ad installers ("malvertising") mimicking legitimate software!
3. **Audit Who Already Has Local Admin (`Get-LocalAdministrators`):** Run `psstore://05_Security_Defender/Get-LocalAdministrators.ps1` to verify unauthorized accounts weren't left inside `Administrators`.

### L2 Technical Diagnostics
1. **Inspect Signer Authenticode, SHA-256 Hash, and Local Administrators Group (read-only):**
   ```powershell
   Get-LocalGroupMember -Group "Administrators" | Select-Object Name, ObjectClass, PrincipalSource
   Get-AuthenticodeSignature -FilePath "C:\Path\To\ApprovedInstaller.exe" | Select-Object Status, SignerCertificate
   Get-FileHash -Path "C:\Path\To\ApprovedInstaller.exe" -Algorithm SHA256
   ```
2. **Diagnose Installer Failure (`1603` Fatal Error during Installation):**
   - Check `%TEMP%\*msi*.log` (or rerun with `/L*V C:\Windows\Temp\install.log`): **`1603`** usually means **pending Windows reboot (`[win-001]`)**, **older version locked open by running app**, **C: drive low space (`[win-011]`)**, or **Defender ASR (`[sec-002]`)** blocking a temp child script!

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact requested app name/version, download URL / signed vendor name, ticket/manager approval status, and installer `.log` snippet if `1603` failed.

## Deep-Dive Investigation (L3)
1. **Standard User App Requires Elevation Daily (Shims / ProgramData ACLs / EPM):** Instead of making `jsmith@example.com` a Local Administrator (high ransomware risk!), inspect with ProcMon why the LOB app triggers UAC — often it writes to `C:\Program Files\<App>` or `HKLM` and can be fixed cleanly with **scoped folder ACL**, **Intune Endpoint Privilege Management (EPM)** rule, or an elevated scheduled auto-updater.
2. **Missing/Expired LAPS or Break-Glass Account:** Verify **Windows LAPS (Entra ID / AD)** rotated cleanly and zero plaintext static passwords are shared directly with end users!

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER grant permanent **Local Administrator** membership to an end user unless formally approved in writing by the client's security lead + MSP policy! NEVER enter shared admin credentials while leaving a user's screen unattended (`shift+click -> cmd` privilege escalation risk!).

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Approved Self-Service / Safe User-Scope Install)** Direct user to install from **Company Portal**, or confirm written approval + verified digital signature (`Status = Valid`), close conflicting open apps (`1603`), and install silently via RMM / elevated session (`msiexec /i <Approved.msi> /qn /norestart`).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Scoped Temporary Elevation via Windows LAPS or Intune Deployment)** Package recurring requests as an **Intune Win32 / Winget** app in Company Portal, OR use single-session audited elevation (Intune EPM / RMM SYSTEM / audited **Windows LAPS** password that auto-rotates immediately after use!).

## Verification & Post-Fix Checks
1. Confirm the approved software launches cleanly under the standard non-admin user session (`jsmith@example.com`) with zero UAC popups.
2. Re-run `Get-LocalGroupMember -Group "Administrators"` to verify `jsmith@example.com` was NOT added as a permanent Local Admin.

## Cross-Subject Escalation & Pivot Links
- **Approved installer launches then gets quarantined by Defender / ASR rules:** [sec-002 — Microsoft Defender ASR Rule or Antivirus Blocking Legitimate LOB App or Macro](./sec-002-defender-asr-block-and-false-positive.md)
- **Company Portal cannot load or push approved apps because Intune sync failed:** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](../07_macOS_Mobile_MDM/mdm-001-intune-compliance-sync.md)
- **Adobe Acrobat / Creative Cloud installer or updater triggers repeat UAC loops:** [app-003 — Adobe Acrobat and Creative Cloud Licensing Errors, Sign-In Loops, and Repair](../09_Apps_LOB/app-003-adobe-acrobat-creative-cloud-licensing-and-repair.md)

## Client Update Snippets (EN / FR)
- **EN:** We verified the publisher signature and approval status for the requested software on `PC-LAB-01`, completed the elevated installation securely (or enabled it in Company Portal) while preserving standard least-privilege security. Could you open the application and confirm everything launches properly?
- **FR:** Nous avons vérifié la signature numérique et l'approbation du logiciel demandé sur `PC-LAB-01`, puis effectué l'installation sécurisée tout en préservant les droits utilisateurs standards. Pouvez-vous ouvrir l'application et confirmer qu'elle fonctionne normalement ?
