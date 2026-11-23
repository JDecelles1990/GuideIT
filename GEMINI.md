# GuideIT Master — Unified Workspace Architecture & Coding Contract (`GEMINI.md`)

## 1. Project Identity & Core Workflow

**GuideIT Master** is a unified, offline-capable **Python 3.11+ / PySide6 / SQLite** Windows desktop workstation and Antigravity knowledge base built for **Multi-OS bilingual (EN/FR) MSP helpdesk and data center technicians (L1 through L3)**. It combines two core modules under one shell window:

1. **GuideIT Playbook Library (`playbooks/` + `taxonomy/`):**
   - 65 canonical L1–L3 Markdown troubleshooting playbooks across 9 numbered domains (`01_Identity_AD_Entra` through `09_Apps_LOB`) and 23 subcategories.
   - Powered by an accent-insensitive SQLite FTS5 search engine (`data/guideit.db`) with bilingual EN/FR symptom expansion (`taxonomy/keyword_map.json`), exact error-code ranking, and a curated external tools directory (`taxonomy/resources.json`).
2. **PowerShellStore Script Workstation (`powershell_scripts/`):**
   - 38 production Windows PowerShell 5.1 (`Desktop`) diagnostic and remediation `.ps1` scripts across 6 numbered categories (`01_System` through `99_Custom`).
   - File-first architecture: real `.ps1` files on disk with `.PSSTORE_META` JSON headers are indexed automatically into SQLite (`data/powershell_store.db`) with SHA-256 integrity checks, dynamic typed UI parameter forms, **Copy Raw Script**, **Copy RMM-Ready Script** (in-memory `param()` default injection and multi-script `& { ... }` bundles), non-blocking `QProcess` local sandbox & single-UAC batch execution, and Rich-Text HTML + Markdown ticket audit reports.
3. **Bidirectional Deep Linking & Split-View Workstation:**
   - Markdown playbooks link directly to PowerShell scripts via YAML frontmatter `linked_scripts` and inline `psstore://` links.
   - Technicians can copy RMM-ready scripts directly from a playbook card, open a linked script preloaded in the Script Workstation, view reverse `"Used in Playbooks"` badges on every script, or work in **Split View (`Alt+3`)** with the playbook on the left and the live PowerShell runner/parameter form on the right.

> **CRITICAL READ-ONLY RULE:** The reference directories `_ref_GuideIT/` and `_ref_PowerShellStore/` are **STRICTLY READ-ONLY** historical archives. Never modify, move, or delete any file inside `_ref_GuideIT/` or `_ref_PowerShellStore/`.

---

## 2. Repository Map & PyInstaller-Ready Path Resolution

All filesystem access **MUST** go through `src/guideit_master/paths.py` so the app runs identically from source and from a frozen PyInstaller `.exe` bundle:

- **Read-Only Bundled Assets (`paths.get_bundle_dir()` — repo root in dev, `sys._MEIPASS` when frozen):**
  - `playbooks/01_Identity_AD_Entra/` (`id-NNN`) — Identity / AD & Entra ID
  - `playbooks/02_M365_Email_Collab/` (`m365-NNN`) — Microsoft 365 / Email & Collaboration
  - `playbooks/03_Windows_Endpoints/` (`win-NNN`) — Windows Endpoints
  - `playbooks/04_Network_VPN_VoIP/` (`net-NNN`) — Network, VPN & VoIP
  - `playbooks/05_Printers_Devices/` (`prt-NNN`) — Printers & Peripherals
  - `playbooks/06_Security_Access/` (`sec-NNN`) — Security & Access
  - `playbooks/07_macOS_Mobile_MDM/` (`mdm-NNN`) — macOS, Mobile & MDM
  - `playbooks/08_Servers_Cloud_Infra/` (`srv-NNN`) — Servers, Cloud & Infrastructure
  - `playbooks/09_Apps_LOB/` (`app-NNN`) — Applications & LOB
  - `powershell_scripts/01_System/`, `02_Network/`, `03_M365/`, `04_Devices/`, `05_Security_Defender/`, `99_Custom/` — Categorized `.ps1` script catalog
  - `taxonomy/` — `domains.json`, `schema.json`, `keyword_map.json`, `resources.json`
  - `templates/` — `playbook-template.md`
  - `docs/` — `TROUBLESHOOTING_MATRIX.md`
- **Writable Local User Data (`paths.get_user_data_dir()` — `data/` in dev, `%LOCALAPPDATA%\GuideIT_Master` when frozen, or `GUIDEIT_DATA_DIR` override in tests):**
  - `data/guideit.db` — Generated SQLite FTS5 playbook index (gitignored)
  - `data/powershell_store.db` — Generated SQLite script catalog, `scripts_fts` & `run_history` database (gitignored)
  - `data/user_scripts/` — Reserved writable custom `.ps1` scripts directory (overlay scanning deferred to Phase 4)
  - `data/logs/` — Diagnostic logs
- **Application Source & Tooling (Clean `guideit_master.*` Imports Only — Zero Legacy Shims):**
  - `src/guideit_master/` — Unified Python package (`paths.py`, `core/event_bus.py`, `services/`, `ui/`, `guideit/`, `psstore/`)
  - `tools/` — CLI entrypoints (`validate_playbooks.py`, `build_index.py`, `search_cli.py`, `lint_scripts.py`)
  - `.agents/skills/` — Workspace skills (`triage-ticket`, `new-playbook`, `audit-library`, `powershell-script-authoring`)
  - `tests/` — Automated pytest suite (`tests/psstore/`, `tests/guideit/`, `tests/test_paths.py`, `tests/test_cross_linking.py`, `tests/test_e2e_unified.py`)

---

## 3. Strict Layer Boundaries & Module Decoupling

Modules must never bypass their architectural layer:

```text
ui/ (PySide6 Presentation Views & Widgets ONLY)
  ↓ communicates via typed models & AppEventBus Qt Signals
services/ (Scanner, QProcess Runner, Clipboard Injector, Report, Validator, Search, CrossLink)
  ↓
repositories/ & indexers/ (CatalogRepo, FTS5 Indexer & Search SQLite Persistence)
  ↓
data/guideit.db + data/powershell_store.db + playbooks/ + powershell_scripts/
```

1. **Presentation Layer (`src/guideit_master/ui/`, `guideit/ui/`, `psstore/ui/`):**
   - Contains PySide6 widgets, views, layouts, syntax highlighters, and visual effects only.
   - **FORBIDDEN IMPORTS IN `ui/`:** Never import `sqlite3`, `subprocess`, or `hashlib` inside any `ui/` file. Never execute blocking disk/process I/O on the GUI thread.
2. **Zero UI Cross-Imports & No Legacy Top-Level Shims:**
   - `guideit_master.guideit.ui` must **NEVER** import from `guideit_master.psstore.ui`, and `guideit_master.psstore.ui` must **NEVER** import from `guideit_master.guideit.ui`.
   - All Python imports across source, tools, and tests **MUST** use `guideit_master.*` directly (no top-level compatibility shim packages such as `src/guideit/`, `src/repositories/`, `src/services/`, or `src/ui/`).
   - All cross-module interactions (opening a linked script from a playbook, copying an RMM-ready script from a playbook card, opening Split View, or jumping from a script's `"Used in Playbooks"` badge back to a playbook) **MUST** flow through `AppEventBus` (`src/guideit_master/core/event_bus.py`) coordinated by `UnifiedShellWindow`.
3. **Split View Without Reparenting & Single Shell Service Owner:**
   - `UnifiedShellWindow` hosts `PlaybooksWorkspaceWidget` and `ScriptsWorkspaceWidget` inside **one permanent top-level `QSplitter`**. Toggling Split View (`Alt+3`) invokes `set_compact_mode(bool)` on each workspace to hide/restore sidebars and catalog lists without reparenting widgets or instantiating duplicate runners/repositories.
   - **ONLY `UnifiedShellWindow`** owns `QSystemTrayIcon`, `closeEvent` minimize-to-tray, window opacity slider, `StartupService`, and `GlobalHotkeyManager` (`Win+F8`). Workspace widgets are pure `QWidget`s that emit signals and never register tray icons or global hotkeys.
4. **Persistence Layer (`CatalogRepo`, `indexer.py`, `search.py`):**
   - Owns all `sqlite3` connections, `CREATE TABLE` / `FTS5` virtual table definitions, and parameterized SQL queries. Always use context managers (`with closing(sqlite3.connect(...))` or `with self._get_connection()`) for transaction safety.

---

## 4. Live Troubleshooting Routing & Diagnostic Safety Guardrails

### 4.1 Live Ticket Triage Routing Contract
When a technician pastes a ticket symptom, log snippet, or error code:
1. **Search the FTS5 index first:** Run `python tools/search_cli.py "<symptom or error code>" --json` (which expands EN/FR phrases via `taxonomy/keyword_map.json` and searches both `guideit.db` playbooks and `powershell_store.db` scripts).
   - If `data/guideit.db` is missing, rebuild it first with `python tools/build_index.py`.
2. **Load minimally:** Open and read only the top 1–3 matched playbooks. Never load the entire `playbooks/` tree into context.
3. **Always cite matches:** Cite every matched playbook ID and relative path explicitly (`[id-001] (playbooks/01_Identity_AD_Entra/id-001-account-lockout.md)`) and any linked PowerShellStore scripts (`powershell_scripts/04_Devices/Reset-PrintSpooler.ps1`).
4. **Match ticket language (EN / FR):** Always reply in the same language as the pasted ticket (English or French) and offer the playbook's EN/FR client update snippets when helpful.
5. **No-Match Protocol:** If search returns zero relevant playbooks, begin explicitly with `[NO PLAYBOOK MATCH]`, provide general **read-only** diagnostic steps clearly labeled as **unverified general guidance outside the GuideIT playbook library**, and offer to capture a validated playbook using the `new-playbook` skill once resolved.

### 4.2 Diagnostic Safety & Accuracy Guardrails
1. **Read-Only Diagnostics First:** Present scoping questions (`Fast Triage`) and non-destructive inspection commands (`Read-Only Diagnostics (L1-L2)` / `Deep-Dive Investigation (L3)`) before proposing any state-changing fix.
2. **Confirmation-Gated Remediation:** Any command or script that alters system, identity, or service state (`risk_level: "remediation"`, PowerShell `Set-*`, `Remove-*`, `Restart-*`, registry edits, GPO/Intune/Entra changes, token revocation) **MUST** be prefixed with `[REMEDIATION — CONFIRM BEFORE RUNNING]` in playbooks and gated behind a confirmation dialog in the desktop UI.
3. **Zero Hallucinated Commands or Codes:** Never invent PowerShell cmdlets, parameters, CLI flags, registry paths, Event IDs, or error codes.

---

## 5. Strict Multi-Tenant MSP Redaction Contract

GuideIT Master is shared across client environments. **Never** write real customer data into playbooks, PowerShell scripts, templates, skills, tests, or `taxonomy/*.json`:

- **Forbidden:** Real client company names, real tenant domains, real user emails/UPNs, real public IPv4/IPv6 addresses, real tenant/subscription/object GUIDs, device serial numbers, passwords, API keys, or session tokens.
- **Approved Synthetic Placeholders Only:**
  - Domains & Emails: `contoso.com`, `example.com`, `example.org`, `example.net`, `fabrikam.com`, `contoso.onmicrosoft.com`, `tenant.onmicrosoft.com`, `domain.local`, `corp.local`, `jsmith@example.com`
  - Network & Hosts: `198.51.100.10` (RFC 5737 TEST-NET-2), `10.0.10.25` (RFC 1918), `1.1.1.1` / `8.8.8.8` / `9.9.9.9` (public DNS), `PC-LAB-01`, `DC01.domain.local`
  - Identifiers: `00000000-0000-0000-0000-000000000000`, `<tenant-id>`, `<user-upn>`, `<device-name>`

The validator (`python tools/validate_playbooks.py --strict`) automatically enforces PII/redaction rules and fails on non-placeholder emails (`PII_EMAIL`), public IPs (`PII_PUBLIC_IP`), raw GUIDs (`PII_GUID`), or secret key headers (`PII_SECRET`).

---

## 6. Playbook Authoring Contract (`playbooks/` & `taxonomy/schema.json`)

- **Atomic Rule:** Keep one root-cause troubleshooting flow per file. Filenames must follow `<id>-<kebab-slug>.md` (lowercase kebab-case) inside the matching numbered domain folder (`playbooks/01_Identity_AD_Entra/` .. `09_Apps_LOB/`).
- **Required YAML Frontmatter Fields:** `id`, `domain`, `subject`, `title`, `tier` (`L1` | `L2` | `L3`), `keywords_en`, `keywords_fr`, `error_codes`, `tags` (`snake_case`), `os`, `environment`, `tools`, `risk_level` (`low` | `medium` | `high`), `requires_admin` (`true` | `false`), `last_verified` (`YYYY-MM-DD`).
- **Optional YAML Frontmatter Fields:** `subcategory` (must match `taxonomy/domains.json`), `related_ids` (list of existing playbook IDs), `linked_scripts` (list of exact `NN_Category/Verb-Noun.ps1` relative paths under `powershell_scripts/`, e.g., `04_Devices/Reset-PrintSpooler.ps1`; filename-only entries without category folder are invalid).
- **Required Markdown Headings (in exact order):**
  1. `## Fast Triage (Under 2 Minutes)`
  2. `## Read-Only Diagnostics (L1-L2)`
  3. `## Deep-Dive Investigation (L3)`
  4. `## Remediation (Confirm Before Running)`
  5. `## Verification & Post-Fix Checks`
  - Optional: `## Cross-Subject Escalation & Pivot Links`, `## Useful Links & External Tools`, `## Client Update Snippets (EN / FR)`

---

## 7. PowerShell Script Contract (`.PSSTORE_META`, PS 5.1 & Batch Compatibility)

Every `.ps1` script under `powershell_scripts/<NN_Category>/` **MUST** obey the file-first contract in `SKILLS.md` and pass `python tools/lint_scripts.py`:

1. **Mandatory Top Comment Block (`.SYNOPSIS` & `.PSSTORE_META` JSON):**
   ```powershell
   <#
   .SYNOPSIS
       Concise one-line description of what this script inspects or remediates.
   .PSSTORE_META
       {
           "title": "Human-Readable Script Title",
           "risk_level": "read_only",
           "ps_edition": "Desktop",
           "requires_admin": false,
           "timeout_seconds": 30,
           "output_mode": "json",
           "params": [
               {"name": "TargetService", "type": "string", "default": "Spooler"},
               {"name": "MaxEvents", "type": "int", "default": 20, "min": 1, "max": 500},
               {"name": "IncludeDisabled", "type": "bool", "default": false}
           ]
       }
   #>
   ```
   - `risk_level`: `"read_only"` (strictly non-mutating; eligible for `Ctrl+Shift+O` bulk selection) or `"remediation"` (modifies state; triggers UI confirmation).
   - `ps_edition`: `"Desktop"` (`powershell.exe` 5.1 for maximum RMM & batch bundle compatibility) or `"Core"` (`pwsh.exe` 7+).
2. **`[CmdletBinding()]` & Injectable `param(...)` Block:**
   - Every parameter in `.PSSTORE_META.params` must appear in `param(...)` with `[Parameter(Mandatory = $false)]`, explicit type (`[string]`, `[int]`, `[bool]` — never `[switch]`), and matching default value.
   - Place the closing `)` of `param(...)` on its own line, do **not** use nested parentheses (`[ValidateSet(...)]` or `[ValidateRange(...)]`) inside `param(...)`, avoid commas inside string defaults, and reference every declared parameter in the script body after `$ErrorActionPreference = 'Stop'`.
3. **Strict Error Handling & Batch Compatibility Rules:**
   - Set `$ErrorActionPreference = 'Stop'` immediately after `param(...)` and wrap all logic in `try { ... } catch { ... } finally { ... }` passing `-ErrorAction Stop` to cmdlets inside `try`.
   - **NEVER call `exit` or `exit 1` inside `output_mode: "json"` scripts** (terminates the host PowerShell process and aborts remaining scripts inside `& { ... }` multi-script clipboard bundles). Catch errors in `catch`, set `$status = "error"`, add to `$errors`, and let `finally` emit the JSON envelope.
   - **NEVER use `#Requires` or `using namespace`** (rejected by PowerShell 5.1 inside `& { ... }` bundles).
   - **NEVER use `[Environment]::TickCount64`** or PowerShell 7-only operators (`? :`, `??`, `&&`, `||`) in `Desktop` scripts.
   - **100% Non-Interactive** (no `Read-Host`, `Pause`, `Out-GridView`, or interactive prompts).
4. **Dual-Purpose Output Contract (`Format-Table` + Single-Line JSON Envelope):**
   - When `output_mode` is `"json"`, format and emit a human-readable ASCII table first (`$results | Format-Table -AutoSize | Out-String -Width 4096 | Write-Output`) for RMM logs and Raw Console.
   - Emit `$payload | ConvertTo-Json -Depth 4 -Compress` as the very last line in `finally`, where `data = @($results)` contains flat PascalCase `[PSCustomObject]` items and `errors = @($errors)` is a flat string array (never `, @($errors)`).

---

## 8. UI, Keyboard Shortcuts & Mandatory Post-Edit Verification

- **Keyboard Shortcuts Documentation Rule (Mandatory):**
  - Whenever a keyboard shortcut (global OS hotkey or in-app `QShortcut`) is assigned, modified, or removed for any function or UI action, you **MUST** document it in the **Keyboard Shortcuts** section of `README.md` in the same change (recording key combination, scope, target action, and behavior) and update the corresponding widget tooltip.
- **Mandatory Post-Edit Verification Commands:**
  After creating or modifying any playbook, taxonomy file, PowerShell script, or Python module, always run:
  ```powershell
  python tools/validate_playbooks.py --strict
  python tools/build_index.py
  python tools/lint_scripts.py
  python -m pytest tests/ -v
  ```
  *(During Phase 1 before GuideIT playbooks are copied into root, run `python tools/lint_scripts.py` and `python -m pytest tests/test_paths.py tests/psstore/ -v`.)*
  Any packaging script (`build.ps1`, added in Phase 4) must run cleanly in **both Windows PowerShell 5.1 (`powershell.exe`) and PowerShell 7 (`pwsh`)**.
  Do not consider any task complete until validation, indexing, PowerShell AST linting, and the pytest suite exit `0`.
