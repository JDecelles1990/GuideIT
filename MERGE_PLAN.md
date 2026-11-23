# GuideIT Master — Architecture Audit & Unified Merge Plan (`GuideIT` + `PowerShellStore`)

## 1. Executive Summary

**GuideIT Master** unifies two production MSP desktop utilities into a single, modular **Python 3.11+ / PySide6 / SQLite** Windows workstation at the root of `GuideIT_Master`:

1. **`_ref_GuideIT`** — Bilingual (EN/FR) L1–L3 IT troubleshooting playbook library (65 Markdown playbooks across 9 domains and 23 subcategories), strict zero-dependency YAML frontmatter & section parser, multi-tenant PII/redaction validator, accent-insensitive SQLite FTS5 search engine with synonym expansion (`taxonomy/keyword_map.json`), curated external tools directory (`taxonomy/resources.json`), and a 3-pane Dark PySide6 search & copy console.
2. **`_ref_PowerShellStore`** — File-first Windows PowerShell 5.1 script library (38 production `.ps1` scripts across 6 categories), `.PSSTORE_META` JSON header scanner with SHA-256 live sync (`QFileSystemWatcher`), SQLite catalog & execution history repository, dynamic typed parameter input forms, dual-mode Windows Clipboard service (Raw & in-memory RMM parameter-injected single/bundle scripts), non-blocking `QProcess` local sandbox & single-UAC batch runner, Rich-Text HTML + Markdown ticket audit report generator, system tray & global `Win+F8` hotkey integration, and cyber-aurora frosted-glass UI effects.

This plan guarantees **100% feature parity (zero simplifications)**, resolves all folder, dependency, UI shell, and layer-boundary conflicts, introduces **bidirectional deep linking & unified FTS5 search** between troubleshooting playbooks and diagnostic/remediation PowerShell scripts, and establishes **PyInstaller-ready path resolution (`src/guideit_master/paths.py`) from Day 1**.

---

## 2. Complete Feature Inventory & Parity Matrix (100% Preservation Contract)

### 2.1 `_ref_GuideIT` Feature Inventory

| Feature Area | Reference Source (`_ref_GuideIT/`) | Capabilities & Contract Details | Unified Target Location & Preservation Strategy |
| :--- | :--- | :--- | :--- |
| **Canonical Playbook Library (65 Playbooks)** | `playbooks/01_Identity_AD_Entra/` .. `09_Apps_LOB/` | 65 atomic L1–L3 Markdown playbooks (`id-001`..`id-008`, `m365-001`..`m365-008`, `win-001`..`win-008`, `net-001`..`net-005`, `prt-001`..`prt-004`, `sec-001`..`sec-004`, `mdm-001`..`mdm-008`, `srv-001`..`srv-016`, `app-001`..`app-004`). 5 ordered required sections (`Fast Triage`, `Read-Only Diagnostics (L1-L2)`, `Deep-Dive Investigation (L3)`, `Remediation (Confirm Before Running)`, `Verification & Post-Fix Checks`) + optional `Cross-Subject Escalation & Pivot Links`, `Useful Links & External Tools`, and `Client Update Snippets (EN / FR)`. | Copied intact to root `playbooks/` in Phase 2; enriched with `linked_scripts` YAML frontmatter in Phase 3. |
| **Taxonomy, Sub-Subjects & Bilingual Keyword Map** | `taxonomy/domains.json`, `taxonomy/schema.json`, `taxonomy/keyword_map.json`, `src/guideit/taxonomy.py` | 9 numbered domains with ID prefixes and 23 `subcategories`; `schema.json` defining required/optional frontmatter fields, enums (`tier`, `os`, `environment`, `risk_level`), section order, allowed placeholder email domains (`contoso.com`, `example.com`, etc.), and allowed public DNS IPs; `keyword_map.json` + `normalize_text()` (NFKD diacritic stripping) + `expand_query()` expanding EN/FR colloquial phrases into canonical tags, domains, and error codes. | `taxonomy/*.json` at root (bundled read-only assets); core logic in `src/guideit_master/guideit/taxonomy.py` (clean `guideit_master.*` imports throughout, zero legacy top-level shims). |
| **Curated External Tools & Websites Directory** | `taxonomy/resources.json`, `src/guideit/ui/widgets/resources_dialog.py` | 31+ curated MSP & Data Center lookup sites (MXToolbox, VirusTotal, AbuseIPDB, URLScan, Subnet Calculators, M365 Maps, KMS GVLK keys, Entra AADSTS lookup, Adobe Cleaner, DisplayLink, Apple Recovery, Cloud Status dashboards) with EN/FR search, category filter, usage instructions, one-click `Copy URL`, and `Open ↗` (`Ctrl+T`). | `taxonomy/resources.json` + `src/guideit_master/guideit/ui/widgets/resources_dialog.py`, accessible via `Ctrl+T` and top command bar. |
| **Strict Zero-Dependency YAML Frontmatter & Section Parser** | `src/guideit/frontmatter.py` | `parse_frontmatter()` with exact 1-based line numbers (`FrontmatterError`), BOM/CRLF handling, inline `#` comment stripping, single/double-quoted scalars, flow lists (`[...]`), block lists (`- item`), duplicate key and tab rejection; `extract_sections()` parsing `## ` headings while ignoring headings inside ```` ``` ```` or `~~~` code fences. | Preserved verbatim in `src/guideit_master/guideit/frontmatter.py`. |
| **Repository Validator & Multi-Tenant PII Linter** | `src/guideit/validator.py`, `scripts/validate.py` | `validate_repository()` enforcing schema fields, ID/domain/filename kebab-case rules, subcategory validity, enum checks, ISO `last_verified` staleness warning (`> 180` days), required section order, `related_ids` & relative `.md` link integrity (`BROKEN_RELATED_ID`, `BROKEN_MD_LINK`, `UNSYNCED_MD_LINK`, `SELF_MD_LINK`), `keyword_map.json` tag coverage (`UNCOVERED_TAG`), and line-by-line PII scanning (`PII_EMAIL`, `PII_PUBLIC_IP`, `PII_GUID`, `PII_SECRET`). | Preserved in `src/guideit_master/guideit/validator.py` and extended in Phase 3 to validate `linked_scripts` against the PowerShell catalog (`BROKEN_LINKED_SCRIPT`). CLI moved to `tools/validate_playbooks.py`. |
| **Atomic SQLite FTS5 Indexer & Hybrid EN/FR Search** | `src/guideit/indexer.py`, `src/guideit/search.py`, `scripts/build_index.py`, `scripts/search.py` | Atomic rebuild via `.tmp.<pid>` + `os.replace` into `guideit.db` (`index_meta`, `playbooks`, `playbooks_fts` with `unicode61 remove_diacritics 2`); `search_playbooks()` combining FTS5 BM25 ranking (`-bm25(...)`) with boosts for exact ID (`+100`), exact error code (`+80`), expanded tag (`+25`), bilingual keyword (`+20`), and suggested domain (`+5`), plus safe FTS token quoting and facet filtering (`domain`, `subcategory`, `tier`, `os_filter`, `env_filter`, `risk_level`). | Preserved in `src/guideit_master/guideit/indexer.py` & `search.py` (writing to `paths.get_guideit_db_path()`); extended in Phase 3 with `linked_scripts_json` and unified search. CLIs in `tools/build_index.py` & `tools/search_cli.py`. |
| **GuideIT 3-Pane Dark Console & Playbook Viewer** | `src/guideit/ui/main_window.py`, `markdown_blocks.py`, `theme.py`, `workers.py`, `widgets/*` | Top search bar (`Ctrl+K`) with 120ms debounce & taxonomy expansion bar; `ValidationDialog` health pill; background `ReindexWorker` (`QThread`, `F5`); `FilterSidebar` (Tier pills, 2-level Subjects tree with Collapse/Expand & counts, OS/Env/Risk combos, `Ctrl+R` reset); `ResultsList` (wrapping `_ResultCardWidget` items + `[NO PLAYBOOK MATCH]` card); `PlaybookViewer` (`_FlowLayout` header, `← Back` `Alt+Left` history, `Copy Path`, `Open .md`, clickable error code chips & related playbook pills, color-striped section cards, amber remediation warnings, auto-wrapping `CodeBlockWidget` with `CommandSyntaxHighlighter` & `Copy`, `Client Update Snippets (EN / FR)` copy cards, `guideit://<id>` link routing). | Embedded as `PlaybooksWorkspaceWidget` inside the unified shell window (`src/guideit_master/guideit/ui/`), preserving every widget attribute, signal, shortcut, and layout behavior. |
| **GuideIT Pytest Suite & Workspace Skills** | `tests/test_frontmatter.py`, `test_search_and_index.py`, `test_validator.py`, `test_ui.py`; `_old_agents/skills/*` | Full unit, FTS5 ranking, PII validation, and headless PySide6 UI tests (including card/code-block no-clipping geometry assertions); `triage-ticket`, `new-playbook`, and `audit-library` skills. | All tests migrated to root `tests/guideit/` and skills unified under `.agents/skills/`. |

### 2.2 `_ref_PowerShellStore` Feature Inventory

| Feature Area | Reference Source (`_ref_PowerShellStore/`) | Capabilities & Contract Details | Unified Target Location & Preservation Strategy |
| :--- | :--- | :--- | :--- |
| **38 Built-In Production PowerShell 5.1 Scripts** | `scripts/01_System/` (11), `02_Network/` (6), `03_M365/` (7), `04_Devices/` (6), `05_Security_Defender/` (7), `99_Custom/` (1) | All 38 `.ps1` scripts with `<# .SYNOPSIS ... .PSSTORE_META { ... } #>`, `[CmdletBinding()] param(...)`, `$ErrorActionPreference = 'Stop'`, `try/catch/finally`, batch-safe execution (no raw `exit 1` in JSON scripts, no `#Requires`, no `[Environment]::TickCount64`), human-readable `Format-Table` output first, and single-line JSON envelope (`ConvertTo-Json -Depth 4 -Compress`) last. | Preserved intact at root `powershell_scripts/<NN_Category>/*.ps1` (resolved via `paths.get_ps_scripts_dir()`). Phase 1 keeps `ScriptScanner` and `CatalogRepo` focused solely on `paths.get_ps_scripts_dir()`; optional `data/user_scripts/` overlay scanning is deferred to Phase 4. |
| **SQLite Catalog & Run History Repository** | `repositories/catalog_repo.py` | `CatalogRepo` managing `scripts` table (unique `relative_path`, metadata, `params_json`, `sha256`) and `run_history` table (foreign key cascade, `duration_ms`, `exit_code`, `status`, `summary`, `parameters_json`, `raw_output`, `json_payload`, `executed_at`) with WAL mode, category counts, and search/risk/edition filters. | Preserved in `src/guideit_master/psstore/repositories/catalog_repo.py` (writing to `paths.get_psstore_db_path()`). |
| **File-First `.PSSTORE_META` Scanner & Live Sync** | `services/scanner.py`, `QFileSystemWatcher` in `launcher_view.py` | `ScriptScanner` parsing `.SYNOPSIS` and `.PSSTORE_META` JSON (with trailing-comma/quote recovery), deriving category names from numbered folders, computing SHA-256 digests, syncing add/update/delete changes to `CatalogRepo`, and auto-rescanning on disk edits via `QFileSystemWatcher`. | Preserved in `src/guideit_master/psstore/services/scanner.py` + `QFileSystemWatcher` in the PowerShellStore workspace view. |
| **Dual-Mode & Multi-Script Bundle Clipboard Service** | `services/clipboard_service.py` | `format_powershell_literal()`, `inject_parameters()` (in-memory regex injection into `param(...)` defaults), `combine_scripts_bundle()` (isolated `try { & { ... } } catch { ... }` PowerShell 5.1 scriptblocks), single and multi-script **Copy Raw Script** (`Ctrl+Shift+C`) and **Copy RMM-Ready Script** (`Ctrl+Shift+R`), with `QGuiApplication.clipboard()` and Win32 `ctypes` fallback. | Preserved verbatim in `src/guideit_master/psstore/services/clipboard_service.py`. |
| **Non-Blocking `QProcess` Sandbox & Batch/UAC Runner** | `services/runner.py` | `ScriptRunner` (`QObject`) executing `powershell.exe` (Desktop 5.1) or `pwsh.exe` (Core 7+) non-blockingly via `QProcess` with per-script `QTimer` timeouts, pre-run SHA-256 check, live stdout/stderr streaming, JSON envelope + `[SUCCESS]`/`[WARNING]`/`[ERROR]` fallback parser (`RunResult`), automatic `run_history` persistence, sequential multi-script `execute_batch()`, and single/batch UAC elevation (`execute_script_elevated()` / `execute_batch_elevated()` via `ShellExecuteW` `runas`). | Preserved verbatim in `src/guideit_master/psstore/services/runner.py`. |
| **Rich-Text HTML & Markdown Ticket Report Service** | `services/report_service.py` | `ReportService` capturing host/operator/OS/timestamp audit headers, generating styled HTML and Markdown evidence tables, placing both on the Windows Clipboard simultaneously via `QMimeData` (`Ctrl+Shift+T`), and exporting standalone `.html` reports (`Ctrl+S`) for live, batch, and historical runs. | Preserved verbatim in `src/guideit_master/psstore/services/report_service.py`. |
| **Global `Win+F8` Hotkey, Windows Startup & System Tray** | `services/hotkey_service.py`, `services/startup_service.py`, `launcher_view.py` | `GlobalHotkeyManager` (`RegisterHotKey` `Win+F8` + `_NativeHotkeyEventFilter` `WM_HOTKEY` + `bring_window_to_foreground`); `StartupService` (`HKCU\...\Run` with `pythonw.exe` or frozen `.exe --startup`); `QSystemTrayIcon` (`>_` icon, context menu, minimize-to-tray on close, `--startup`/`--minimized`/`--tray` flags). | Hosted at the unified shell window level (`UnifiedShellWindow`) using `src/guideit_master/psstore/services/hotkey_service.py` & `startup_service.py` so `Win+F8` and system tray control the entire unified workstation. |
| **3-Pane Script Workstation UI & Cyber-Aurora Visual FX** | `ui/launcher_view.py`, `sidebar_view.py`, `catalog_table_view.py`, `parameter_form.py`, `console_view.py`, `styles.py`, `backdrop_fx.py`, `effects.py`, `tooltip_fx.py` | Collapsible `SidebarView` (`Ctrl+B`, search `Ctrl+F`, category list, risk/edition combos, sync `F5`, startup checkbox, `Win+F8` badge); `CatalogTableView` (3 columns `Title`/`Risk Level`/`Admin`, clickable natural alphanumeric/risk/admin header sorting, persistent checkboxes across filters, `☑ Check All` `Ctrl+Shift+A`, `☑ Read-Only` `Ctrl+Shift+O`, `☐ Clear` `Ctrl+Shift+D`, `📂 Scripts Folder` `Ctrl+O`); `ParameterFormWidget` (typed `string`/`int`/`bool` inputs, per-script `_saved_params` memory, `↺ Reset Defaults` `Ctrl+Alt+R`); `ConsoleView` (`Structured Results` `Ctrl+1`, `Raw Console` `Ctrl+2` + `Ctrl+L`, `Script Source` `Ctrl+3`, `Run History` `Ctrl+4` double-click reload); remediation confirmation & UAC dialogs; opacity slider (`60%–100%`, `Ctrl+=`/`Ctrl+-`/`Ctrl+0`); `BackdropFx`, `ButtonFx`, `GlowItemDelegate`, and `RainbowTooltip`. | Embedded in `src/guideit_master/psstore/ui/` and shared UI effects (`backdrop_fx.py`, `effects.py`, `tooltip_fx.py`), preserving all 24 shortcuts, tooltips, and visual effects. |
| **Static & PS 5.1 AST Linter & Pytest Suite** | `tools/lint_scripts.py`, `tests/test_*.py` (11 files, 54 tests), `_old_agents/skills/powershell-script-authoring` | 8-point `.PSSTORE_META` + PowerShell 5.1 `Parser::ParseFile` batch AST linter; 54 unit/UI/batch/FX tests; `powershell-script-authoring` skill. | Linter at `tools/lint_scripts.py`; all 11 test files migrated to `tests/psstore/`; skill unified under `.agents/skills/powershell-script-authoring/`. |

---

## 3. Architectural Conflict Resolution Decisions

### 3.1 Resolving the `scripts/` Folder Collision
- **Conflict:** `_ref_GuideIT/scripts/` contains 4 Python CLI entrypoints (`validate.py`, `build_index.py`, `search.py`, `launch_gui.py`), whereas `_ref_PowerShellStore/scripts/` contains the 6 numbered subfolders of 38 production `.ps1` files (`01_System`..`99_Custom`) plus `_ref_PowerShellStore/tools/lint_scripts.py`.
- **Decision:**
  1. **`powershell_scripts/` (Root Asset Directory):** Houses the 6 numbered PowerShell category folders (`01_System/`, `02_Network/`, `03_M365/`, `04_Devices/`, `05_Security_Defender/`, `99_Custom/`) and `README.md`. All path references in `ScriptScanner`, `ClipboardService`, `ScriptRunner`, and `lint_scripts.py` resolve this directory dynamically via `paths.get_ps_scripts_dir()` (with constructor override `scripts_dir: Path | None = None` retained for unit tests).
  2. **`tools/` (Root CLI & Developer Utilities Directory):** Consolidates all Python CLI scripts in one place:
     - `tools/lint_scripts.py` (PowerShell `.PSSTORE_META` & PS 5.1 AST contract linter)
     - `tools/validate_playbooks.py` (GuideIT schema, PII/redaction, and cross-link validator CLI — replaces `_ref_GuideIT/scripts/validate.py`)
     - `tools/build_index.py` (GuideIT + unified SQLite FTS5 index builder CLI — replaces `_ref_GuideIT/scripts/build_index.py`)
     - `tools/search_cli.py` (Unified EN/FR playbook & PowerShell script search CLI — replaces `_ref_GuideIT/scripts/search.py`)

### 3.2 Consolidating Dependencies (`pyproject.toml`, `requirements.txt`, `.gitignore`)
- **Conflict:** `_ref_GuideIT` uses `pyproject.toml` (`requires-python = ">=3.11"`, optional `PySide6>=6.7`, `pytest>=8.0`), while `_ref_PowerShellStore` uses `requirements.txt` (`PySide6>=6.8.0`, `shiboken6>=6.8.0`, `pytest>=8.0.0`).
- **Decision:**
  - **Single Root `pyproject.toml`:**
    - Package name: `guideit-master` (`version = "1.0.0"`, `requires-python = ">=3.11"`).
    - Core runtime dependencies: `PySide6>=6.8.0`, `shiboken6>=6.8.0`.
    - Optional dependencies: `dev = ["pytest>=8.0.0", "pyinstaller>=6.0"]`.
    - Entrypoints (`[project.scripts]`): `guideit-master = "guideit_master.main:main"`.
    - Pytest config (`[tool.pytest.ini_options]`): `pythonpath = ["src", "."]`, `testpaths = ["tests"]`.
  - **Single Root `requirements.txt`:** Mirrors `PySide6>=6.8.0`, `shiboken6>=6.8.0`, `pytest>=8.0.0`, `pyinstaller>=6.0` for `pip install -r requirements.txt` workflows.
  - **Single Root `.gitignore`:** Ignores runtime SQLite databases (`data/*.db`, `data/*.db-*`, `index/*.db`, `index/*.db-*`), virtual environments (`.venv/`, `venv/`), Python bytecode (`__pycache__/`, `*.py[cod]`), build/PyInstaller outputs (`build/`, `dist/`, `*.egg-info/`), caches (`.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`), and OS files (`desktop.ini`, `Thumbs.db`, `.DS_Store`), while keeping `_ref_GuideIT/` and `_ref_PowerShellStore/` untouched.
  - **No Legacy Top-Level Shims:** All application code and tests use clean `guideit_master.*` package imports directly—never creating top-level shim packages (`src/guideit/`, `src/repositories/`, `src/services/`, `src/ui/`), avoiding double-module imports and PyInstaller edge cases.

### 3.3 Single `QApplication`, Unified Shell Window & Split View Without Reparenting
- **Conflict:** Both reference projects instantiate their own `QApplication`, apply global stylesheets (`apply_dark_theme` vs. `DARK_THEME_QSS` + `install_button_fx` + `install_tooltip_fx`), own system tray / hotkeys / opacity controls, and bind overlapping shortcuts (`F5`, `Escape`, search focus).
- **Decision — Single `QApplication` & `UnifiedShellWindow` (`src/guideit_master/ui/shell_window.py`):**
  1. **Split View (`Alt+3`) Without Reparenting:**
     - `UnifiedShellWindow` hosts `PlaybooksWorkspaceWidget` and `ScriptsWorkspaceWidget` permanently inside **one top-level `QSplitter` (`mode_splitter`)**.
     - Each workspace widget exposes `set_compact_mode(bool)`:
       - **`📘 Playbooks` (`Alt+1`):** Shows `PlaybooksWorkspaceWidget` (`set_compact_mode(False)`), hides `ScriptsWorkspaceWidget`.
       - **`⚡ Scripts` (`Alt+2`):** Hides `PlaybooksWorkspaceWidget`, shows `ScriptsWorkspaceWidget` (`set_compact_mode(False)`).
       - **`🔀 Split View` (`Alt+3`):** Shows both inside the permanent `mode_splitter` with `set_compact_mode(True)` on each—hiding sidebars and catalog/results lists so the Playbook Viewer sits cleanly beside the live Script Inspector/Parameter Form/Console without ever reparenting widgets or instantiating duplicate `ScriptRunner` or `CatalogRepo` instances.
  2. **Single Owner for Shell Services:**
     - `ScriptsWorkspaceWidget` (`launcher_view.py`) is a pure `QWidget` (not `QMainWindow`) with `QSystemTrayIcon`, `closeEvent` minimize-to-tray, window opacity slider, `StartupService`, and `GlobalHotkeyManager` (`Win+F8`) removed.
     - **ONLY `UnifiedShellWindow`** owns `QSystemTrayIcon`, `closeEvent` minimize-to-tray, the **60%–100% Window Opacity Slider**, `StartupService`, and `GlobalHotkeyManager` (`Win+F8`), preventing duplicate tray icons or OS hotkey collisions.
  3. **Unified Global Shell Header Bar:**
     - **Left Brand & Mode Switcher:** Segmented `Playbooks (Alt+1)` / `Scripts (Alt+2)` / `Split View (Alt+3)` buttons.
     - **Center Unified Omnibox Search (`Ctrl+K`)** *(Phase 2/3)*: Queries both playbooks and scripts (`scripts_fts`) with EN/FR symptom expansion.
     - **Right Shell Controls:** `Useful Tools (Ctrl+T)` and `Valid` health pill *(Phase 2)*, **Window Opacity Slider (`60%–100%`, `Ctrl+=`/`Ctrl+-`/`Ctrl+0`)**, and **`Win+F8` Hotkey Badge**.
  4. **Context-Aware Keyboard Shortcut Routing:**
     - Global OS Hotkey: `Win+F8` toggles visibility of `UnifiedShellWindow`.
     - App-wide shortcuts: `Alt+1` (Playbooks mode), `Alt+2` (Scripts mode), `Alt+3` (Split View mode), `Ctrl+K` (Unified/Playbook search in Phase 2), `Ctrl+F` (Script catalog filter), `Ctrl+T` (Useful Tools dialog in Phase 2), `F5` (Sync scripts & re-index playbooks), `Ctrl+=`/`Ctrl+-`/`Ctrl+0` (Opacity), `Ctrl+Q` (Quit application).
     - Playbook-scoped (`Ctrl+R`, `Alt+Left`) and Script-scoped (`Ctrl+B`, `Ctrl+O`, `Ctrl+Shift+A/O/D`, `Ctrl+Shift+C/R`, `Ctrl+Enter`/`Ctrl+Return`, `Shift+F5`, `Ctrl+Alt+R`, `Ctrl+1..4`, `Ctrl+Shift+T`, `Ctrl+S`, `Ctrl+L`) shortcuts remain active and conflict-free.
  5. **Harmonized Dark & Frosted-Glass Theme:**
     - Combines PowerShellStore's `BackdropFx`, `ButtonFx`, `GlowItemDelegate`, and `RainbowTooltip` with GuideIT's scoped `#objectName` card selectors (`#headerCard`, `#sectionCard`, `#remediationSectionCard`, `#codeCard`, `#remediationCodeCard`, `#tierPill`, `#relatedPill`, `#codeChip`, `#healthPill`) so both modules render with 100% visual fidelity.

### 3.4 Strict Layer Boundaries & Decoupled Qt Signal Event Bus
- **Requirement:** UI widgets must never import `sqlite3`, `subprocess`, or `hashlib` directly, and the GuideIT UI module and PowerShellStore UI module must **never cross-import each other's UI widgets**.
- **Decision:**
  1. **Strict 3-Tier Layering per Module:**
     ```text
     ui/ (PySide6 Widgets & Views ONLY — zero sqlite3 / subprocess / hashlib imports)
       ↓ communicates via typed dataclasses & Qt Signals
     services/ (Scanner, Runner, Clipboard, Report, Validator, Taxonomy, UnifiedSearch, EventBus)
       ↓
     repositories/ (CatalogRepo, PlaybookRepo / FTS5 Indexer — owns all sqlite3 connections)
     ```
     *Note:* In `_ref_GuideIT/src/guideit/ui/main_window.py`, `_ensure_index_exists()` and `_query_db_stats()` previously used `sqlite3` directly. In the unified architecture, those two queries are moved cleanly into `src/guideit_master/guideit/search.py` (`ensure_index_current()` and `get_domain_and_subcategory_counts()`), achieving **100% `sqlite3`-free `ui/` code across both GuideIT and PowerShellStore** (enforced by automated AST/regex boundary tests).
  2. **Lightweight Qt Signal Event Bus (`src/guideit_master/core/event_bus.py`):**
     - `AppEventBus(QObject)` defines typed cross-module signals:
       - `open_script_requested = Signal(str, dict, bool)` — `(script_id_or_relpath, param_overrides, open_in_split_view)` emitted by GuideIT's `PlaybookViewer` when a technician clicks a linked PowerShell script action card (`Open in Workstation` or `Split View & Run`).
       - `copy_script_requested = Signal(str, dict, bool)` — `(script_id_or_relpath, param_overrides, rmm_ready)` emitted by GuideIT's `PlaybookViewer` when a technician clicks `⚡ Copy RMM-Ready` or `📋 Copy Raw` directly on a playbook's linked script card.
       - `run_script_requested = Signal(str, dict)` — `(script_id_or_relpath, param_overrides)` emitted when a technician clicks `▶ Test Locally` from a playbook card (switches to Split View and invokes PowerShellStore's safety-gated execution flow).
       - `open_playbook_requested = Signal(str, bool)` — `(playbook_id, open_in_split_view)` emitted by PowerShellStore's `InspectorFrame` when a technician clicks a reverse `"Used in Playbooks: [prt-001]"` badge.
       - `catalog_synced = Signal()` / `playbooks_reindexed = Signal()` — notifies the shell and cross-reference caches when either library refreshes.
       - `status_toast_requested = Signal(str, int)` — displays unified status bar feedback.
     - `UnifiedShellWindow` wires `AppEventBus` between `PlaybooksWorkspaceWidget` and `ScriptsWorkspaceWidget`. Neither module ever imports the other's UI classes.

---

## 4. Deep Linking & Unified Search Architecture

### 4.1 Playbook-to-Script Frontmatter Schema (`linked_scripts`)
- **`taxonomy/schema.json` Extension:** Add `"linked_scripts"` to `optional_fields` in `taxonomy/schema.json` and `linked_scripts: list[str]` to the `Playbook` dataclass (`models.py`) and `playbooks` SQLite table (`linked_scripts_json TEXT NOT NULL DEFAULT '[]'`).
- **Canonical Script Identifier Format (Strict):** Each entry in `linked_scripts` MUST be the exact `NN_Category/Verb-Noun.ps1` relative path inside `powershell_scripts/` (e.g., `"04_Devices/Reset-PrintSpooler.ps1"`, `"04_Devices/Get-PrintQueues.ps1"`). Filename-only values without the numbered category folder are forbidden and rejected by the validator.
- **Example Frontmatter (`playbooks/05_Printers_Devices/prt-001-spooler-and-0x0000011b.md`):**
  ```yaml
  related_ids: [net-001, srv-012, win-001, net-004]
  linked_scripts:
    - 04_Devices/Get-PrintQueues.ps1
    - 04_Devices/Reset-PrintSpooler.ps1
    - 01_System/Get-RecentEventErrors.ps1
  ```
- **Inline Markdown Deep Links (`psstore://` URI scheme):** Playbook Markdown bodies can also reference scripts inline via `[Reset-PrintSpooler.ps1](psstore://04_Devices/Reset-PrintSpooler.ps1?ClearQueueFiles=true)`, which `markdown_blocks.py` renders as an interactive cyan/violet action pill that emits `open_script_requested` with parsed query parameters!
- **Curated Initial Cross-Link Mapping across Seed Playbooks:**
  - `prt-001` (Print Spooler) ↔ `04_Devices/Get-PrintQueues.ps1`, `04_Devices/Reset-PrintSpooler.ps1`
  - `prt-003` (USB-C Dock Monitors) ↔ `04_Devices/Get-DisplayTopology.ps1`, `04_Devices/Get-DeviceDrivers.ps1`, `04_Devices/Get-ProblemDevices.ps1`
  - `win-001` (Windows Update Corruption) ↔ `01_System/Get-PendingRebootStatus.ps1`, `01_System/Update-Windows.ps1`, `01_System/Invoke-DeepSystemCleanup.ps1`
  - `win-002` (BitLocker Recovery) ↔ `05_Security_Defender/Get-BitLockerStatus.ps1`
  - `win-003` (BSOD & Driver Triage) ↔ `01_System/Get-SystemCrashHistory.ps1`, `04_Devices/Get-DeviceDrivers.ps1`, `04_Devices/Get-ProblemDevices.ps1`
  - `win-006` (High CPU / Disk / Memory) ↔ `01_System/Get-HighResourceProcesses.ps1`, `01_System/Get-DiskSpaceReport.ps1`, `01_System/Get-RecentEventErrors.ps1`
  - `win-007` (Audio / Webcam / Mic) ↔ `04_Devices/Get-ProblemDevices.ps1`, `04_Devices/Get-DeviceDrivers.ps1`, `04_Devices/Update-DeviceDrivers.ps1`
  - `win-008` (Windows Activation) ↔ `01_System/Get-OSInformation.ps1`, `03_M365/Get-OfficeActivationStatus.ps1`
  - `net-001` (No Internet / APIPA / DNS) ↔ `02_Network/Get-NetworkSnapshot.ps1`, `02_Network/Test-PortConnectivity.ps1`, `02_Network/Reset-NetworkStack.ps1`
  - `net-002` (Wi-Fi Drops) ↔ `02_Network/Get-WiFiDiagnostics.ps1`, `02_Network/Get-NetworkSnapshot.ps1`
  - `net-003` (Teams / VoIP Jitter) ↔ `02_Network/Test-NetworkQuality.ps1`, `02_Network/Get-WiFiDiagnostics.ps1`
  - `m365-001` (Outlook Auth Loop) ↔ `03_M365/Get-EntraRegistrationStatus.ps1`, `03_M365/Get-OfficeActivationStatus.ps1`, `03_M365/Clear-OutlookCache.ps1`
  - `m365-005` (OneDrive Sync Stuck) ↔ `03_M365/Reset-OneDriveSync.ps1`
  - `id-001` (Account Lockout) ↔ `05_Security_Defender/Get-LocalAccountStatus.ps1`, `01_System/Get-RecentEventErrors.ps1`
  - `id-005` (Domain Trust Failed) ↔ `03_M365/Get-EntraRegistrationStatus.ps1`, `01_System/Get-OSInformation.ps1`
  - `sec-002` (Defender ASR / False Positive) ↔ `05_Security_Defender/Get-DefenderStatus.ps1`, `05_Security_Defender/Invoke-DefenderUpdateAndScan.ps1`
  - `sec-003` (TLS/SSL Certificate Expired) ↔ `05_Security_Defender/Get-ExpiringCertificates.ps1`
  - `srv-001` (Server Disk & VSS) ↔ `01_System/Get-DiskSpaceReport.ps1`, `01_System/Invoke-DeepSystemCleanup.ps1`
  - `app-001` (Browser SSO Loop) ↔ `03_M365/Clear-BrowserCache.ps1`, `03_M365/Get-EntraRegistrationStatus.ps1`
  - `app-002` (Office Add-ins Freeze) ↔ `03_M365/Get-OutlookAddins.ps1`, `03_M365/Clear-OutlookCache.ps1`

### 4.2 Interactive Linked Script Action Cards in `PlaybookViewer`
When a playbook defines `linked_scripts`, `PlaybookViewer` renders a dedicated **`⚡ Linked Diagnostic & Remediation Scripts`** card section (and header quick-pills) displaying each linked script's:
- **Title, Category badge, Risk badge (`READ-ONLY` green vs. `REMEDIATION` amber), `Requires Admin` badge, and Synopsis**.
- **Four 1-Click Technician Actions:**
  1. **`⚡ Copy RMM-Ready`** — Copies the script with default (or overridden) parameters injected via `AppEventBus.copy_script_requested`.
  2. **`📋 Copy Raw`** — Copies the unmodified `.ps1` script from disk.
  3. **`🔧 Open in Script Workstation`** — Emits `AppEventBus.open_script_requested(rel_path, params, False)` to switch to the Scripts view with that script selected and its dynamic `ParameterFormWidget` preloaded.
  4. **`🔀 Open Side-by-Side (Split View)`** — Emits `AppEventBus.open_script_requested(rel_path, params, True)` so the technician keeps reading the playbook on the left while configuring/running the script on the right.

### 4.3 Reverse `"Used in Playbooks"` References in PowerShellStore
- `CrossLinkService` queries `guideit.db` to build a reverse map `{script_relative_path: list[PlaybookSummary]}`.
- In PowerShellStore's `InspectorFrame` (right workstation pane), right below the script's category/risk/admin chips, a **`📘 Used in Playbooks:`** flow row renders clickable `[prt-001]`, `[win-003]` pills (with full playbook title tooltips).
- Clicking any playbook pill emits `AppEventBus.open_playbook_requested(playbook_id, split_view)`—jumping directly to that playbook (or opening it side-by-side in Split View if `Shift`-clicked or via context button).

### 4.4 Unified Bilingual FTS5 Search Across Playbooks & Scripts
- **PowerShell FTS5 Virtual Table (`scripts_fts`):** `CatalogRepo.init_db()` adds an FTS5 virtual table `scripts_fts(relative_path, title, category, synopsis, filename, params_text, tokenize = "unicode61 remove_diacritics 2")` kept in sync during `upsert_script()` and `delete_missing_scripts()`.
- **Unified Search Service (`src/guideit_master/services/unified_search.py`):**
  - Accepts a raw EN/FR query (e.g., `"spooler 0x0000011b"`, `"compte verrouillé"`, `"bitlocker"`, `"onedrive bloque"`).
  - Runs `expand_query(query, taxonomy)` from GuideIT's `taxonomy/keyword_map.json` to obtain canonical `expanded_tags`, `suggested_domains`, and `error_codes`.
  - Queries `guideit.db` (`search_playbooks`) AND `powershell_store.db` (`scripts_fts` + tag/keyword token expansion, plus boosting any script that is in `linked_scripts` of top-matching playbooks!).
  - Returns a `UnifiedSearchResponse` containing ranked `playbook_hits: list[SearchHit]` and ranked `script_hits: list[ScriptSearchHit]`, powering both the top omnibox dropdown and cross-module search badges.

### 4.5 Broken Cross-Link Validator
- `validate_repository()` in `validator.py` inspects `linked_scripts` and `psstore://` inline links in every playbook against the real `powershell_scripts/` directory (via `paths.get_ps_scripts_dir()`).
- Emits `ValidationIssue(severity="error", code="BROKEN_LINKED_SCRIPT", ...)` if any referenced `.ps1` file does not exist on disk, ensuring `python tools/validate_playbooks.py --strict` and the UI Health Pill catch broken script links immediately.

---

## 5. PyInstaller-Ready Centralized Path Resolver (`src/guideit_master/paths.py`)

To ensure standalone `.exe` packaging (`PyInstaller` `--onedir` or `--onefile`) works from Day 1 without writing SQLite files or logs into a read-only `Program Files` or ephemeral `_MEIPASS` extraction directory, all modules resolve paths exclusively through `src/guideit_master/paths.py`:

```python
"""Centralized PyInstaller-aware path resolver for GuideIT Master."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "GuideIT_Master"
ENV_BUNDLE_DIR = "GUIDEIT_BUNDLE_DIR"
ENV_DATA_DIR = "GUIDEIT_DATA_DIR"


def is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def get_bundle_dir() -> Path:
    """Return the root directory containing read-only bundled assets.

    Order of precedence:
    1. GUIDEIT_BUNDLE_DIR environment variable (for tests/CLI overrides).
    2. sys._MEIPASS when frozen by PyInstaller.
    3. Repository root directory (parent of src/) during source execution.
    """
    env_override = os.environ.get(ENV_BUNDLE_DIR)
    if env_override:
        return Path(env_override).resolve()
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def get_user_data_dir() -> Path:
    """Return the writable directory for SQLite databases, logs, and user custom scripts.

    Order of precedence:
    1. GUIDEIT_DATA_DIR environment variable (for isolated pytest tmp_path runs).
    2. %LOCALAPPDATA%\\GuideIT_Master when frozen as a packaged Windows executable.
    3. <repo_root>\\data during local developer execution.
    """
    env_override = os.environ.get(ENV_DATA_DIR)
    if env_override:
        path = Path(env_override).resolve()
    elif is_frozen():
        local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = (Path(local_app_data) / APP_NAME).resolve()
    else:
        path = (get_bundle_dir() / "data").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- Read-Only Bundled Assets ---
def get_playbooks_dir(root_dir: Path | None = None) -> Path:
    return ((root_dir or get_bundle_dir()) / "playbooks").resolve()


def get_taxonomy_dir(root_dir: Path | None = None) -> Path:
    return ((root_dir or get_bundle_dir()) / "taxonomy").resolve()


def get_templates_dir(root_dir: Path | None = None) -> Path:
    return ((root_dir or get_bundle_dir()) / "templates").resolve()


def get_ps_scripts_dir(root_dir: Path | None = None) -> Path:
    return ((root_dir or get_bundle_dir()) / "powershell_scripts").resolve()


# --- Writable Local User Data ---
def get_guideit_db_path(data_dir: Path | None = None) -> Path:
    return ((data_dir or get_user_data_dir()) / "guideit.db").resolve()


def get_psstore_db_path(data_dir: Path | None = None) -> Path:
    return ((data_dir or get_user_data_dir()) / "powershell_store.db").resolve()


def get_user_custom_scripts_dir(data_dir: Path | None = None) -> Path:
    custom_dir = ((data_dir or get_user_data_dir()) / "user_scripts").resolve()
    custom_dir.mkdir(parents=True, exist_ok=True)
    return custom_dir


def get_logs_dir(data_dir: Path | None = None) -> Path:
    logs_dir = ((data_dir or get_user_data_dir()) / "logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir
```

- **`StartupService` PyInstaller Compatibility:** `StartupService.get_launch_command()` checks `paths.is_frozen()`: when frozen, it registers `'"<sys.executable>" --startup'`; when running from source, it registers `'"<pythonw.exe>" "<root>/main.py" --startup'`.

---

## 6. Proposed Unified Folder Tree

```text
GuideIT_Master/
├── _ref_GuideIT/                       # [STRICTLY READ-ONLY REFERENCE — NEVER MODIFIED]
├── _ref_PowerShellStore/               # [STRICTLY READ-ONLY REFERENCE — NEVER MODIFIED]
├── GEMINI.md                           # Unified Antigravity workspace architecture & coding contract
├── MERGE_PLAN.md                       # This architecture audit & 4-phase build plan
├── README.md                           # Unified documentation, 38-script catalog, 65-playbook matrix & shortcuts
├── SKILLS.md                           # PowerShell 5.1 (.PSSTORE_META) & Playbook authoring contract
├── pyproject.toml                      # Unified package config, dependencies & pytest settings
├── requirements.txt                    # Pip dependency lock (PySide6, shiboken6, pytest, pyinstaller)
├── .gitignore                          # Unified gitignore (data/*.db, index/*.db, build/, dist/, .venv/)
├── main.py                             # Root desktop application entrypoint (--startup / --minimized / --tray)
├── build.ps1                           # Phase 4 PyInstaller packaging & verification script
├── guideit_master.spec                 # Phase 4 PyInstaller specification bundling playbooks/, powershell_scripts/, taxonomy/
│
├── .agents/
│   └── skills/                         # Unified Antigravity workspace skills
│       ├── triage-ticket/SKILL.md
│       ├── new-playbook/SKILL.md
│       ├── audit-library/SKILL.md
│       └── powershell-script-authoring/SKILL.md
│
├── taxonomy/                           # Read-only bundled GuideIT taxonomy & external tools JSONs
│   ├── domains.json                    # 9 canonical domains (01..09) & 23 subcategories
│   ├── schema.json                     # Playbook schema (including optional linked_scripts) & redaction rules
│   ├── keyword_map.json                # Bilingual EN/FR user symptom -> canonical tag & error code map
│   └── resources.json                  # 31+ curated MSP & Data Center websites & lookup instructions
│
├── templates/
│   └── playbook-template.md            # Canonical L1–L3 playbook template (with linked_scripts)
│
├── docs/
│   └── TROUBLESHOOTING_MATRIX.md       # Inter-subject troubleshooting matrix & Mermaid pivot flowchart
│
├── playbooks/                          # Read-only bundled 65 L1–L3 Markdown playbooks
│   ├── 01_Identity_AD_Entra/           # id-001 .. id-008
│   ├── 02_M365_Email_Collab/           # m365-001 .. m365-008
│   ├── 03_Windows_Endpoints/           # win-001 .. win-008
│   ├── 04_Network_VPN_VoIP/            # net-001 .. net-005
│   ├── 05_Printers_Devices/            # prt-001 .. prt-004
│   ├── 06_Security_Access/             # sec-001 .. sec-004
│   ├── 07_macOS_Mobile_MDM/            # mdm-001 .. mdm-008
│   ├── 08_Servers_Cloud_Infra/         # srv-001 .. srv-016
│   └── 09_Apps_LOB/                    # app-001 .. app-004
│
├── powershell_scripts/                 # Read-only bundled 38 PowerShell 5.1 scripts (File-First Source of Truth)
│   ├── README.md
│   ├── 01_System/                      # 11 scripts
│   ├── 02_Network/                     # 6 scripts
│   ├── 03_M365/                        # 7 scripts
│   ├── 04_Devices/                     # 6 scripts
│   ├── 05_Security_Defender/           # 7 scripts
│   └── 99_Custom/                      # 1 script
│
├── data/                               # Writable local runtime data (gitignored)
│   ├── guideit.db                      # Generated SQLite FTS5 playbook index
│   ├── powershell_store.db             # Generated SQLite script catalog, FTS5 & run_history DB
│   ├── user_scripts/                   # Reserved in paths.py (Phase 1); optional overlay scanning in Phase 4
│   └── logs/                           # Application diagnostic logs
│
├── tools/                              # Unified CLI entrypoints & developer linters
│   ├── lint_scripts.py                 # Static & PowerShell 5.1 AST contract linter
│   ├── validate_playbooks.py           # Playbook schema, PII redaction & linked_scripts validator CLI
│   ├── build_index.py                  # Atomic SQLite FTS5 index builder CLI
│   └── search_cli.py                   # Bilingual EN/FR playbook & script FTS5 search CLI
│
├── src/
│   ├── guideit_master/                 # Primary unified application package
│   │   ├── __init__.py
│   │   ├── main.py                     # QApplication bootstrap, theme/FX install & CLI flag handling
│   │   ├── paths.py                    # PyInstaller-aware path resolver (bundle vs. writable user data)
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   └── event_bus.py            # Lightweight Qt Signal event bus decoupling GuideIT & PSStore UIs
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── cross_link_service.py   # Bidirectional Playbook <-> Script resolution & reverse lookup
│   │   │   └── unified_search.py       # Bilingual FTS5 search across playbooks_fts and scripts_fts
│   │   ├── ui/
│   │   │   ├── __init__.py
│   │   │   ├── shell_window.py         # UnifiedShellWindow (Playbooks | Scripts | Split View, Omnibox, Tray)
│   │   │   ├── unified_theme.py        # Combined Dark + Frosted Glass QSS & palette
│   │   │   ├── backdrop_fx.py          # Animated cyber-aurora canvas & cursor-reactive glass overlays
│   │   │   ├── effects.py              # 60fps button rainbow glow/shine/ripple & GlowItemDelegate
│   │   │   └── tooltip_fx.py           # Animated dynamic-rainbow text & aurora tooltip popup
│   │   ├── psstore/                    # PowerShellStore module (100% feature parity)
│   │   │   ├── __init__.py
│   │   │   ├── repositories/
│   │   │   │   ├── __init__.py
│   │   │   │   └── catalog_repo.py     # SQLite scripts, scripts_fts & run_history persistence
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── scanner.py          # .PSSTORE_META parser & SHA-256 catalog sync
│   │   │   │   ├── clipboard_service.py# Raw & RMM parameter-injected single/bundle clipboard service
│   │   │   │   ├── runner.py           # Non-blocking QProcess runner, batch queue & UAC elevation
│   │   │   │   ├── report_service.py   # Rich-text HTML + Markdown ticket audit report generator
│   │   │   │   ├── hotkey_service.py   # Global Win+F8 Win32 RegisterHotKey manager
│   │   │   │   └── startup_service.py  # Windows HKCU Run registry manager (source & frozen .exe aware)
│   │   │   └── ui/
│   │   │       ├── __init__.py
│   │   │       ├── launcher_view.py    # ScriptsWorkspaceWidget (pure QWidget 3-pane workstation + set_compact_mode)
│   │   │       ├── sidebar_view.py     # Categories, search, risk/edition filters, startup checkbox
│   │   │       ├── catalog_table_view.py # Checkable 3-column sortable table & batch toolbar
│   │   │       ├── parameter_form.py   # Dynamic typed parameter form with per-script value memory
│   │   │       └── console_view.py     # 4-tab console (Structured Results, Raw, Source, Run History)
│   │   └── guideit/                    # GuideIT module (100% feature parity)
│   │       ├── __init__.py
│   │       ├── models.py               # Playbook (with linked_scripts), SearchHit, ValidationReport
│   │       ├── frontmatter.py          # Strict zero-dependency YAML frontmatter & section parser
│   │       ├── taxonomy.py             # Domains, subcategories, schema, and EN/FR query expansion
│   │       ├── validator.py            # Schema, section order, related_ids, linked_scripts & PII linter
│   │       ├── indexer.py              # Atomic SQLite FTS5 builder
│   │       ├── search.py               # Hybrid FTS5 BM25 + error code/tag/keyword boost engine
│   │       └── ui/
│   │           ├── __init__.py
│   │           ├── main_window.py      # PlaybooksWorkspaceWidget (3-pane playbook console + set_compact_mode)
│   │           ├── markdown_blocks.py  # Markdown prose, code blocks, client snippets & guideit:// / psstore:// links
│   │           ├── theme.py            # GuideIT color tokens & section accents
│   │           ├── workers.py          # Background ReindexWorker (QThread)
│   │           └── widgets/
│   │               ├── __init__.py
│   │               ├── filter_sidebar.py   # Tier pills, 2-level Subjects tree, OS/Env/Risk combos
│   │               ├── results_list.py     # Wrapping result cards & [NO PLAYBOOK MATCH] view
│   │               ├── playbook_viewer.py  # L1-L3 section cards, linked script action cards & snippets
│   │               ├── code_block.py       # Auto-wrapping syntax-highlighted command card with Copy
│   │               └── resources_dialog.py # Searchable Useful Websites & External Tools dialog (Ctrl+T)
│   │
│   │   # Note: Clean `guideit_master.*` imports are used everywhere (zero top-level compatibility shims).
│
└── tests/                              # Unified automated pytest suite (100% preserved + cross-link & E2E tests)
    ├── conftest.py                     # Shared session QApplication fixture & offscreen/cleanup hooks
    ├── test_paths.py                   # Phase 1: PyInstaller frozen vs. source path resolver tests
    ├── psstore/                        # Phase 1: All 11 PowerShellStore test modules (54+ tests)
    │   ├── test_phase1.py
    │   ├── test_phase2.py
    │   ├── test_phase3.py
    │   ├── test_phase4.py
    │   ├── test_batch_selection.py
    │   ├── test_shortcuts.py
    │   ├── test_report_service.py
    │   ├── test_startup_and_hotkey.py
    │   ├── test_backdrop_fx.py
    │   ├── test_effects.py
    │   └── test_tooltip_fx.py
    ├── guideit/                        # Phase 2: All 4 GuideIT test modules (90+ test cases)
    │   ├── test_frontmatter.py
    │   ├── test_search_and_index.py
    │   ├── test_validator.py
    │   └── test_ui.py
    ├── test_cross_linking.py           # Phase 3: Deep linking, reverse badges, unified search & broken-link validator tests
    └── test_e2e_unified.py             # Phase 4: End-to-end shell, Split View, layer boundaries & build spec audit tests
```

---

## 7. Four-Phase Incremental Build Roadmap

Every phase leaves the workspace in a **clean, runnable, test-passing state** while keeping `_ref_GuideIT/` and `_ref_PowerShellStore/` strictly untouched.

### Phase 1: Root Project Scaffolding, Unified `paths.py`, Shared Shell Window & Full PowerShellStore Module
**Goal:** Stand up the root `GuideIT_Master` packaging structure, centralized PyInstaller-aware path resolver, shared `UnifiedShellWindow` + `AppEventBus`, all 38 production `.ps1` scripts under `powershell_scripts/`, and the complete PowerShellStore module passing all migrated tests and static/AST script linting.

1. **Root Configuration & Documentation:**
   - Create root `pyproject.toml`, `requirements.txt`, `.gitignore`, `SKILLS.md`, and initial `README.md`.
2. **Centralized Path Resolver & Event Bus:**
   - Implement `src/guideit_master/paths.py` (`is_frozen()`, `get_bundle_dir()`, `get_user_data_dir()`, `get_ps_scripts_dir()`, `get_guideit_db_path()`, `get_psstore_db_path()`, `get_user_custom_scripts_dir()`, `get_logs_dir()`).
   - Keep `get_user_custom_scripts_dir()` reserved in `paths.py`; keep Phase 1 `ScriptScanner` and `CatalogRepo` focused cleanly on `paths.get_ps_scripts_dir()` (deferring optional `data/user_scripts/` overlay scanning to Phase 4).
   - Implement `src/guideit_master/core/event_bus.py` (`AppEventBus` QObject with decoupled navigation, copy, execution, and sync signals).
3. **Copy Bundled PowerShell Script Catalog (Read-Only Source → Root `powershell_scripts/`):**
   - Copy all 38 `.ps1` scripts across `01_System`..`99_Custom` and `README.md` from `_ref_PowerShellStore/scripts/` into `powershell_scripts/`.
4. **Embed Full PowerShellStore Module, Visual FX & Single-Owner Shell Window:**
   - Implement `src/guideit_master/psstore/repositories/catalog_repo.py` (using `paths.get_psstore_db_path()`).
   - Implement `src/guideit_master/psstore/services/` (`scanner.py`, `clipboard_service.py`, `runner.py`, `report_service.py`, `hotkey_service.py`, `startup_service.py`) wired strictly to `paths.get_ps_scripts_dir()`.
   - Implement `src/guideit_master/ui/` visual effects (`backdrop_fx.py`, `effects.py`, `tooltip_fx.py`, `unified_theme.py`) and `src/guideit_master/psstore/ui/` (`launcher_view.py` as pure `QWidget` `ScriptsWorkspaceWidget` with `set_compact_mode(bool)`, `sidebar_view.py`, `catalog_table_view.py`, `parameter_form.py`, `console_view.py`).
   - Use clean `guideit_master.*` imports across all application modules and migrated tests (no top-level legacy compatibility shims under `src/`).
   - Implement `src/guideit_master/ui/shell_window.py` (`UnifiedShellWindow`) as the **sole owner** of `QSystemTrayIcon`, `closeEvent` minimize-to-tray, window opacity slider, `StartupService`, and `GlobalHotkeyManager` (`Win+F8`), hosting a permanent `QSplitter` (`mode_splitter`) containing a Phase 1 `PlaybooksPlaceholderWidget` and `ScriptsWorkspaceWidget` with `Alt+1..3` mode switching and `set_compact_mode(True)` in Split View (zero reparenting, zero duplicate runners), plus root `main.py` and `tools/lint_scripts.py`.
5. **Phase 1 Verification Gate:**
   - Create `tests/conftest.py`, `tests/test_paths.py`, and migrate all 11 PowerShellStore test suites (plus shell tests) into `tests/psstore/`.
   - Run `python tools/lint_scripts.py` (must report `38/38 passed, 0 failed`).
   - Run `python -m pytest tests/test_paths.py tests/psstore/ -v` (100% pass).

---

### Phase 2: Full GuideIT Module Integration (Playbooks, Taxonomy, Bilingual FTS5 Search & Viewer UI)
**Goal:** Integrate all 65 Markdown playbooks, `taxonomy/*.json`, `templates/`, `docs/`, the zero-dependency GuideIT core (`frontmatter`, `taxonomy`, `validator`, `indexer`, `search`), CLI tools, and the 3-pane Dark Playbook UI into `UnifiedShellWindow`'s permanent `mode_splitter` with 100% test parity.

1. **Copy Bundled GuideIT Assets (Read-Only Source → Root Directories):**
   - Copy `playbooks/01_Identity_AD_Entra`..`09_Apps_LOB` (65 playbooks), `taxonomy/` (`domains.json`, `schema.json`, `keyword_map.json`, `resources.json`), `templates/playbook-template.md`, `docs/TROUBLESHOOTING_MATRIX.md`, and `.agents/skills/` from `_ref_GuideIT/` and `_ref_PowerShellStore/` to the root workspace.
2. **Integrate GuideIT Core & Strict Layer Boundary Cleanup:**
   - Implement `src/guideit_master/guideit/` (`models.py`, `frontmatter.py`, `taxonomy.py`, `validator.py`, `indexer.py`, `search.py`) using `paths.get_bundle_dir()` and `paths.get_guideit_db_path()`.
   - Move direct SQLite index-version check and domain/subcategory count queries out of `ui/main_window.py` into `search.py` (`ensure_index_current()` and `get_domain_and_subcategory_counts()`) so `guideit/ui/` has zero `sqlite3` imports.
   - Use clean `guideit_master.guideit.*` imports across all source modules, tools, and tests (no top-level `src/guideit/` compatibility shim).
3. **Integrate GuideIT 3-Pane UI & CLI Tools:**
   - Implement `src/guideit_master/guideit/ui/` (`main_window.py` as `PlaybooksWorkspaceWidget(QWidget)` implementing `set_compact_mode(bool)`, `markdown_blocks.py`, `theme.py`, `workers.py`, and `widgets/filter_sidebar.py`, `results_list.py`, `playbook_viewer.py`, `code_block.py`, `resources_dialog.py`).
   - Replace the Phase 1 placeholder widget inside `UnifiedShellWindow`'s permanent `mode_splitter` with `PlaybooksWorkspaceWidget` (Mode 0 `Alt+1`: Playbooks, Mode 1 `Alt+2`: Scripts, Mode 2 `Alt+3`: Split View with both workspaces in `set_compact_mode(True)`).
   - Implement `tools/validate_playbooks.py`, `tools/build_index.py`, and `tools/search_cli.py`.
4. **Phase 2 Verification Gate:**
   - Migrate all 4 GuideIT test suites into `tests/guideit/` using `guideit_master.guideit.*` imports.
   - Run `python tools/validate_playbooks.py --strict` (`Checked 65 playbook(s): 0 error(s), 0 warning(s)`).
   - Run `python tools/build_index.py` (`Indexed 65 playbook(s)`).
   - Run `python -m pytest tests/ -v` (all Phase 1 + Phase 2 tests must pass together in one unified pytest invocation).

---

### Phase 3: Bidirectional Cross-Linking, Action Cards, Reverse References & Unified FTS5 Search
**Goal:** Connect troubleshooting playbooks directly to diagnostic and remediation PowerShell scripts with strict `NN_Category/Verb-Noun.ps1` deep links, parameter preloading, Split-View execution, reverse `"Used in Playbooks"` pills, unified EN/FR FTS5 search, and broken-link validation.

1. **Schema, Frontmatter & Validator Extension (`linked_scripts`):**
   - Add `"linked_scripts"` to `optional_fields` in `taxonomy/schema.json` and `templates/playbook-template.md`, enforcing exact `NN_Category/Verb-Noun.ps1` relative paths (no filename-only fallback).
   - Extend `Playbook` and `SearchHit` dataclasses (`models.py`), `load_playbook_file()` (`validator.py`), `playbooks` SQLite table (`indexer.py`), and `get_playbook_by_id()` (`search.py`) with `linked_scripts: list[str]`.
   - Extend `validate_repository()` (`validator.py`) to reject malformed paths and verify every entry in `linked_scripts` (and every inline `psstore://NN_Category/Verb-Noun.ps1` Markdown link) exists in `powershell_scripts/`, emitting `BROKEN_LINKED_SCRIPT` on missing or non-canonical targets.
   - Populate curated `linked_scripts` across matching Windows/M365/Network/Printer/Security/Server playbooks in `playbooks/`.
2. **Cross-Link Service & Unified Bilingual FTS5 Search:**
   - Add `scripts_fts` FTS5 virtual table (`unicode61 remove_diacritics 2`) to `CatalogRepo` (`catalog_repo.py`).
   - Implement `src/guideit_master/services/cross_link_service.py` providing exact `NN_Category/Verb-Noun.ps1` lookup of `ScriptRecord` objects for a playbook's `linked_scripts` and reverse lookup of `Playbook` summaries for any script (`get_playbooks_for_script(relative_path)`).
   - Implement `src/guideit_master/services/unified_search.py` (`search_all(query, ...)`) combining EN/FR `keyword_map.json` expansion across both `playbooks_fts` and `scripts_fts`, and boosting scripts linked to matched playbooks.
3. **UI Deep-Linking via `AppEventBus` (Zero Cross-Imports):**
   - **In `PlaybookViewer` (`guideit/ui/widgets/playbook_viewer.py`):** Render the **`⚡ Linked PowerShell Scripts`** section card and header pills for any playbook with `linked_scripts`, featuring `⚡ Copy RMM-Ready`, `📋 Copy Raw`, `🔧 Open in Workstation`, and `🔀 Split View & Run` buttons that emit `AppEventBus` signals, plus support for inline `psstore://NN_Category/Verb-Noun.ps1?Param=Value` links.
   - **In `ScriptsWorkspaceWidget` (`psstore/ui/launcher_view.py`):** Render the **`📘 Used in Playbooks:`** badge row in `InspectorFrame` with clickable `[playbook-id]` pills that emit `AppEventBus.open_playbook_requested`, plus a public `select_and_preload_script(relative_path, param_overrides)` slot wired by `UnifiedShellWindow`.
   - **In `UnifiedShellWindow` (`ui/shell_window.py`):** Wire `AppEventBus` signals between the Playbooks and Scripts workspaces inside `mode_splitter`, automatically toggling `Alt+3` Split View (`set_compact_mode(True)`) when a technician launches a side-by-side script test from a playbook without reparenting widgets.
4. **Phase 3 Verification Gate:**
   - Create `tests/test_cross_linking.py` covering strict `NN_Category/Verb-Noun.ps1` `linked_scripts` parsing/indexing, `BROKEN_LINKED_SCRIPT` validation (including rejecting bare filenames), one-click Playbook → Script preloading (with custom parameter overrides), 1-click RMM/Raw copy from a playbook card, reverse Script → Playbook navigation, Split View activation without reparenting, and unified EN/FR search returning both playbooks and scripts.
   - Run `python tools/validate_playbooks.py --strict`, `python tools/lint_scripts.py`, and `python -m pytest tests/ -v` (100% pass).

---

### Phase 4: Dual-Root User Scripts Overlay, End-to-End Verification & Cross-PS Build Pipeline (`build.ps1`)
**Goal:** Add optional `data/user_scripts/` custom script overlay scanning, complete end-to-end architectural and layer-boundary verification, comprehensive documentation synchronization, and a reproducible PyInstaller packaging pipeline (`guideit_master.spec` + `build.ps1`) compatible with both Windows PowerShell 5.1 and PowerShell 7.

1. **Optional `data/user_scripts/` Overlay Scanning:**
   - Extend `ScriptScanner` and `CatalogRepo` to optionally scan `paths.get_user_custom_scripts_dir()` alongside `paths.get_ps_scripts_dir()` with explicit source precedence rules (`user` vs. `bundled`).
2. **PyInstaller Specification & Dual-Shell Build Pipeline:**
   - Author `guideit_master.spec` bundling read-only data directories (`playbooks/`, `powershell_scripts/`, `taxonomy/`, `templates/`, `docs/`) while excluding runtime `data/*.db` and `_ref_*/`.
   - Author `build.ps1` using clean PowerShell 5.1-safe syntax (no PS 7-only operators `? :`, `??`, `&&`, `||`) supporting `-VerifyOnly` (validates playbooks, lints PowerShell scripts, runs pytest, and audits PyInstaller spec data paths) and full `-Package` mode (builds `dist/GuideIT_Master/GuideIT_Master.exe` and smoke-tests frozen path resolution) under both `powershell.exe` 5.1 and `pwsh` 7+.
3. **End-to-End & Architectural Boundary Test Suite (`tests/test_e2e_unified.py`):**
   - Verify **strict layer boundary enforcement**: zero `sqlite3`, `subprocess`, or `hashlib` imports anywhere in `src/guideit_master/ui/`, `src/guideit_master/guideit/ui/`, or `src/guideit_master/psstore/ui/`.
   - Verify **strict module decoupling**: `guideit_master.guideit.ui` never imports `guideit_master.psstore.ui` and vice versa, and zero top-level legacy shim packages exist in `src/`.
   - Verify **read-only reference integrity**: `_ref_GuideIT/` and `_ref_PowerShellStore/` remain completely unmodified.
   - Verify **frozen PyInstaller mode simulation** (`monkeypatch` `sys.frozen = True` and `sys._MEIPASS`): bundled assets load from `_MEIPASS` while `guideit.db`, `powershell_store.db`, `user_scripts/`, and `logs/` write cleanly to `LOCALAPPDATA` / `GUIDEIT_DATA_DIR`.
   - Verify all keyboard shortcuts and all 38 scripts + 65 playbooks are documented in root `README.md` and `GEMINI.md`.
4. **Phase 4 Verification Gate:**
   - Run `python tools/validate_playbooks.py --strict`
   - Run `python tools/lint_scripts.py`
   - Run `python -m pytest tests/ -v`
   - Run both `powershell.exe -NoProfile -ExecutionPolicy Bypass -File build.ps1 -VerifyOnly` and `pwsh -NoProfile -File build.ps1 -VerifyOnly`
