---
id: mdm-008
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: intune_autopilot_mdm
title: Intune New Device Enrollment, Windows Autopilot OOBE, and ESP Failures
tier: L2
keywords_en:
  - enroll new device intune
  - autopilot failed oobe
  - enrollment status page timeout
  - intune mdm enrollment error
  - company portal windows enroll
keywords_fr:
  - enroler nouvel appareil intune
  - echec autopilot oobe
  - erreur inscription intune
  - page etat inscription bloquee
  - enregistrer appareil mdm intune
error_codes:
  - "80180014"
  - "80180005"
  - "80180018"
  - "80070774"
  - "0x8018002b"
  - "0x800705b4"
tags:
  - intune_enrollment
  - autopilot_oobe
os:
  - windows
environment:
  - intune
  - entra_id
  - hybrid_ad
tools:
  - Intune Admin Center
  - Entra Admin Center
  - PowerShell
  - MdmDiagnosticsTool
  - Event Viewer
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - mdm-001
  - win-005
  - net-001
  - id-004
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is this a **brand-new PC at the Windows Setup Welcome / Out-of-Box screen (`Autopilot OOBE`)**, OR an **already set-up PC failing Company Portal / Work or School join**?
2. What exact screen error is shown (`80180014`, `80180005`, `80180018`, `80070774`, `0x800705b4` ESP Timeout), and is the PC running **Windows Home** vs **Pro / Enterprise**? *(Windows Home CANNOT join Entra/Intune!)*
3. Verify the PC is on a clean unrestricted network (**wired Ethernet or stable Wi-Fi** without captive hotel login) and confirm **how many old devices** `jsmith@example.com` already has enrolled!

### Initial Scope & Classification
- **`80180014`:** Device limit reached or Windows Home/MDM disabled; **`80070774`:** Hybrid Autopilot cannot reach DC; **`0x800705b4`:** ESP app timeout.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Entra / Intune Portal Prerequisites)
1. **Verify Prerequisites in Entra ID & Intune Admin Center GUI:**
   - **License:** Confirm `jsmith@example.com` holds **Microsoft Intune Plan 1** (Business Premium / E3 / E5).
   - **MDM Scope:** Open **Entra ID -> Mobility (MDM and WIP) -> Microsoft Intune**: confirm user is in **MDM user scope**!
   - **Device Cap (`80180014`!):** Open **Intune Admin Center -> Users -> `jsmith@example.com` -> Devices**: if 5–15 stale old laptops/phones are sitting enrolled, hitting the enrollment cap blocks any new PC until stale records are removed!
   - **Autopilot Hash:** For new Autopilot laptops, check **Intune -> Devices -> Enrollment -> Windows -> Devices** and verify the laptop Serial Number shows **`Profile status = Assigned`**!

### L2 Technical Diagnostics
1. **On the Windows Endpoint (`Shift+F10` during OOBE or local PowerShell), inspect join & enrollment state (read-only):**
   ```cmd
   dsregcmd /status
   winver
   ```
   ```powershell
   Get-WinEvent -LogName "Microsoft-Windows-DeviceManagement-Enterprise-Diagnostics-Provider/Admin" -MaxEvents 20 -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, LevelDisplayName, Message
   ```
   *(Key Event IDs: `76` = Autopilot profile timeout/failure, `209` = App/ESP install error, `813` / `814` = OMA-DM policy sync result.)*
3. **Export Complete Intune / Autopilot Diagnostic Bundle:**
   ```cmd
   MdmDiagnosticsTool.exe -area Autopilot;TPM -cab C:\Windows\Temp\AutopilotDiag.cab
   ```

## Deep-Dive Investigation (L3)
1. **Enrollment Status Page (ESP) Hangs (`0x800705b4`):** Mixing **LOB `.msi` apps** and **Win32 `.intunewin` apps** during Autopilot ESP frequently deadlocks the Windows Installer mutex! Always package apps as **Win32** during ESP.
2. **Re-Enrolling a Repaired/Swapped Motherboard (`80180018` / Duplicate Hardware Hash):** If a motherboard was replaced under warranty or a device was wiped without deleting the old **Intune + Entra + Autopilot** object, re-capture the hardware hash and remove the orphaned Autopilot/Intune entry before syncing.
3. **TPM Attestation Failure during Pre-Provisioning / Self-Deploying (`0x800705b4` / `80070490`):** Verify BIOS has **TPM 2.0 + Secure Boot** enabled, firmware is updated, and the device can reach `*.manage.microsoft.com`, `enterpriseregistration.windows.net`, and `ztd.dds.microsoft.com`.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** To capture and import a new workstation's **Autopilot Hardware Hash** directly during OOBE (`Shift+F10` -> `powershell`) or existing Windows (requires PowerShell execution approval & `Intune-Administrator` login):
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
   Install-Script -Name Get-WindowsAutopilotInfo -Force
   Get-WindowsAutopilotInfo -Online
   ```
   *(Or export to CSV via `-OutputFile C:\AutopilotHWID.csv` for upload in **Intune -> Enrollment -> Windows -> Devices -> Import**.)*
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If `80180014` is caused by user device limit: delete confirmed decommissioned devices for `jsmith@example.com` in **Intune -> Devices** / **Entra ID -> Devices**, or confirm user is running **Windows Pro / Enterprise / Education** (upgrade Home -> Pro first!).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **existing non-Autopilot Windows Pro devices**, enroll via **Settings -> Accounts -> Access work or school -> Connect -> Join this device to Microsoft Entra ID** (auto-enrolls into Intune when MDM scope is enabled!), or install **Company Portal** for BYOD MAM/MDM enrollment.
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **stuck Autopilot OOBE** after fixing group/ESP assignments: reset cleanly from **Settings -> System -> Recovery -> Reset this PC** (or `systemreset -factoryreset`), then wait 15 minutes after Autopilot profile shows `Assigned` before starting OOBE.

## Verification & Post-Fix Checks
1. Run `dsregcmd /status` and confirm `AzureAdJoined : YES`, `AzureAdPrt : YES`, and `MDMUrl` points to `https://enrollment.manage.microsoft.com/...`.
2. Confirm **Intune Admin Center -> Devices -> All devices** lists the new endpoint as **Managed by: Intune**, **Compliant**, and enrolled under `jsmith@example.com`.

## Cross-Subject Escalation & Pivot Links
- **Enrollment completes yet endpoint stays Non-Compliant blocking Conditional Access:** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](./mdm-001-intune-compliance-sync.md)
- **Newly enrolled Windows 10 device must migrate cleanly to Windows 11 via Intune Feature Updates:** [win-005 — Intune Windows 10 to Windows 11 Migration, Feature Updates, and Safeguard Holds](../03_Windows_Endpoints/win-005-intune-windows-11-migration-and-safeguard-holds.md)
- **Autopilot OOBE / ESP (80072ee7) fails because DNS or proxy blocks Intune/Entra URLs:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Hybrid Entra Join Autopilot hangs on ODJ domain-join connector or GPO retrieval:** [id-004 — Active Directory GPO Not Applying, SYSVOL Permissions, and DFSR Replication Errors](../01_Identity_AD_Entra/id-004-ad-gpo-not-applying-replication-and-dfsr.md)


## Useful Links & External Tools
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Verify Autopilot hardware hash import, ESP profile, and enrollment restrictions.
- **[Microsoft Entra Admin Center](https://entra.microsoft.com/)** — Check MDM user scope and device limit quotas.
- **[M365 Maps (Microsoft Licensing Matrix)](https://m365maps.com/)** — Confirm user holds an Intune-entitled M365 license.
## Client Update Snippets (EN / FR)
- **EN:** We imported the device into Intune / Autopilot, cleared the enrollment restriction, and verified successful MDM provisioning. Please sign in with `jsmith@example.com` and allow 10–15 minutes for company policies and apps to finish syncing.
- **FR:** Nous avons enregistré l'appareil dans Intune / Autopilot, levé l'erreur d'inscription et confirmé le déploiement MDM. Veuillez vous connecter avec `jsmith@example.com` et patienter 10 à 15 minutes pour la synchronisation finale des stratégies et applications.
