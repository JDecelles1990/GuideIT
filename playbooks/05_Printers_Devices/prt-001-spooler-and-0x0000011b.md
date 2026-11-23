---
id: prt-001
domain: 05_Printers_Devices
subject: "Printers & Peripherals"
subcategory: printers_spooler_scan
title: Print Spooler Stuck, Offline Printer, and RPC Print Error 0x0000011b
tier: L1
keywords_en:
  - won't print
  - offline printer
  - spooler crash
  - print queue stuck
  - network printer error
keywords_fr:
  - bloqué en file
  - bloque en file
  - imprimante hors ligne
  - n'imprime pas
  - spouleur bloqué
  - erreur impression
error_codes:
  - "0x0000011b"
  - "0x00000709"
  - "0x00000bcb"
tags:
  - print_spooler
  - rpc_print_auth
os:
  - windows
environment:
  - local_endpoint
  - on_prem_ad
  - hybrid_ad
tools:
  - PowerShell
  - Print Management
  - Event Viewer
  - Test-NetConnection
risk_level: low
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - srv-012
  - win-001
  - net-004
linked_scripts:
  - 04_Devices/Get-PrintQueues.ps1
  - 04_Devices/Reset-PrintSpooler.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Can **nobody in the office** print to `PRT-FIN-01` (`10.0.10.50`), or does it fail **only from your PC (`PC-LAB-01`)**?
2. Does the printer show **`Offline`**, stay **stuck `"Printing / Deleting"` in the print queue**, or pop up an error code (`0x0000011b` / `0x00000709`)?
3. Look at the physical printer screen right now: is it powered on, connected to Wi-Fi/Ethernet, and free of **paper jams, open doors, or empty toner/paper trays**?
4. Did this start right after a **Windows Update** or switching Wi-Fi/VPN?

### Initial Scope & Classification
- Verify physical readiness and printer web UI (`http://10.0.10.50`) first, then distinguish local `PC-LAB-01` **Print Spooler / WSD port hang** from **Print Server `0x0000011b` RPC error**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Physical Printer & Queue Check (`Control Panel -> Devices and Printers`):**
   - Verify the printer IP web page opens in Edge/Chrome (`http://10.0.10.50`) and shows `Ready` (no paper jam/empty tray!). If user's PC is on VPN (`[net-006]`), confirm whether local office printers are blocked when full-tunnel VPN is on!
   - Double-click the printer -> **See what's printing**: check if one giant stuck PDF at the top of the queue is blocking every job behind it, and check **Printer -> Use Printer Offline** isn't accidentally checked!
   - Check **`services.msc`** for **`Print Spooler`** status (`Running`?).
2. **Check Port Type (`Printer properties -> Ports`):** Does the checked port start with **`WSD-...`** (notorious for going `"Offline"` randomly!) vs **`Standard TCP/IP Port` (`10.0.10.50`)** or shared **`\\print01\...`**?

### L2 Technical Diagnostics
1. Check Print Spooler service state, installed printers, port type (`WSD` vs `Standard TCP/IP`), and stuck jobs (read-only):
   ```powershell
   Get-Service -Name Spooler | Select-Object Name, Status, StartType
   Get-Printer | Select-Object Name, PortName, DriverName, PrinterStatus, WorkOffline
   Get-PrinterPort | Select-Object Name, Description, PrinterHostAddress
   Get-PrintJob -PrinterName "*" -ErrorAction SilentlyContinue | Select-Object PrinterName, Id, JobStatus, DocumentName, UserName
   ```
2. Verify TCP reachability to the printer on raw JetDirect port `9100` (read-only):
   ```powershell
   Test-NetConnection -ComputerName 10.0.10.50 -Port 9100 | Select-Object ComputerName, TcpTestSucceeded
   ```
3. Check PrintService Operational logs for spooler or RPC authentication failures (`0x0000011b` / `0x00000709`):
   ```powershell
   Get-WinEvent -LogName "Microsoft-Windows-PrintService/Operational" -MaxEvents 10 -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, LevelDisplayName, Message
   ```

## Deep-Dive Investigation (L3)
1. **Error `0x0000011b` / `0x00000709` (RPC Privacy Level Hardening):** After Windows security updates (CVE-2021-1678 / PrintNightmare hardening), Windows enforces `RpcAuthnLevelPrivacyEnabled` on print servers and RPC over Named Pipes vs TCP (`RpcUseNamedPipeProtocol`). Inspect `HKLM:\SYSTEM\CurrentControlSet\Control\Print` on both print server and client.
2. **WSD Port Instability:** WSD ports rely on dynamic multicast discovery and frequently drop to `"Offline"` across VLANs or sleep states; prefer Standard TCP/IP Port (`Raw` `9100`) with SNMP status enabled or disabled cleanly depending on firewall rules.
3. **Driver Crashes (`0x00000bcb` / Spooler crash):** Check `Event ID 1000` in `Application` log for `spoolsv.exe` faulting module names (third-party Type 3 driver DLLs vs Microsoft Type 4 / Universal Print driver).

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Clear stuck spooler queue files on `PC-LAB-01` (or print server with approval during low usage) and restart `Spooler`:
   ```powershell
   Stop-Service -Name Spooler -Force
   Remove-Item -Path "$env:SystemRoot\System32\spool\PRINTERS\*" -Force
   Start-Service -Name Spooler
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Replace unstable `WSD` port with a `Standard TCP/IP Port` (`10.0.10.50`, port `9100`), or disable SNMP Status Enabled in Port Properties if ICMP/SNMP is blocked across subnets.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For `0x0000011b` on legacy print servers while planning driver/OS upgrades, verify approved GPO/security policy before touching `RpcAuthnLevelPrivacyEnabled` (`HKLM:\SYSTEM\CurrentControlSet\Control\Print`). Prefer deploying signed Type 4 / Universal drivers via Print Management or Intune over weakening RPC security defaults.

## Verification & Post-Fix Checks
1. Confirm `Get-Service Spooler` shows `Running` and `Get-Printer` shows `PrinterStatus = Normal`, `WorkOffline = False`.
2. Print a Windows **Test Page** and verify the job enters and clears the queue within seconds.

## Cross-Subject Escalation & Pivot Links
- **Printer shows Offline because WSD port, printer hostname DNS, or static IP changed:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Printer lost DHCP lease or print server resolution fails during Windows DHCP/DNS outage:** [srv-012 — Windows Server DHCP Scope Exhausted, DNS AD Load Failure, and Kerberos Time Skew](../08_Servers_Cloud_Infra/srv-012-windows-dhcp-exhausted-dns-forwarder-and-ntp-skew.md)
- **Windows PrintNightmare cumulative KB triggered RPC error 0x0000011b on shared queues:** [win-001 — Windows Update Failure and Component Store Corruption](../03_Windows_Endpoints/win-001-windows-update-corruption.md)
- **Print server SMB queue (\\print01) blocked over VPN (0x80070035) or Error 1219:** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)

## Client Update Snippets (EN / FR)
- **EN:** We cleared the stuck print spooler queue and verified connectivity to `PRT-FIN-01`. Please try printing your document again and confirm it prints properly.
- **FR:** Nous avons vidé la file d'attente bloquée du spouleur d'impression et vérifié la connexion vers `PRT-FIN-01`. Pouvez-vous relancer votre impression et nous confirmer que tout fonctionne ?
