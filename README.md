# GuideIT Master ⚡📘

A unified, offline-capable **Python 3.11+ / PySide6 / SQLite** Windows desktop workstation combining **PowerShellStore** (production Windows PowerShell 5.1 diagnostic & remediation workstation) and **GuideIT** (L1–L3 bilingual EN/FR troubleshooting playbook library).

> **Build Status:** **Phase 4 Complete** — Unified root project scaffolding, PyInstaller-ready `paths.py` with writable `user_scripts/` overlay support, `AppEventBus`, `UnifiedShellWindow` (Playbooks | Scripts | Split View, Unified Omnibox `Ctrl+Shift+K`, tray, global `Win+F8` hotkey, opacity slider, and cyber-aurora frosted-glass UI), the **PowerShellStore** Windows PowerShell 5.1 workstation, the **GuideIT** bilingual (EN/FR) troubleshooting library, bidirectional `linked_scripts` / `psstore://` / `📘 Used in Playbooks` cross-linking, `guideit_master.spec`, and cross-PowerShell `build.ps1` (`-VerifyOnly` / `-Package`) are implemented and verified.

---

## 🚀 Key Features (Phases 1–4)

- **Bilingual (EN/FR) L1–L3 Playbooks Across Numbered Operational Domains:** Canonical troubleshooting workflows under `playbooks/` (`01_Identity_AD_Entra` through `09_Apps_LOB`) organized into domain subcategories with progressive triage, read-only diagnostics, confirmation-gated remediations, verification checks, and 1-click EN/FR client update snippets.
- **Accent-Insensitive SQLite FTS5 Search & Taxonomy Expansion:** `data/guideit.db` (`playbooks_fts`) and `data/powershell_store.db` (`scripts_fts`) power unified EN/FR symptom expansion via `taxonomy/keyword_map.json`, boosting PowerShell scripts linked to top-matching playbooks in both the Unified Omnibox (`Ctrl+Shift+K`) and `tools/search_cli.py`.
- **Bidirectional Playbook ↔ Script Deep Linking:** Playbooks link directly to canonical `NN_Category/Verb-Noun.ps1` scripts via `linked_scripts` frontmatter and `psstore://` URIs—rendering 1-click **`⚡ Linked Diagnostic & Remediation Scripts`** action cards (`Copy RMM-Ready`, `Copy Raw`, `Open in Workstation`, `Split View & Run`, plus **`📦 Copy Read-Only Bundle`** / **`☑ Load Read-Only Batch`** when 2+ `read_only` scripts are linked) inside `PlaybookViewer` and reverse **`📘 Used in Playbooks`** pills inside PowerShellStore's inspector pane.
- **Curated External Tools Directory (`Ctrl+T`) & Multi-Tenant PII + Cross-Link Health Pill:** Searchable `ResourcesDialog` (`taxonomy/resources.json`) of curated MSP & Data Center lookup sites and live `ValidationDialog` enforcing zero non-placeholder emails, public IPs, raw GUIDs, secret tokens, or broken `linked_scripts` (`BROKEN_LINKED_SCRIPT`).
- **Ready-to-Use PowerShell 5.1 Scripts + Writable `user_scripts/` Overlay:** Production diagnostics and remediations under `powershell_scripts/` (`01_System`, `02_Network`, `03_M365`, `04_Devices`, `05_Security_Defender`, and `99_Custom`), plus optional writable `data/user_scripts/` (or `%LOCALAPPDATA%\GuideIT_Master\user_scripts\` when frozen) overlay scanning where custom technician `.ps1` files take precedence over bundled paths without modifying read-only `_MEIPASS` assets.
- **Unified Shell Window & Mode Switcher (`Alt+1` / `Alt+2` / `Alt+3`):** Permanent top-level `QSplitter` housing `PlaybooksWorkspaceWidget` and `ScriptsWorkspaceWidget` with compact-mode Split View (`Alt+3`) without widget reparenting or duplicate runners.
- **Single Shell Owner for System Services:** `UnifiedShellWindow` exclusively owns the system tray icon (`QSystemTrayIcon`), minimize-to-tray `closeEvent`, global `Win+F8` Win32 hotkey (`hotkey_service.py`), Windows login startup (`startup_service.py`), and the **60%–100% window opacity slider**.
- **Multi-Script Checkboxes & Clickable Sorting:** Click column headers (`Title`, `Risk Level`, `Admin`) to sort alphanumerically or by risk/admin flags, and check multiple scripts across categories/filters (including one-click **Read-Only** `Ctrl+Shift+O` selection) to copy combined PowerShell 5.1 `& { ... }` bundles or run sequentially locally / in one UAC-elevated session.
- **File-First Architecture with Live Sync:** Real `.ps1` files under `powershell_scripts/` and `user_scripts/` are scanned via `.PSSTORE_META` JSON headers and SHA-256 hashes into SQLite (`data/powershell_store.db`) automatically via `QFileSystemWatcher`.
- **Dynamic Parameter Forms & Dual-Mode Clipboard:** Generates typed controls (`string`, `int` with bounds, `bool`) from `.PSSTORE_META.params`, preserves parameter edits across selections, and copies either **Raw Script** (`Ctrl+Shift+C`) or **RMM-Ready Script** (`Ctrl+Shift+R`, in-memory `param()` default injection).
- **Local Testing Sandbox & Rich-Text Ticket Reports:** Non-blocking `QProcess` execution with live stdout/stderr streaming, per-script `QTimer` timeouts, remediation safety gates, UAC elevation prompts, SQLite **Run History**, Rich-Text HTML + Markdown clipboard copy (`Ctrl+Shift+T`), and standalone `.html` audit export (`Ctrl+S`).
- **PyInstaller Onedir Packaging & Dual-Shell Build Pipeline (`guideit_master.spec` + `build.ps1`):** Clean separation between read-only bundled assets (`get_bundle_dir()`) and writable user data (`get_user_data_dir()` → `data/` in dev, `%LOCALAPPDATA%\GuideIT_Master` when frozen, or `GUIDEIT_DATA_DIR` override), with automated `--smoke-test` verification for frozen builds.

---

## 🛠️ Quick Start

### Prerequisites
- **OS:** Windows 10 / Windows 11 / Windows Server 2016+
- **Python:** 3.11 or higher
- **PowerShell:** Windows PowerShell 5.1 (`powershell.exe`, default for maximum RMM compatibility) and/or PowerShell 7+ (`pwsh.exe`)

### Installation
```powershell
pip install -r requirements.txt
```

### Running the Application
```powershell
# Normal windowed launch
python main.py

# Silent background startup to system tray (press Win+F8 to toggle)
pythonw main.py --startup
```

### Custom User Scripts Overlay (`user_scripts/`)
Drop custom `.PSSTORE_META`-compliant `.ps1` scripts into:
- **Source / Development:** `data/user_scripts/`
- **Frozen `.exe` Build:** `%LOCALAPPDATA%\GuideIT_Master\user_scripts\` (opened directly by `Ctrl+O` when frozen)

Custom scripts placed directly in `user_scripts/` default to the `Custom` category (unless `"category"` is specified in `.PSSTORE_META`), and scripts placed in matching `NN_Category/Verb-Noun.ps1` paths cleanly override bundled scripts without touching read-only `_MEIPASS` bundle files.

### Verification, CLI Tools & PyInstaller Packaging (`build.ps1`)
```powershell
# Strictly validate all playbooks (schema, sections, linked_scripts, and multi-tenant PII rules)
python tools/validate_playbooks.py --strict

# Build or rebuild the GuideIT SQLite FTS5 search index (data/guideit.db)
python tools/build_index.py

# Unified EN/FR search across both playbooks and PowerShell scripts
python tools/search_cli.py "compte verrouille" --json

# Lint all bundled PowerShell scripts against the .PSSTORE_META and PS 5.1 AST contract
python tools/lint_scripts.py

# Run the complete unified test suite (Paths + PSStore + GuideIT + Cross-Linking + Phase 4 E2E)
python -m pytest tests/ -v

# Run full Phase 4 verification gate & PyInstaller spec audit (works in Windows PowerShell 5.1 & pwsh 7+)
powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1 -VerifyOnly
pwsh -NoProfile -File build.ps1 -VerifyOnly

# Compile dist\GuideIT_Master\GuideIT_Master.exe via guideit_master.spec and run isolated GUIDEIT_DATA_DIR smoke test
# (Requires PyInstaller: pip install pyinstaller>=6.0)
.\build.ps1 -Package

# Launch compiled standalone workstation
.\dist\GuideIT_Master\GuideIT_Master.exe
```

---

## 📚 Playbook Library Domain Architecture

| Domain Folder | Subject | ID Prefix | Core Scope |
| :--- | :--- | :--- | :--- |
| `01_Identity_AD_Entra` | Identity / AD & Entra ID | `id-NNN` | Account lockouts, MFA/2SV, Kerberos, GPO, hybrid sync, Conditional Access |
| `02_M365_Email_Collab` | Microsoft 365 / Email & Collaboration | `m365-NNN` | Outlook auth, Exchange mail flow, OneDrive, Teams, SharePoint & Workspace |
| `03_Windows_Endpoints` | Windows Endpoints | `win-NNN` | Windows Update, BitLocker, BSODs, licensing, user profiles, audio/video |
| `04_Network_VPN_VoIP` | Network, VPN & VoIP | `net-NNN` | DNS, DHCP, APIPA, Wi-Fi, VoIP jitter, SMB drives, IPsec VPN tunnels |
| `05_Printers_Devices` | Printers & Peripherals | `prt-NNN` | Print Spooler, RPC errors, scan-to-email, Bluetooth headsets, USB-C docks |
| `06_Security_Access` | Security & Access | `sec-NNN` | Phishing/BEC containment, Defender ASR, TLS/SSL certificates, Purview DLP |
| `07_macOS_Mobile_MDM` | macOS, Mobile & MDM | `mdm-NNN` | Intune enrollment, Autopilot, compliance, macOS apps, Keychain, SMB & recovery |
| `08_Servers_Cloud_Infra` | Servers, Cloud & Infrastructure | `srv-NNN` | Windows Server, Linux systemd/OOM/SSH, RAID/IPMI, SFP+ optics, Azure/GCP |
| `09_Apps_LOB` | Applications & LOB | `app-NNN` | Browser SSO loops, Office add-ins, Adobe licensing, LOB runtime certs |

---

## ⌨️ Keyboard Shortcuts

Standard text-editing shortcuts (`Ctrl+C`, `Ctrl+V`, `Ctrl+X`, `Ctrl+A`, `Ctrl+Z`) are left untouched inside search fields, parameter inputs, **Raw Console**, and **Script Source** previews.

### Global Windows Shortcut
| Shortcut | Scope | Action / Function | Behavior & Notes |
| :--- | :--- | :--- | :--- |
| `Win+F8` | Global (OS-wide) | **Show / Minimize GuideIT Master** (`hotkey_service.py` → `toggle_window_visibility`) | Registered via Win32 `RegisterHotKey` by `UnifiedShellWindow`. Restores/brings the window to the foreground from tray or minimized state, or minimizes it if already active. |

### Shell Workspace Modes
| Shortcut | Scope | Action / Function | Behavior & Notes |
| :--- | :--- | :--- | :--- |
| `Alt+1` | In-App | **Playbooks Mode** (`set_mode(MODE_PLAYBOOKS)`) | Displays the Playbooks workspace in full width. |
| `Alt+2` | In-App | **Scripts Mode** (`set_mode(MODE_SCRIPTS)`) | Displays the full 3-pane PowerShellStore Script Workstation. |
| `Alt+3` | In-App | **Split View Mode** (`set_mode(MODE_SPLIT)`) | Displays Playbooks and Script Workstation side-by-side in compact mode without reparenting widgets. |

### Navigation & Catalog
| Shortcut | Scope | Action / Function | Behavior & Notes |
| :--- | :--- | :--- | :--- |
| `Ctrl+B` | In-App | **Toggle Active Sidebar** (`_toggle_active_sidebar`) | Collapses or expands the active workspace's left filter/category sidebar (exits Split View to Scripts if pressed in Split mode). |
| `Ctrl+O` | In-App | **Open Scripts Folder** (`open_scripts_folder`) | Opens `powershell_scripts/` in development, or writable `%LOCALAPPDATA%\GuideIT_Master\user_scripts\` when running as a frozen `.exe`. |
| `Ctrl+F` | In-App | **Focus Script Search Box** (`_focus_search_input`) | Expands the sidebar if collapsed, switches out of Playbooks-only mode if needed, focuses the script search input, and selects existing query text. |
| `F5` | In-App | **Sync Scripts & Re-Index Playbooks** (`_sync_all_libraries`) | Rescans `powershell_scripts/` into `powershell_store.db` AND validates & rebuilds `guideit.db` in the background. |
| `Esc` | In-App | **Stop / Clear Active Search** (`_handle_escape`) | Context-aware: stops the active script if currently running; otherwise clears the Playbooks search bar (in Playbooks mode) or the Scripts search filter. |
| `Ctrl+Shift+A` | In-App | **Check Visible Scripts** (`_shortcut_check_all_visible`) | Checks all scripts currently shown in the Script Catalog table for batch copy or execution. |
| `Ctrl+Shift+O` | In-App | **Check Read-Only Scripts** (`_shortcut_check_read_only_visible`) | Checks all visible `read_only` scripts in the Script Catalog table while leaving remediation scripts unchecked. |
| `Ctrl+Shift+D` | In-App | **Clear Checked Scripts** (`_shortcut_clear_checked`) | Unchecks all selected scripts across all categories. |

### GuideIT Playbooks & External Tools
| Shortcut | Scope | Action / Function | Behavior & Notes |
| :--- | :--- | :--- | :--- |
| `Ctrl+K` | In-App | **Focus Playbook Search** (`_focus_playbook_search`) | Switches to Playbooks mode (`Alt+1`) if needed, focuses the EN/FR playbook search bar, and selects existing text. |
| `Ctrl+Shift+K` | In-App | **Focus Unified Omnibox Search** (`_focus_unified_search`) | Focuses the global header Unified Omnibox to search both GuideIT playbooks and PowerShellStore scripts simultaneously. |
| `Ctrl+T` | In-App | **Useful Websites & External Tools** (`open_resources_dialog`) | Opens the searchable `ResourcesDialog` directory of curated MSP & Data Center websites (`taxonomy/resources.json`). |
| `Ctrl+R` | In-App | **Reset Playbook Search & Filters** (`reset_all`) | Clears the playbook search query, resets Tier/Subjects/OS/Environment/Risk filters, and clears viewer navigation history. |
| `Alt+Left` | In-App | **Back to Previous Playbook** (`navigate_back`) | Steps back through visited playbooks after clicking related `[id-NNN]` pills or inline `guideit://` links. |
| `Ctrl+Shift+B` | In-App | **Copy Linked Read-Only Bundle** (`_shortcut_copy_linked_readonly_bundle`) | Context-aware in Playbooks (`Alt+1`) and Split View (`Alt+3`): bundles 2+ linked `read_only` scripts on the active playbook into one RMM-ready PowerShell 5.1 `& { ... }` clipboard bundle while strictly excluding remediation scripts. |

### Script Actions & Parameters
| Shortcut | Scope | Action / Function | Behavior & Notes |
| :--- | :--- | :--- | :--- |
| `Ctrl+Shift+C` | In-App | **Copy Raw Script** (`_on_copy_raw_clicked`) | Copies the exact unmodified `.ps1` file (or combined bundle if multiple checked) from disk to the Windows Clipboard. |
| `Ctrl+Shift+R` | In-App | **Copy RMM-Ready Script** (`_on_copy_rmm_clicked`) | Injects current UI parameter values into the script's `param()` defaults in memory and copies the standalone script (or combined bundle) to the Windows Clipboard. |
| `Ctrl+Enter` *(or `Ctrl+Return`)* | In-App | **Test Locally on My PC** (`_shortcut_run_local`) | Runs the checked/selected script locally in the non-blocking `QProcess` sandbox (respects remediation confirmations & UAC prompts; ignored if a script is already running). |
| `Shift+F5` | In-App | **Stop Script** (`_shortcut_stop_execution`) | Terminates the currently running local PowerShell script (active only while executing). |
| `Ctrl+Alt+R` | In-App | **Reset Parameter Defaults** (`_shortcut_reset_parameters`) | Restores all configurable parameters on the selected script back to their `.PSSTORE_META` defaults. |

### Workstation Tabs & Ticket Reporting
| Shortcut | Scope | Action / Function | Behavior & Notes |
| :--- | :--- | :--- | :--- |
| `Ctrl+1` | In-App | **Structured Results Tab** (`_switch_console_tab(0)`) | Switches the right workstation pane to **Structured Results**. |
| `Ctrl+2` | In-App | **Raw Console Tab** (`_switch_console_tab(1)`) | Switches the right workstation pane to **Raw Console**. |
| `Ctrl+3` | In-App | **Script Source Tab** (`_switch_console_tab(2)`) | Switches the right workstation pane to read-only **Script Source**. |
| `Ctrl+4` | In-App | **Run History Tab** (`_switch_console_tab(3)`) | Switches the right workstation pane to **Run History**. |
| `Ctrl+Shift+T` | In-App | **Copy Ticket Report** (`_shortcut_copy_report`) | Copies Rich-Text HTML + Markdown audit evidence for the active (or reloaded history) run to the Windows Clipboard. |
| `Ctrl+S` | In-App | **Save Report...** (`_shortcut_save_report`) | Opens the Save dialog to export a self-contained `.html` execution report to disk. |
| `Ctrl+L` | In-App | **Clear Raw Console** (`_shortcut_clear_console`) | Clears all text in the **Raw Console** tab. |

### Window & Application
| Shortcut | Scope | Action / Function | Behavior & Notes |
| :--- | :--- | :--- | :--- |
| `Ctrl+=` / `Ctrl++` | In-App | **Increase Window Opacity** (`_adjust_opacity(+5)`) | Raises `UnifiedShellWindow` opacity by `+5%` (clamped at `100%`). |
| `Ctrl+-` | In-App | **Decrease Window Opacity** (`_adjust_opacity(-5)`) | Lowers `UnifiedShellWindow` opacity by `-5%` (clamped at `60%`). |
| `Ctrl+0` | In-App | **Reset Window Opacity** (`_reset_opacity`) | Restores `UnifiedShellWindow` opacity immediately to `100%`. |
| `Ctrl+Q` | In-App | **Quit GuideIT Master** (`quit_application`) | Unregisters `Win+F8`, hides the tray icon, and exits completely (bypasses minimize-to-tray). |

---

## 📦 Built-In PowerShell Script Catalog

All built-in scripts live under `powershell_scripts/`, target Windows PowerShell 5.1 (`Desktop`) for maximum RMM compatibility, pass static + PowerShell 5.1 AST validation via `tools/lint_scripts.py`, and wrap execution in `try / catch / finally` with `$ErrorActionPreference = 'Stop'`.

### `01_System`
| Script | Title | Risk / Admin | Parameters (Defaults & Range) | Explanation & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `Get-BatteryHealthReport.ps1` | Get Battery Health & Power Status | `read_only` · No · `30s` | `WearThresholdPercent=30` *(int, 5–80)* | Inspects `.NET PowerStatus` for live charge %, AC line status, and battery presence, then extracts `powercfg.exe /batteryreport /xml` design vs. full-charge capacity, cycle count, and wear %. |
| `Get-DiskSpaceReport.ps1` | Disk Free Space Report | `read_only` · No · `20s` | `LowSpaceThresholdPercent=15` *(int, 1–90)* | Evaluates fixed logical volumes (`Win32_LogicalDisk` via CIM with `.NET DriveInfo` fallback) returning `DeviceID`, `VolumeName`, `TotalGB`, `FreeGB`, `PercentFree`, and `LowDiskSpace`. |
| `Get-HardwareInventory.ps1` | Get Hardware & BIOS Inventory | `read_only` · No · `30s` | `IncludeGPU=true` *(bool)* | Gathers manufacturer, product model, motherboard, BIOS version/release date, CPU name/clock/cores, RAM usage %, and display adapters via CIM with read-only registry fallback. |
| `Get-HighResourceProcesses.ps1` | Get High-Resource Processes | `read_only` · No · `20s` | `SortBy="CPU"` *(string: `CPU` \| `Memory`)*, `TopCount=10` *(int, 1–50)* | Audits running processes sorted by CPU seconds or Working Set memory, reporting PID, name, `CPUSec`, `WorkingSetMB`, `PrivateMemMB`, company, and executable path. |
| `Get-OSInformation.ps1` | Get Operating System Information | `read_only` · No · `30s` | `Detailed=true` *(bool)* | Collects OS edition/caption, DisplayVersion, build number, architecture, install date, last boot time, uptime, pending reboot indicator, and optional hotfix count. |
| `Get-PendingRebootStatus.ps1` | Check Pending Reboot Status | `read_only` · No · `15s` | *None* | Checks Windows registry indicators for CBS (`RebootPending`), Windows Update (`RebootRequired`), Pending File Rename Operations, and pending Computer Name changes. |
| `Get-RecentEventErrors.ps1` | Get Recent Event Log Errors | `read_only` · No · `30s` | `HoursBack=24` *(int, 1–168)*, `MaxEvents=30` *(int, 5–100)* | Queries `Get-WinEvent` across `System` and `Application` logs for `Critical` (Level 1) and `Error` (Level 2) records within the lookback window. |
| `Get-StartupApplications.ps1` | Get Startup Applications & Tasks | `read_only` · No · `25s` | `IncludeScheduledTasks=true` *(bool)* | Enumerates auto-start items from `HKCU`/`HKLM` `Run` keys, Startup folder shortcuts, and logon/boot Scheduled Tasks. |
| `Get-SystemCrashHistory.ps1` | Get System Crash & BSOD History | `read_only` · **Yes** · `30s` | `MaxDays=30` *(int, 1–90)* | Inspects `C:\Windows\Minidump\*.dmp` files and `System` Event Log crash entries (`Id` `1001` BugCheck & `41` Kernel-Power) within `MaxDays`. |
| `Invoke-DeepSystemCleanup.ps1` | Deep System Cleanup & Health Repair | `remediation` · **Yes** · `600s` | `ClearUserTemps=true`, `ClearSystemTemp=true`, `ClearWindowsUpdateCache=true`, `EmptyRecycleBins=true`, `RunDismCleanup=true`, `RunSfcScan=true` *(all bool)* | Clears user/system Temp, Windows Update cache, and Recycle Bins, runs `DISM /Online /Cleanup-Image /StartComponentCleanup` and `sfc /scannow`, and reports space reclaimed. |
| `Update-Windows.ps1` | Install Windows Updates | `remediation` · **Yes** · `900s` | `ScanOnly=false` *(bool)*, `AutoReboot=false` *(bool)*, `MaxUpdates=25` *(int, 1–100)* | Uses `Microsoft.Update.Session` COM API to search, download, and install pending updates (or scan only), reporting KB IDs and `reboot_required`. |

### `02_Network`
| Script | Title | Risk / Admin | Parameters (Defaults & Range) | Explanation & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `Get-ListeningPorts.ps1` | Get Active Listening Ports | `read_only` · No · `20s` | `Protocol="All"` *(string: `All` \| `TCP` \| `UDP`)*, `PortFilter=0` *(int, 0–65535)* | Lists active TCP listeners and UDP endpoints mapped to local address, PID, process name, and executable path (with `netstat.exe -ano` fallback). |
| `Get-NetworkSnapshot.ps1` | Get Network & DNS Snapshot | `read_only` · No · `20s` | `AdapterName="*"` *(string wildcard)* | Collects matching network adapters (`Get-NetAdapter` with `.NET NetworkInterface` fallback), operational status, link speed, MAC, and DNS servers. |
| `Get-WiFiDiagnostics.ps1` | Get Wi-Fi Health & Signal Diagnostics | `read_only` · No · `25s` | `PingGateway=true` *(bool)* | Queries `netsh wlan show interfaces` for SSID, BSSID, signal %, radio type, channel, Tx/Rx Mbps, and optionally pings the default gateway. |
| `Reset-NetworkStack.ps1` | Reset Network Stack & Flush DNS | `remediation` · **Yes** · `60s` | `FlushDNS=true`, `RenewDHCP=true`, `ResetWinsock=true`, `ResetTCPStack=true` *(all bool)* | Executes selectable network stack repair steps (`ipconfig /flushdns` + `/registerdns`, `/release` + `/renew`, `netsh winsock reset`, `netsh int ip reset`). |
| `Test-NetworkQuality.ps1` | Test Network Quality & Jitter | `read_only` · No · `45s` | `TargetHost="1.1.1.1"`, `PingCount=10` *(int, 4–50)*, `MaxAcceptableLatencyMs=100` *(int, 10–1000)* | Runs ICMP echo probes (falling back to TCP 443/80), computing min/avg/max latency, jitter, packet loss %, and `QualityRating`. |
| `Test-PortConnectivity.ps1` | Test TCP Port Connectivity | `read_only` · No · `15s` | `TargetHost="1.1.1.1"`, `Port=443` *(int, 1–65535)*, `TimeoutMs=3000` *(int, 500–15000)* | Opens an async `.NET TcpClient` connection test to `TargetHost:Port` with explicit millisecond timeout control. |

### `03_M365`
| Script | Title | Risk / Admin | Parameters (Defaults & Range) | Explanation & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `Clear-BrowserCache.ps1` | Clear Browser Cache (Edge & Chrome) | `remediation` · No · `30s` | `TargetBrowser="All"` *(string: `All` \| `Edge` \| `Chrome`)*, `CloseRunningBrowsers=true` *(bool)* | Optionally closes `msedge`/`chrome` and purges `Cache`, `Code Cache`, and `GPUCache` while preserving bookmarks, passwords, and history. |
| `Clear-OutlookCache.ps1` | Clear Microsoft Outlook Cache | `remediation` · No · `60s` | `CloseOutlook=true`, `ClearAttachmentTemp=true`, `ClearRoamCache=true`, `PreserveAutoComplete=true`, `ClearOfflineAddressBook=true`, `ClearFormsCache=true` *(all bool)* | Terminates Outlook and clears `Content.Outlook`, `RoamCache` (preserving `Stream_Autocomplete_*.dat` by default), OAB, Forms, and New Outlook (`OLK`) caches. |
| `Clear-TeamsCache.ps1` | Clear Microsoft Teams Cache | `remediation` · No · `30s` | `KillRunningProcesses=true`, `RelaunchTeams=false` *(both bool)* | Stops Classic and New Teams processes, clears cache subfolders, and optionally relaunches `ms-teams:`. |
| `Get-EntraRegistrationStatus.ps1` | Get Entra ID Join & Device Status | `read_only` · No · `20s` | *None* | Runs native `dsregcmd.exe /status` and parses `AzureAdJoined`, `EnterpriseJoined`, `DomainJoined`, `DeviceId`, and `TenantName`. |
| `Get-OfficeActivationStatus.ps1` | Get Office & M365 Activation Status | `read_only` · No · `30s` | `CheckVolumeLicensing=true` *(bool)* | Reads Office Click-to-Run registry configuration, installed release IDs, Shared Computer Licensing, signed-in identity, and optional `OSPP.VBS` KMS state. |
| `Get-OutlookAddins.ps1` | Get Outlook COM Add-ins & Cache Status | `read_only` · No · `20s` | `CheckOSTSize=true` *(bool)* | Audits HKCU/HKLM Outlook COM Add-ins (`ProgId`, name, scope, `LoadBehavior`) and optionally inspects `.ost` mailbox file sizes. |
| `Reset-OneDriveSync.ps1` | Reset Microsoft OneDrive Sync | `remediation` · No · `45s` | `KillRunningProcess=true`, `RunResetCommand=true`, `RelaunchOneDrive=true` *(all bool)* | Stops `OneDrive.exe`, cleans temporary sync lock/cache artifacts without deleting user files, runs `OneDrive.exe /reset`, and relaunches OneDrive. |

### `04_Devices`
| Script | Title | Risk / Admin | Parameters (Defaults & Range) | Explanation & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `Get-DeviceDrivers.ps1` | Get Installed Device Drivers | `read_only` · No · `45s` | `DeviceClass="*"` *(wildcard)*, `OnlySigned=false` *(bool)*, `MaxResults=50` *(int, 1–1000)* | Inventories PnP drivers via CIM `Win32_PnPSignedDriver`, Registry Class keys, and `driverquery` fallback. |
| `Get-DisplayTopology.ps1` | Get Display & Monitor Topology | `read_only` · No · `20s` | *None* | Enumerates active monitors via `System.Windows.Forms.Screen` paired with GPU controllers (`Win32_VideoController`). |
| `Get-PrintQueues.ps1` | Get Print Queues & Stuck Jobs | `read_only` · No · `30s` | `IncludeJobs=true`, `OnlyWithJobs=false` *(both bool)* | Inspects installed printers (`Get-Printer`) and queued/stuck jobs (`Get-PrintJob`) with `.NET PrinterSettings` + spooler file fallback. |
| `Get-ProblemDevices.ps1` | Get Problem Devices (Device Manager Errors) | `read_only` · No · `20s` | `IncludeDisabled=false` *(bool)* | Queries `Win32_PnPEntity` where `ConfigManagerErrorCode <> 0` and translates Device Manager error codes (Code 10, 28, 39, 43, etc.). |
| `Reset-PrintSpooler.ps1` | Reset Print Spooler | `remediation` · **Yes** · `30s` | `ClearQueueFiles=true` *(bool)* | **Output Mode: `text`.** Stops `Spooler`, optionally clears `%SystemRoot%\System32\spool\PRINTERS\*`, restarts `Spooler`, and outputs service state. |
| `Update-DeviceDrivers.ps1` | Update All Device Drivers | `remediation` · **Yes** · `600s` | `IncludeOptional=true`, `RescanPnPDevices=true`, `RebootIfRequired=false` *(all bool)* | Uses `Microsoft.Update.Session` (`Type='Driver'`) to download/install pending drivers, runs `pnputil.exe /scan-devices`, and optionally schedules a 60s reboot. |

### `05_Security_Defender`
| Script | Title | Risk / Admin | Parameters (Defaults & Range) | Explanation & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `Get-BitLockerStatus.ps1` | Get BitLocker Encryption Status | `read_only` · **Yes** · `30s` | `MountPoint=""` *(string)* | Queries `Get-BitLockerVolume` (with `manage-bde.exe -status` fallback) to audit encryption %, protection status, and key protectors. |
| `Get-DefenderStatus.ps1` | Get Microsoft Defender Status | `read_only` · No · `20s` | *None* | Queries `Get-MpComputerStatus` for Antivirus, Antispyware, Real-Time Protection, engine/signature versions, and signature age in days. |
| `Get-ExpiringCertificates.ps1` | Get Expiring & Expired Certificates | `read_only` · No · `20s` | `DaysThreshold=30` *(int, 1–180)* | Scans `Cert:\LocalMachine\My` and `Cert:\CurrentUser\My` stores to flag certificates expired or expiring within `DaysThreshold` days. |
| `Get-FirewallStatus.ps1` | Get Windows Firewall Status | `read_only` · No · `30s` | `CheckAllProfiles=true` *(bool)* | Checks Windows Firewall state and default inbound/outbound actions across `Domain`, `Private`, and `Public` profiles with registry fallback. |
| `Get-LocalAccountStatus.ps1` | Get Local Account & Password Status | `read_only` · **Yes** · `20s` | *None* | Audits local user accounts (`Get-LocalUser` + `ADSI WinNT://`) including lockout state, password age, expiration policy, and last logon. |
| `Get-LocalAdministrators.ps1` | Audit Local Administrators | `read_only` · **Yes** · `20s` | `IncludeBuiltInAdmin=true` *(bool)* | Enumerates members of local `Administrators`, classifying `Local`, `Active Directory Domain`, or `Microsoft Entra ID` principals. |
| `Invoke-DefenderUpdateAndScan.ps1` | Update Defender Signatures & Trigger Scan | `remediation` · **Yes** · `300s` | `ScanType="QuickScan"` *(string: `QuickScan` \| `FullScan`)*, `UpdateSignatures=true` *(bool)* | Updates Defender signatures (`Update-MpSignature`), runs `Start-MpScan` (`MpCmdRun.exe` fallback), and checks `Get-MpThreatDetection`. |

### `99_Custom`
| Script | Title | Risk / Admin | Parameters (Defaults & Range) | Explanation & Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `Sample-CustomDiagnostic.ps1` | Sample Custom Diagnostic | `read_only` · No · `15s` | `Message="Hello from PowerShellStore"` *(string)* | Minimal starter template demonstrating `.PSSTORE_META`, typed `param()`, CIM query, ASCII table output, and single-line JSON envelope. |
