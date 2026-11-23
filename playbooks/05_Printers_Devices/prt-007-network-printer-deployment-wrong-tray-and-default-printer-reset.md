---
id: prt-007
domain: 05_Printers_Devices
subject: "Printers & Peripherals"
subcategory: printer_setup_scanners
title: Network Printer Deployment, WSD Port Drops, Default Printer Keeps Changing, and Wrong Paper Tray
tier: L1
keywords_en:
  - add network printer ip address
  - default printer keeps changing windows
  - printer using wrong tray a4 letter
  - wsd printer port keeps going offline
  - install shared network printer driver
keywords_fr:
  - ajouter imprimante reseau adresse ip
  - imprimante par defaut change toute seule windows
  - imprimante prend mauvais bac papier a4 lettre
  - port wsd imprimante hors ligne
  - installer nouvelle imprimante reseau
error_codes:
  - WSD_PORT_OFFLINE
  - LEGACY_DEFAULT_PRINTER
  - A4_LETTER_MISMATCH
  - "0x00000709"
tags:
  - network_printer_setup
  - default_printer_changing
  - printer_wrong_tray_paper
os:
  - windows
  - macos
environment:
  - local_endpoint
  - network
  - hybrid_ad
tools:
  - PowerShell
  - Print Management (printmanagement.msc)
  - Printer Web UI
  - Windows Settings -> Printers
risk_level: low
requires_admin: false
last_verified: 2026-11-23
related_ids:
  - prt-001
  - prt-006
  - net-001
  - id-004
linked_scripts:
  - 04_Devices/Get-PrinterPortsAndScannerHealth.ps1
  - 04_Devices/Get-PrintQueues.ps1
  - 02_Network/Test-PortConnectivity.ps1
  - 04_Devices/Reset-PrintSpooler.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you trying to **install a new network/office printer**, is **Windows switching your default printer (`Let Windows manage my default printer`)** every time you move between home and office (`LEGACY_DEFAULT_PRINTER`), or is the printer **prompting to load A4 / wrong paper tray (`A4_LETTER_MISMATCH`)**?
2. If the printer keeps going **Offline** every couple of days, is it connected via an auto-discovered **WSD port (`WSD-*`)** instead of a **Standard TCP/IP Port (`10.0.10.50`)** (`WSD_PORT_OFFLINE`)?
3. What is the **printer's IP address or asset tag** (`e.g., 10.0.10.50` printed from its Configuration page), and are you on the **office LAN / VPN**?
4. Do you get an administrator prompt or `0x00000709` / `0x0000011b` when setting default or connecting to a `\\PRINT01\Printer` share?

### Initial Scope & Classification
- **Default printer changes on its own (very common laptop call!):** Windows 10/11 enables **"Let Windows manage my default printer"** (`LegacyDefaultPrinterMode = 0`) by default — every time a user prints to `Microsoft Print to PDF` at home, Windows overwrites their default!
- **Printer shows Offline repeatedly after router/printer reboot:** Windows Setup auto-added a **WSD (`Web Services for Devices`)** port instead of a deterministic **Standard TCP/IP Port (RAW 9100 / LPR)** paired with a **DHCP Reservation** on the printer.
- **Wrong paper size (`Load A4 Paper`) or wrong tray:** Windows locale/install defaulted **Printing Preferences** + **Device Settings -> Paper Size** to **A4** instead of **North American Letter (8.5 x 11")**, OR Type 3/Type 4 Universal Driver lacks **Automatic Tray Selection / Cassette Configuration**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Windows Settings GUI)
1. **Check Windows Auto-Default Printer Setting (`Settings -> Bluetooth & devices -> Printers & scanners`):**
   - Scroll down and inspect **`Let Windows manage my default printer`** — if **ON**, Windows overrides the default whenever the user prints elsewhere!
2. **Inspect Installed Printer Port Type (`Printer Properties -> Ports`):**
   - Open **Control Panel -> Devices and Printers -> right-click Printer -> Printer properties -> Ports tab**. Check whether the checkmark is next to a **`WSD-*`** port (problematic!) vs **`10.0.10.50`** **`Standard TCP/IP Port`**.
3. **Check Tray & Paper Size (`Printing Preferences -> Paper/Quality` AND `Printer Properties -> Device Settings`):**
   - Verify BOTH **Printing Defaults** (`Advanced -> Printing Defaults`) AND **Printing Preferences** are set to **Letter (8.5 x 11")** (not `A4`) and **Paper Source** matches **Automatically Select** or the expected tray (`Tray 1` / `Tray 2`), and check `Device Settings -> Form To Tray Assignment`.

### L2 Technical Diagnostics
1. **Audit Printer Ports (WSD vs TCP), Default Printer Registry Mode, Installed Drivers & Reachability on `PC-LAB-01` (read-only):**
   ```powershell
   # Check Windows auto-default printer setting (0 = auto-managed/changes, 1 = locked manual default)
   Get-ItemProperty "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Windows" -Name LegacyDefaultPrinterMode, Device -ErrorAction SilentlyContinue

   # Audit printers, port names/types (flag WSD!), and driver names
   Get-Printer | Select-Object Name, PortName, DriverName, PrinterStatus, Shared | Format-Table -AutoSize
   Get-PrinterPort | Select-Object Name, Description, PrinterHostAddress | Format-Table -AutoSize

   # Test raw print port 9100 reachability to a network printer IP (10.0.10.50)
   Test-NetConnection -ComputerName "10.0.10.50" -Port 9100
   ```
   *(Run the linked `04_Devices/Get-PrinterPortsAndScannerHealth.ps1`, `04_Devices/Get-PrintQueues.ps1`, and `02_Network/Test-PortConnectivity.ps1` scripts directly from PowerShellStore.)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Printer model, static/DHCP-reserved IP (`10.0.10.50`), installed driver name & version (`Get-PrinterDriver`), current port type (`WSD` vs `Standard TCP/IP`), TCP `9100` reachability, and screenshot of tray/paper mismatch.

## Deep-Dive Investigation (L3)
1. **GPO / Intune Point-and-Print Restrictions (`0x0000011b` / `0x00000709`):** If standard users get UAC/error installing from `\\PRINT01\PrinterName` (`id-004` / `prt-001`), inspect PrintNightmare hardening (`RestrictDriverInstallationToAdministrators`) or deploy pre-packaged **vendor Universal Print / Type 4 drivers via Intune Win32** (using `pnputil /add-driver` + `Add-PrinterDriver` + `Add-PrinterPort` + `Add-Printer`).
2. **Duplex Printing / Booklet / Tray Auto-Detect (`Device Settings -> Installable Options`):** Many enterprise copiers (Ricoh, Canon, Xerox, HP) disable optional **Tray 3/4**, **Duplex Unit**, or **Finisher** in Windows until **Bi-Directional Communication** or **Update Now** runs inside `Printer Properties -> Device Settings`.
3. **Default Printer `0x00000709` Error:** Stale permissions or locked value on `HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Windows\Device` prevent setting a default printer until `LegacyDefaultPrinterMode` is set to `1` cleanly.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Installing printer drivers or deleting stuck ports modifies system print configuration. Confirm you are targeting the intended printer IP (`10.0.10.50`) and never remove shared queues on a print server without notifying users.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Lock Manual Default Printer So Windows Never Changes It)**
   ```powershell
   # Set LegacyDefaultPrinterMode = 1 (turns OFF 'Let Windows manage my default printer')
   Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows NT\CurrentVersion\Windows" -Name "LegacyDefaultPrinterMode" -Value 1 -Type DWord
   ```
   - Then open **Settings -> Printers & scanners -> click desired office printer -> Set as default**.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Convert Unreliable WSD Port to Standard TCP/IP Port — Requires Admin if Adding Port/Printer)**
   ```powershell
   # Example: Add deterministic Standard TCP/IP port for 10.0.10.50 and bind existing printer
   # First verify the vendor driver name with Get-PrinterDriver and printer name with Get-Printer
   Add-PrinterPort -Name "IP_10.0.10.50" -PrinterHostAddress "10.0.10.50"
   # Note: uncheck SNMP Status Enabled in Port Settings -> Configure Port if printer ignores SNMP and falsely shows Offline!
   Set-Printer -Name "Office-MFP" -PortName "IP_10.0.10.50"
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Fix Wrong Tray / `Load A4` Prompt Permanently)**
   - Open **`Printer properties -> General -> Preferences`** AND **`Advanced -> Printing Defaults`** -> change default paper size to **Letter (8.5 x 11")** and Tray to **Automatically Select** (or requested Cassette).
   - Also check the copier's own physical control panel / Web UI (`Tray Settings`) to ensure physical sensors match **Letter**! Restart `Spooler` via `04_Devices/Reset-PrintSpooler.ps1` if queued jobs still carry stale `A4` properties.

## Verification & Post-Fix Checks
1. Re-run `04_Devices/Get-PrinterPortsAndScannerHealth.ps1` and verify `DefaultPrinterPolicy` is `LockedManual`, the office printer port is `Standard TCP/IP` (`IP_...`, not `WSD`), and `PrinterStatus` is **Normal**.
2. Have `jsmith@example.com` print a Windows Test Page (`Printer properties -> Print Test Page`) plus a 1-page PDF/Word document to confirm correct tray feed and default printer persistence.

## Cross-Subject Escalation & Pivot Links
- **Print Spooler keeps crashing, jobs stick in queue, or RPC error `0x0000011b`:** [prt-001 — Print Spooler Stuck, Offline Printer, and RPC Print Error 0x0000011b](./prt-001-spooler-and-0x0000011b.md)
- **User also needs Scan-to-Folder (SMB) or WIA scanner configured:** [prt-006 — MFP Scanner Scan-to-Folder (SMB) Failure, NTLMv2 Auth Errors, and WIA/TWAIN Scanner Not Found](./prt-006-scanner-mfp-scan-to-smb-folder-and-wia-twain-failure.md)
- **Printer IP `10.0.10.50` is unreachable across VLANs or over VPN:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Domain GPO deployed wrong printers or blocked Point-and-Print installation:** [id-004 — Active Directory GPO Not Applying, SYSVOL Permissions, and DFSR Replication Errors](../01_Identity_AD_Entra/id-004-ad-gpo-not-applying-replication-and-dfsr.md)

## Useful Links & External Tools
- **[Windows Release Health & Known Issues](https://learn.microsoft.com/en-us/windows/release-health/)** — Check active Microsoft printing, Universal Print, or Point-and-Print KB known issues before rolling out driver fixes.
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Review or deploy Intune-packaged Universal Print / Win32 TCP/IP printer scripts for remote endpoints.

## Client Update Snippets (EN / FR)
- **EN:** We deployed your network printer using a stable TCP/IP port, locked your preferred default printer so Windows stops changing it automatically, and aligned the paper tray settings to Letter. Could you please send a quick test print and confirm it prints cleanly from the right tray?
- **FR:** Nous avons configuré l'imprimante réseau sur un port TCP/IP stable, verrouillé votre imprimante par défaut pour éviter qu'elle ne change automatiquement et ajusté le bac papier au format Lettre. Pouvez-vous lancer une page d'impression test pour confirmer que tout fonctionne correctement ?
