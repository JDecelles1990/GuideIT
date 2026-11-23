---
id: app-006
domain: 09_Apps_LOB
subject: "Applications & LOB"
subcategory: accounting_lob_runtimes
title: Accounting & LOB Multi-User Errors (QuickBooks H202, Sage 50 Connection Manager, Acomba)
tier: L2
keywords_en:
  - quickbooks error h202 multi user mode
  - quickbooks database server manager not running
  - sage 50 connection manager cannot open company
  - acomba multi user file lock error
  - accounting software multi user mode blocked
keywords_fr:
  - quickbooks erreur h202 mode multi utilisateur
  - sage 50 gestionnaire connexion bloque
  - acomba erreur partage multi poste
  - logiciel comptable mode multi utilisateur bloque
  - gestionnaire base de donnees quickbooks
error_codes:
  - H202
  - H505
  - "-6000"
  - SAGE50_CONN_MGR
  - ACOMBA_FILE_LOCK
tags:
  - quickbooks_h202_multiuser
  - sage50_connection_manager
  - acomba_lob_multiuser
os:
  - windows
environment:
  - hybrid_ad
  - on_prem_ad
  - network
  - local_endpoint
tools:
  - PowerShell
  - QuickBooks Database Server Manager / Tool Hub
  - Sage 50 Database Connection Manager
  - Windows Firewall / SMB Management
risk_level: medium
requires_admin: true
last_verified: 2026-11-23
related_ids:
  - net-004
  - srv-017
  - sec-006
  - net-001
  - app-007
linked_scripts:
  - 01_System/Get-RuntimesAndMSIHealth.ps1
  - 07_Servers_Infra/Get-ServerAutoServices.ps1
  - 07_Servers_Infra/Get-FirewallAndListeningPorts.ps1
  - 07_Servers_Infra/Get-SMBSharesAndSessions.ps1
  - 02_Network/Test-PortConnectivity.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. **Which accounting / LOB application is failing?** (**QuickBooks Desktop** `H202`/`H505`/`-6000`, **Sage 50 Canada** `Connection Manager cannot connect`, **Acomba** multi-user lock/BTRIEVE, or another SQL/shared-folder LOB app)?
2. Does **Single-User Mode** open cleanly on the server (or for a single user), and does the error ONLY appear when switching to **Multi-User Mode (`H202`)**?
3. Are **ALL accounting workstations** getting the error (`Server service / Firewall / SMB lock problem`), OR **ONLY ONE workstation** (`VPN, Wi-Fi vs Ethernet, mapped drive red X, or workstation mistakenly set to "Host Multi-User Access"!`)?
4. Did Windows Update / Antivirus / Server reboot happen overnight before multi-user broke this morning?

### Initial Scope & Classification
- **QuickBooks `H202` / `H505`:** Workstation cannot reach **QuickBooks Database Server Manager (`QuickBooksDBXX` + `QBCFMonitorService`)** on the company-file server (`SRV-ACCT01`), OR another user workstation accidentally turned ON **`File -> Utilities -> Host Multi-User Access`** (`H505`)!
- **Sage 50 Canada (`Unable to open company file / Connection Manager`):** **Sage 50 Database Connection Manager (`MySQL` / `Sage 50 DB`)** stopped on the file server, Windows Firewall blocked TCP **`13540–13541`**, OR mapped drive SMB session dropped (`[net-004]`).
- **Acomba Multi-User / File Locks (`Acomba` / shared DB):** Stale file locks (`OpenSMBFile`) left after a workstation crashed, UNC/mapped drive access denied (`[srv-017]`), OR aggressive real-time AV scanning locking `.DAT`/`.FD`/`.QBW`/`.SAJ` transaction files simultaneously.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Server Host Isolation & Workstation Mapped Drive)
1. **Verify Mapped Drive & Network Access (`PC-LAB-01` -> `\\SRV-ACCT01\Accounting`):**
   - Open File Explorer -> confirm the mapped share (`e.g., Q:\` or `S:\`) does NOT have a red X (`[net-004]`) and that `jsmith@example.com` can read/write a small test file inside the shared accounting folder!
   - **Rule for VPN Users:** QuickBooks Desktop and Sage 50 over slow home VPNs frequently drop multi-user packets or lock files on disconnect — verify stable low-latency LAN/RDS/AVD session usage where required.
2. **QuickBooks Desktop `H505` Workstation Check (`Host Multi-User Access` Must Be OFF on Workstations!):**
   - On affected workstations, open QuickBooks (**without** opening the company file yet) -> check **`File -> Utilities`**: if it says **`Stop Hosting Multi-User Access`**, someone turned hosting ON on a client PC! ONLY the **Server** hosting the `.QBW` file should ever host!
3. **Check Accounting Services on Host Server (`SRV-ACCT01`) Read-Only:** Check `services.msc` for `QuickBooksDBXX` (e.g., `QuickBooksDB32`/`33`/`34`), `QBCFMonitorService`, `Sage 50 Database Connection Manager`, or `Acomba` services.

### L2 Technical Diagnostics
1. **Audit Accounting Services, Firewall Listening Ports (QuickBooks `8019` / Sage `13540`), and Open SMB File Locks on Server & Workstation (read-only):**
   ```powershell
   # Run on the Accounting File Server (SRV-ACCT01): check QuickBooks/Sage/Acomba services
   Get-Service | Where-Object {
       $_.Name -match 'QuickBooks|QBCF|Sage|Simply|Acomba|MSSQL'
   } | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize

   # Check listening TCP ports for QuickBooks (8019, 55378+) and Sage 50 (13540-13541)
   Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
       Where-Object { $_.LocalPort -in @(8019, 13540, 13541, 1433) -or $_.LocalPort -ge 55378 -and $_.LocalPort -le 55390 } |
       Select-Object LocalAddress, LocalPort, OwningProcess

   # Check open SMB file locks holding .QBW, .ND, .SAJ, or Acomba files (requires Server Admin)
   Get-SmbOpenFile -ErrorAction SilentlyContinue |
       Where-Object { $_.Path -match '\.(qbw|nd|tlg|sai|saj|fd|dat)$' } |
       Select-Object FileId, ClientComputerName, ClientUserName, Path

   # Run from Workstation PC-LAB-01: verify DNS & TCP connectivity to QuickBooks/Sage DB ports on server
   Test-NetConnection -ComputerName "SRV-ACCT01" -Port 8019
   Test-NetConnection -ComputerName "SRV-ACCT01" -Port 13540
   ```
   *(Run `01_System/Get-RuntimesAndMSIHealth.ps1`, `07_Servers_Infra/Get-ServerAutoServices.ps1`, `07_Servers_Infra/Get-FirewallAndListeningPorts.ps1`, `07_Servers_Infra/Get-SMBSharesAndSessions.ps1`, and `02_Network/Test-PortConnectivity.ps1` directly from PowerShellStore!)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact app & year/edition (QuickBooks 2024, Sage 50 2025, Acomba), exact error code (`H202`/`H505`/`-6000`), server name (`SRV-ACCT01`), single vs all workstations impacted, open SMB file lock output, and `Get-ServerAutoServices.ps1` + `Test-PortConnectivity.ps1` results.

## Deep-Dive Investigation (L3)
1. **QuickBooks `.ND` Network Descriptor & DNS Resolution Mismatch:** QuickBooks writes a `.qbw.nd` config file beside the `.QBW` file containing the `ServerIp` and `ServerPort`. If the server's DHCP IP changed or `.ND` lists a stale IP / wrong year's `QuickBooksDBXX` port, every workstation throws `H202` until the folder is re-scanned in **QuickBooks Database Server Manager**.
2. **Windows Firewall Switched to `Public` Profile or Missing Inbound Rules (`[sec-006]`):** If `SRV-ACCT01` restarted and Network Location Awareness detected `Public` firewall profile, inbound TCP `8019` / `55378–55382` (QuickBooks) or `13540–13541` (Sage 50) drops silently!
3. **Antivirus Real-Time Lock & SMB Opportunistic Locking (`Acomba` / `QuickBooks` / `Sage 50`):** Concurrent writes over SMB with missing Defender exclusions on shared `.QBW`/`.SAJ`/Acomba data directories cause sporadic multi-user disconnects and `-6000` / database lock errors. Always follow vendor-documented scoped folder exclusions rather than disabling AV!

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER delete `.QBW`, `.TLG`, `.SAJ`, or Acomba data files, and NEVER close open SMB file handles (`Close-SmbOpenFile`) without confirming the user on that session has saved/closed their accounting client — force-closing active writes can corrupt company databases! Always take a verified snapshot/copy of the company folder before deep repair!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Turn Off Accidental Hosting on Client Workstations & Verify Share Access)**
   - On any client PC (`PC-LAB-01`) showing `Stop Hosting Multi-User Access` under **`File -> Utilities`**, click **`Stop Hosting Multi-User Access`** so only `SRV-ACCT01` acts as host.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2 Restart Accounting Database Service & Rescan `.ND` on Server `SRV-ACCT01`)**
   ```powershell
   # Confirm exact service name first (example: QuickBooksDB34 / QBCFMonitorService / Sage 50 Database Connection Manager)
   Restart-Service -Name "QBCFMonitorService" -Force -ErrorAction Stop
   # For Sage 50:
   # Restart-Service -Name "Sage 50 Database Connection Manager" -Force -ErrorAction Stop
   ```
   - **QuickBooks `H202`:** On `SRV-ACCT01`, open **QuickBooks Database Server Manager** (or **QuickBooks Tool Hub -> Network Issues**) -> **Scan Folders** -> add the exact company file folder -> **Start Scan** to regenerate clean `.ND` port/IP bindings.
   - **Stale Crashed SMB Lock (`Acomba` / `Sage 50` / `QuickBooks`):** Verify the disconnected workstation actually closed the app -> if a dead SMB session still locks `.SAJ`/`.ND`/Acomba files on `SRV-ACCT01`, close ONLY that confirmed stale file handle (`Close-SmbOpenFile -FileId <ID>`).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Allow Accounting Ports in Windows Firewall `Domain/Private` Profile)**
   - Ensure inbound TCP rules exist ONLY on `Domain, Private` profiles (see `[sec-006]`) for `QuickBooksDBXX` (`8019` + year dynamic port range) or `Sage 50 Connection Manager` (`13540–13541`), and verify the Windows `hosts` file isn't pointing `SRV-ACCT01` to an old retired IP (`02_Network/Get-WebProxyAndTLSDiagnostics.ps1`).

## Verification & Post-Fix Checks
1. Re-run `07_Servers_Infra/Get-ServerAutoServices.ps1` and `07_Servers_Infra/Get-FirewallAndListeningPorts.ps1` on `SRV-ACCT01` verifying the accounting DB service is **Running** and listening cleanly, and verify `02_Network/Test-PortConnectivity.ps1` returns `TcpTestSucceeded = True` from `PC-LAB-01`.
2. Have **two users simultaneously** open the company file on `PC-LAB-01` and a second workstation in **Multi-User Mode** and verify zero `H202` / Connection Manager / lock errors.

## Cross-Subject Escalation & Pivot Links
- **Mapped network drive `Q:\` / `S:\` shows Red X or `0x80070035`:** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)
- **File server folder NTFS vs Share permissions blocking writes:** [srv-017 — Windows File Server Shared Folder Access Denied (NTFS vs Share Permissions & File Locks)](../08_Servers_Cloud_Infra/srv-017-windows-file-server-shared-folder-access-denied-and-locks.md)
- **Windows Firewall blocking QuickBooks/Sage inbound port on `SRV-ACCT01`:** [sec-006 — Windows Defender Firewall Blocking App, Inbound Port, or Listening Port Conflict](../06_Security_Access/sec-006-windows-firewall-blocked-app-and-listening-port-conflict.md)
- **Workstation DNS or VPN failing to resolve `SRV-ACCT01`:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Accounting app install/update failing due to missing VC++ / .NET runtime or MSI 1603:** [app-007 — Missing .NET/Java/VC++ Runtime, MSI Error 1603, and Winget/Store Install Failures](./app-007-missing-dotnet-java-vcpp-runtime-and-msi-installer-error-1603.md)

## Useful Links & External Tools
- **[Intuit QuickBooks Desktop Support & Tool Hub](https://quickbooks.intuit.com/learn-support/)** — Official QuickBooks Database Server Manager setup, `H202`/`H505` port tables by release year, and QuickBooks Tool Hub download.
- **[Microsoft Visual C++ Redistributable Downloads](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)** — Official x86/x64 runtime installers often required by accounting & PDF desktop clients.

## Client Update Snippets (EN / FR)
- **EN:** We restored multi-user accounting database connectivity on the host server (verifying the database connection service, firewall port rules, and clearing any stale file locks). Could two users please test opening the company file in Multi-User Mode and confirm everything works cleanly?
- **FR:** Nous avons rétabli l'accès multi-utilisateur au logiciel comptable sur le serveur hôte (vérification du service de connexion, des règles de pare-feu et des verrous de fichiers). Pouvez-vous tester l'ouverture en mode multi-utilisateur sur deux postes et nous confirmer que tout fonctionne normalement ?
