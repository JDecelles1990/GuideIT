---
id: prt-006
domain: 05_Printers_Devices
subject: "Printers & Peripherals"
subcategory: printer_setup_scanners
title: MFP Scanner Scan-to-Folder (SMB) Failure, NTLMv2 Auth Errors, and WIA/TWAIN Scanner Not Found
tier: L2
keywords_en:
  - scan to folder smb failed
  - copier scanner not sending to shared folder
  - scanner not found wia twain windows
  - windows update broke scan to folder
  - mfp smb v1 v2 scan error
keywords_fr:
  - numerisation vers dossier smb echouee
  - scan vers dossier partage ne fonctionne plus
  - scanner non detecte wia windows
  - photocopieur erreur smb scan
  - service acquisition image windows arrete
error_codes:
  - SMB_AUTH_FAILED
  - SMB1_DISABLED
  - WIA_SERVICE_STOPPED
  - STATUS_LOGON_FAILURE
  - "0x80070035"
tags:
  - scan_to_smb_failed
  - scanner_wia_twain
  - mfp_smb_ntlmv2
os:
  - windows
  - cross_platform
environment:
  - network
  - on_prem_ad
  - local_endpoint
tools:
  - PowerShell
  - Printer / Copier Web UI
  - Windows Services (stisvc)
  - Event Viewer (Security / SMBServer)
risk_level: medium
requires_admin: true
last_verified: 2026-11-23
related_ids:
  - prt-004
  - prt-001
  - net-004
  - srv-017
  - id-001
linked_scripts:
  - 04_Devices/Get-PrinterPortsAndScannerHealth.ps1
  - 07_Servers_Infra/Get-SMBSharesAndSessions.ps1
  - 07_Servers_Infra/Get-FirewallAndListeningPorts.ps1
  - 02_Network/Test-PortConnectivity.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is the user using **Scan-to-Folder (SMB from a shared office copier/MFP)** OR a **local USB / Wi-Fi desktop scanner** (`Windows Scan` / `Adobe Acrobat` / `WIA` / `TWAIN` app)?
2. For **Scan-to-Folder (SMB):** Does it fail for **ALL users**, or ONLY for `jsmith@example.com`'s workstation/folder (`10.0.10.25`) — and did **`PC-LAB-01`'s IP address, Windows username/password, or Windows 11 update (24H2 SMB signing!)** just change?
3. What exact error code shows on the copier screen or job log (`Logon Failure`, `SMB Connection Error`, `Destination Path Not Found`, `Check Network`)?
4. Can users still **print** to the MFP AND browse the scan destination `\\PC-LAB-01\Scans` (or `\\FILE01\Scans`) from another PC?

### Initial Scope & Classification
- **Scan-to-Folder worked yesterday, fails today for one workstation:** Usually DHCP changed `PC-LAB-01`'s IP (`10.0.10.25`), the user changed their Windows/AD password (and the copier's address book still holds the old password — watch for AD lockout `[id-001]`!), or Windows Firewall switched network profile from **Private/Domain** to **Public** blocking TCP `445`.
- **Fails across ALL PCs after Windows Server / Windows 11 upgrade:** Server hardened **SMBv1 off** (older copiers firmware-locked to SMB1), enabled **Require SMB Signing (`RequireSecuritySignature = 1`)** or **NTLM disabled / Credential Guard**, or `LmCompatibilityLevel = 5` blocked older MFP firmware.
- **USB / Local WIA/TWAIN scanner disappears or hangs:** Windows Image Acquisition service (`stisvc`) stopped, USB sleep/hub power (`[prt-005]`), or missing vendor TWAIN/WIA 64-bit driver.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Copier Web UI & Service Status)
1. **Log into the Copier/MFP Web Admin UI (`http://10.0.10.50`) Read-Only:**
   - Open **Address Book / Scan Destinations** -> record the exact **Hostname/IP**, **Port (`445`)**, **Share Path (`\Scans`)**, **Protocol (`SMB v2/v3` vs `SMB v1`)**, and **Scan Service Account (`domain.local\scanner` or `svc_scan`)**!
   - **CRITICAL CHECK:** Verify the copier is NOT hammering AD/local accounts with a stale password and locking out the account (`[id-001]`).
2. **Verify Destination PC / Server Network Profile & Static IP:** Confirm the Windows Firewall network profile on the scan destination host (`PC-LAB-01` or `SRV-FILE01`) is **Domain** or **Private** (never **Public**, which blocks File & Printer Sharing TCP `445`!).
3. **For Local USB Scanners:** Open `services.msc` -> check **`Windows Image Acquisition (WIA)` (`stisvc`)** is **Running / Automatic** and test in Windows **Fax and Scan** (`wfs.exe`) or **Windows Scan** app.

### L2 Technical Diagnostics
1. **Inspect Scanner Services, SMB Server Config, Firewall TCP 445, and Share Permissions on Destination Host (read-only):**
   ```powershell
   # Check WIA scanner service and Spooler status
   Get-Service -Name stisvc, Spooler, FDResPub, fdPHost -ErrorAction SilentlyContinue |
       Select-Object Name, DisplayName, Status, StartType

   # Inspect Windows SMB server config (SMB1/SMB2/Signing) and NTLM level
   Get-SmbServerConfiguration |
       Select-Object EnableSMB1Protocol, EnableSMB2Protocol, RequireSecuritySignature, EncryptData
   Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -Name LmCompatibilityLevel -ErrorAction SilentlyContinue

   # Verify SMB share & NTFS permissions on the target scan folder (replace path cleanly)
   Get-SmbShare -Name "Scans" -ErrorAction SilentlyContinue | Get-SmbShareAccess
   Get-NetFirewallProfile | Select-Object Name, Enabled
   ```
   *(Run the linked `04_Devices/Get-PrinterPortsAndScannerHealth.ps1`, `07_Servers_Infra/Get-SMBSharesAndSessions.ps1`, and `07_Servers_Infra/Get-FirewallAndListeningPorts.ps1` scripts directly from PowerShellStore.)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Printer/MFP make & model, copier SMB log error text, configured SMB version (`v1` vs `v2/v3`), destination host (`PC-LAB-01` vs file server), Firewall profile + TCP `445` test result, and `Get-PrinterPortsAndScannerHealth.ps1` output.

## Deep-Dive Investigation (L3)
1. **Windows 11 24H2+ / Server SMB Signing & NTLMv1 Security Hardening:** Windows 11 24H2+ enables **SMB Signing Required** and disables **Insecure Guest Logons** by default. Older Ricoh/Konica/Xerox/Brother MFPs with unpatched firmware often fail `STATUS_LOGON_FAILURE` or SMB negotiation unless copier firmware is updated to **SMBv2/SMBv3 with AES/SHA-256 signing** OR scans are temporarily routed to a dedicated hardened scan-relay server / **Scan-to-Email (`prt-004`)**.
2. **Security Event ID `4625` & `SMBServer` Logs:** Query `Microsoft-Windows-SMBServer/Security` (`Event Viewer -> Applications and Services Logs`) and `Security` Event ID `4625` (`SubStatus 0xC000006A` wrong password, `0xC000006D` unknown username, `0xC0000234` account locked out). Notice that Workgroup PCs require `LOCALHOST\scanuser` or just `scanuser` (not stale Microsoft Entra ID email login!).
3. **Hostname vs Static IP Resolution (`DNS / NetBIOS`):** Copiers configured with hostname `PC-LAB-01` instead of FQDN (`PC-LAB-01.domain.local`) or DHCP reservation fail after router/DNS changes (`0x80070035`).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER globally re-enable SMBv1 across client servers or weaken domain-wide NTLM policy for a single old copier — update MFP firmware to SMBv2/SMBv3, fix the dedicated scan service account, or pivot temporarily to Scan-to-Email (`prt-004`).

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 USB/WIA Scanner Quick Fix)**
   ```powershell
   # Restart Windows Image Acquisition (stisvc) and Shell Hardware Detection
   Restart-Service -Name stisvc -Force -ErrorAction Stop
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Fix Scan-to-SMB Credentials, Dedicated Service Account & Firewall Profile)**
   - Create a dedicated local/AD non-interactive **Scan Service Account** (`svc_scan`, non-admin!) with **Change/Modify** permission ONLY on the `\\SRV-FILE01\Scans` Share + NTFS folder (never put a human user's personal password inside the copier!).
   - Assign a **DHCP Reservation** to `PC-LAB-01` (if scanning directly to a workstation) and update the MFP Address Book with the exact IP/FQDN, `SMB v2/v3` enabled, and the new `svc_scan` password.
   - Ensure the Windows Firewall **File and Printer Sharing (SMB-In)** rule is enabled on the **Domain/Private** profile (never expose TCP `445` on Public Wi-Fi!).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L3 MFP Firmware / SMB Signing Alignment)**
   - Upgrade copier firmware from vendor portal so **SMBv2 / SMBv3 + SMB Signing** are natively supported, OR configure **Scan-to-Email (`[prt-004]`)** / **SharePoint/OneDrive Scan Connector** if the legacy MFP hardware cannot support SMBv2/v3.

## Verification & Post-Fix Checks
1. Re-run `04_Devices/Get-PrinterPortsAndScannerHealth.ps1` and verify `stisvc` is **Running**, SMB2/3 is enabled, and TCP `445` is listening on the target host.
2. Perform a live test scan at the copier / local scanner and confirm the PDF lands cleanly inside the destination folder (`\\SRV-FILE01\Scans` or `C:\Scans`) within 5–10 seconds without generating `4625` Security failures.

## Cross-Subject Escalation & Pivot Links
- **Using or falling back to Scan-to-Email SMTP instead of Scan-to-Folder:** [prt-004 — Printer Scan-to-Email SMTP Relay Failure (535 5.7.139 / 550 5.7.64)](./prt-004-scan-to-email-smtp-relay-failure.md)
- **Printer is also offline or Print Spooler is stuck:** [prt-001 — Print Spooler Stuck, Offline Printer, and RPC Print Error 0x0000011b](./prt-001-spooler-and-0x0000011b.md)
- **Workstation cannot browse SMB shares (`0x80070035`):** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)
- **NTFS vs Share permissions blocking folder writes on File Server:** [srv-017 — Windows File Server Shared Folder Access Denied (NTFS vs Share Permissions & File Locks)](../08_Servers_Cloud_Infra/srv-017-windows-file-server-shared-folder-access-denied-and-locks.md)
- **Copier kept retrying an expired password and locked out an account:** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)

## Useful Links & External Tools
- **[Microsoft 365 Portal (Apps & Sign-In)](https://portal.office.com/)** — Verify OneDrive/SharePoint access when configuring cloud scan-to-email/SharePoint libraries as a modern alternative to SMBv1.
- **[Windows Release Health & Known Issues](https://learn.microsoft.com/en-us/windows/release-health/)** — Check recent Windows 11 24H2/server cumulative update SMB signing or WIA scanner regressions.

## Client Update Snippets (EN / FR)
- **EN:** We repaired the scanner configuration (`Scan-to-Folder SMB` / Windows WIA service) and verified destination folder permissions and credentials. Could you please send a 1-page test scan and confirm the PDF arrives cleanly in your Scans folder?
- **FR:** Nous avons corrigé la configuration de numérisation (`Scan-to-Folder SMB` ou service d'acquisition d'images WIA) ainsi que les accès/identifiants du dossier de destination. Pouvez-vous numériser une page test et confirmer que le PDF arrive bien dans votre dossier ?
