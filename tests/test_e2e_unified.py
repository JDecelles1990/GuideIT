"""Phase 4 end-to-end verification, layer boundary, frozen simulation & packaging audit tests."""

from __future__ import annotations

import ast
import json
import logging
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QEventLoop, Qt, QTimer, QUrl

from guideit_master import main as app_main
from guideit_master import paths
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo
from guideit_master.psstore.services.clipboard_service import ClipboardService
from guideit_master.psstore.services.runner import ScriptRunner
from guideit_master.psstore.services.scanner import ScriptScanner
from guideit_master.psstore.services.startup_service import StartupService
from guideit_master.ui.shell_window import MODE_PLAYBOOKS, MODE_SCRIPTS, MODE_SPLIT

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_UI_MODULES = {"sqlite3", "subprocess", "hashlib"}


def _write_ps1(
    target: Path,
    title: str,
    *,
    category: str | None = None,
    param_default: str = "Alpha",
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    cat_line = f'        "category": "{category}",\n' if category else ""
    target.write_text(
        f"""<#
.SYNOPSIS
    {title} diagnostic script.
.PSSTORE_META
    {{
        "title": "{title}",
{cat_line}        "risk_level": "read_only",
        "ps_edition": "Desktop",
        "requires_admin": false,
        "timeout_seconds": 20,
        "output_mode": "json",
        "params": [
            {{"name": "Target", "type": "string", "default": "{param_default}"}}
        ]
    }}
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$Target = '{param_default}'
)
$ErrorActionPreference = 'Stop'
$status = 'pass'
$errors = @()
$results = @()
try {{
    $results = @([PSCustomObject]@{{ Target = $Target }})
    $results | Format-Table -AutoSize | Out-String -Width 4096 | Write-Output
}} catch {{
    $status = 'error'
    $errors += $_.Exception.Message
}} finally {{
    [PSCustomObject]@{{
        status = $status
        summary = "Checked $Target"
        data = @($results)
        errors = @($errors)
    }} | ConvertTo-Json -Depth 4 -Compress
}}
""",
        encoding="utf-8",
    )


def _snapshot_tree(root: Path) -> dict[str, tuple[int, int]]:
    snap: dict[str, tuple[int, int]] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            snap[p.relative_to(root).as_posix()] = (st.st_size, st.st_mtime_ns)
    return snap


def test_ast_layer_boundary_no_forbidden_imports_in_ui() -> None:
    src_root = REPO_ROOT / "src" / "guideit_master"
    ui_dirs = [
        src_root / "ui",
        src_root / "guideit" / "ui",
        src_root / "psstore" / "ui",
    ]
    py_files = [p for d in ui_dirs for p in sorted(d.rglob("*.py"))]
    assert len(py_files) >= 15

    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported = [node.module or ""]
            else:
                continue
            for mod in imported:
                top = mod.split(".")[0]
                assert top not in FORBIDDEN_UI_MODULES, (
                    f"Layer boundary violation: {py_file} imports '{mod}'"
                )


def test_module_decoupling_and_zero_legacy_shims() -> None:
    src_base = REPO_ROOT / "src"
    top_dirs = {
        p.name
        for p in src_base.iterdir()
        if p.is_dir() and not p.name.endswith(".egg-info") and p.name != "__pycache__"
    }
    assert top_dirs == {"guideit_master"}, f"Unexpected top-level packages in src/: {top_dirs}"

    src_root = src_base / "guideit_master"
    for py_file in sorted((src_root / "guideit" / "ui").rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            )
            for mod in names:
                assert not mod.startswith("guideit_master.psstore"), (
                    f"Cross-module UI import '{mod}' in {py_file}"
                )

    for py_file in sorted((src_root / "psstore" / "ui").rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            )
            for mod in names:
                assert not mod.startswith("guideit_master.guideit"), (
                    f"Cross-module UI import '{mod}' in {py_file}"
                )


def test_user_scripts_overlay_precedence_clipboard_runner_and_ui(
    tmp_path: Path, shell_window_factory, qapp
) -> None:
    bundled_dir = tmp_path / "bundled"
    user_dir = tmp_path / "user_scripts"

    _write_ps1(
        bundled_dir / "01_System" / "Get-SampleCheck.ps1",
        "Bundled Sample Check",
        param_default="BundledTarget",
    )
    _write_ps1(
        bundled_dir / "02_Network" / "Get-NetOnly.ps1",
        "Bundled Net Only",
        param_default="NetTarget",
    )
    _write_ps1(
        user_dir / "DropIn-Root.ps1",
        "Drop-In Root Diagnostic",
        param_default="RootParam",
    )
    _write_ps1(
        user_dir / "99_Custom" / "User-FolderTool.ps1",
        "User Folder Tool",
        param_default="FolderParam",
    )
    _write_ps1(
        user_dir / "01_System" / "Get-SampleCheck.ps1",
        "User Override Sample Check",
        param_default="UserOverrideTarget",
    )

    # Legacy DB auto-migration (pre-Phase 4 table missing source and file_path)
    db_path = tmp_path / "overlay_catalog.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            """
            CREATE TABLE scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relative_path TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                filename TEXT NOT NULL,
                title TEXT NOT NULL,
                synopsis TEXT,
                risk_level TEXT NOT NULL DEFAULT 'read_only',
                ps_edition TEXT NOT NULL DEFAULT 'Desktop',
                requires_admin INTEGER NOT NULL DEFAULT 0,
                timeout_seconds INTEGER NOT NULL DEFAULT 30,
                output_mode TEXT NOT NULL DEFAULT 'json',
                params_json TEXT,
                sha256 TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE run_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER NOT NULL,
                executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER NOT NULL,
                exit_code INTEGER NOT NULL,
                status TEXT NOT NULL,
                summary TEXT,
                parameters_json TEXT,
                raw_output TEXT,
                json_payload TEXT
            );
            """
        )

    repo = CatalogRepo(db_path=db_path)
    scanner = ScriptScanner(
        scripts_dir=bundled_dir,
        repo=repo,
        user_scripts_dir=user_dir,
    )
    summary = scanner.sync_catalog()
    assert summary.errors == []
    assert summary.total_found == 4
    assert summary.added == 4

    overridden = repo.get_script_by_path("01_System/Get-SampleCheck.ps1")
    assert overridden is not None
    assert overridden.source == "user"
    assert overridden.title == "User Override Sample Check"
    assert overridden.file_path == str((user_dir / "01_System" / "Get-SampleCheck.ps1").resolve())

    drop_in = repo.get_script_by_path("DropIn-Root.ps1")
    assert drop_in is not None
    assert drop_in.source == "user"
    assert drop_in.category == "Custom"

    assert len(repo.get_all_scripts(source="user")) == 3
    assert len(repo.get_all_scripts(source="bundled")) == 1

    # ClipboardService resolves user override & drop-in user script
    clip = ClipboardService(scripts_dir=bundled_dir, user_scripts_dir=user_dir)
    rmm = clip.get_rmm_ready_script("01_System/Get-SampleCheck.ps1", {"Target": "InjectedUser"})
    assert "User Override Sample Check" in rmm
    assert "[string]$Target = 'InjectedUser'" in rmm
    assert "Drop-In Root Diagnostic" in clip.get_raw_script("DropIn-Root.ps1")

    # ScriptRunner executes drop-in user script via QProcess and records run_history
    runner = ScriptRunner(scripts_dir=bundled_dir, repo=repo, user_scripts_dir=user_dir)
    loop = QEventLoop()
    results = []
    runner.finished.connect(lambda res: (results.append(res), loop.quit()))
    assert runner.execute_script(drop_in, {"Target": "OverlayRun"}) is True
    QTimer.singleShot(20000, loop.quit)
    loop.exec()
    assert len(results) == 1
    assert results[0].status == "pass"
    assert results[0].data == [{"Target": "OverlayRun"}]
    assert len(repo.get_history_for_script(drop_in.id)) == 1

    # UI badge shows USER SCRIPT for user scripts and hides for bundled scripts
    win = shell_window_factory(
        scripts_dir=bundled_dir,
        db_path=db_path,
        user_scripts_dir=user_dir,
    )
    win.show()
    sc = win.scripts_workspace
    assert sc.select_and_preload_script("DropIn-Root.ps1")
    qapp.processEvents()
    assert sc.source_chip.isVisible() is True

    assert sc.select_and_preload_script("02_Network/Get-NetOnly.ps1")
    qapp.processEvents()
    assert sc.source_chip.isVisible() is False

    # Removing user override cleanly reverts back to bundled script on resync
    (user_dir / "01_System" / "Get-SampleCheck.ps1").unlink()
    revert_summary = scanner.sync_catalog()
    assert revert_summary.updated == 1
    reverted = repo.get_script_by_path("01_System/Get-SampleCheck.ps1")
    assert reverted is not None
    assert reverted.source == "bundled"
    assert reverted.title == "Bundled Sample Check"


def test_frozen_pyinstaller_simulation_and_smoke_test(
    tmp_path: Path, monkeypatch, qapp
) -> None:
    meipass_dir = tmp_path / "meipass_bundle"
    for folder in ("playbooks", "powershell_scripts", "taxonomy", "templates", "docs"):
        shutil.copytree(REPO_ROOT / folder, meipass_dir / folder)

    writable_data = tmp_path / "writable_data"
    user_scripts_dir = writable_data / "user_scripts"
    _write_ps1(
        user_scripts_dir / "Custom-FrozenOverlay.ps1",
        "Custom Frozen Overlay",
        param_default="FrozenOK",
    )

    bundle_snapshot_before = _snapshot_tree(meipass_dir)

    monkeypatch.delenv(paths.ENV_BUNDLE_DIR, raising=False)
    monkeypatch.setenv(paths.ENV_DATA_DIR, str(writable_data))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)

    # Guard console=False logging when sys.stdout / sys.stderr are None
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    test_handler = app_main.configure_logging()
    try:
        logging.getLogger("guideit_master.test_frozen").info("Frozen console=False logging test")
    finally:
        logging.getLogger().removeHandler(test_handler)
        test_handler.close()

    monkeypatch.undo()
    monkeypatch.delenv(paths.ENV_BUNDLE_DIR, raising=False)
    monkeypatch.setenv(paths.ENV_DATA_DIR, str(writable_data))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)

    rc = app_main.main(["--smoke-test"])
    assert rc == 0

    guideit_db = writable_data / "guideit.db"
    ps_db = writable_data / "powershell_store.db"
    log_file = writable_data / "logs" / "guideit_master.log"
    result_file = writable_data / "smoke_test_result.json"

    assert guideit_db.is_file()
    assert ps_db.is_file()
    assert user_scripts_dir.is_dir()
    assert log_file.is_file()
    assert result_file.is_file()

    expected_playbooks = len(
        [
            p
            for p in (meipass_dir / "playbooks").rglob("*.md")
            if p.parent != (meipass_dir / "playbooks") and p.name.lower() != "readme.md"
        ]
    )
    expected_bundled_scripts = len(
        list((meipass_dir / "powershell_scripts").rglob("*.ps1"))
    )
    assert expected_playbooks >= 65
    assert expected_bundled_scripts >= 38

    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["frozen"] is True
    assert payload["bundle_dir"] == str(meipass_dir.resolve())
    assert payload["user_data_dir"] == str(writable_data.resolve())
    assert payload["playbook_count"] == expected_playbooks
    assert payload["script_count"] == expected_bundled_scripts + 1
    assert payload["user_script_count"] == 1
    assert payload["unified_search_ok"] is True
    assert payload["split_view_ok"] is True

    # Read-only _MEIPASS simulation must remain completely untouched
    assert _snapshot_tree(meipass_dir) == bundle_snapshot_before


def test_frozen_open_scripts_folder_targets_user_scripts(
    tmp_path: Path, monkeypatch, shell_window_factory
) -> None:
    writable_data = tmp_path / "frozen_data"
    meipass_dir = tmp_path / "frozen_meipass"
    shutil.copytree(REPO_ROOT / "powershell_scripts", meipass_dir / "powershell_scripts")
    shutil.copytree(REPO_ROOT / "playbooks", meipass_dir / "playbooks")
    shutil.copytree(REPO_ROOT / "taxonomy", meipass_dir / "taxonomy")
    shutil.copytree(REPO_ROOT / "templates", meipass_dir / "templates")
    shutil.copytree(REPO_ROOT / "docs", meipass_dir / "docs")

    monkeypatch.delenv(paths.ENV_BUNDLE_DIR, raising=False)
    monkeypatch.setenv(paths.ENV_DATA_DIR, str(writable_data))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)

    win = shell_window_factory()
    opened_urls: list[QUrl] = []
    monkeypatch.setattr(
        "guideit_master.psstore.ui.launcher_view.QDesktopServices.openUrl",
        lambda url: (opened_urls.append(url), True)[1],
    )
    win.scripts_workspace.open_scripts_folder()

    assert len(opened_urls) == 1
    assert Path(opened_urls[0].toLocalFile()).resolve() == (writable_data / "user_scripts").resolve()


def test_e2e_unified_shell_omnibox_split_view_and_reverse_nav(
    shell_window_factory, monkeypatch, tmp_path: Path, qapp
) -> None:
    win = shell_window_factory()
    win.show()

    # 1. Focus Unified Omnibox (Ctrl+Shift+K) and search for "0x0000011b"
    win._focus_unified_search()
    resp = win.run_unified_search("0x0000011b")
    qapp.processEvents()
    assert win.omnibox_popup.isVisible()
    assert resp.playbook_hits[0].id == "prt-001"

    pb_item = None
    for idx in range(win.omnibox_results_list.count()):
        item = win.omnibox_results_list.item(idx)
        if item.data(Qt.ItemDataRole.UserRole) == ("playbook", "prt-001"):
            pb_item = item
            break
    assert pb_item is not None
    win._on_omnibox_item_activated(pb_item)
    qapp.processEvents()

    assert win.current_mode == MODE_PLAYBOOKS
    assert win.playbooks_workspace.viewer.current_playbook_id == "prt-001"

    # 2. Switch to Split View (Alt+3) via linked script action card
    spooler_rel = "04_Devices/Reset-PrintSpooler.ps1"
    btns = win.playbooks_workspace.viewer.linked_script_buttons[spooler_rel]
    btns["split_view"].click()
    qapp.processEvents()

    sc = win.scripts_workspace
    assert win.current_mode == MODE_SPLIT
    assert win.playbooks_workspace.is_compact_mode is True
    assert sc.is_compact_mode is True
    assert win.playbooks_workspace.parentWidget() is win.mode_splitter
    assert sc.parentWidget() is win.mode_splitter
    assert sc._current_script is not None
    assert sc._current_script.relative_path == spooler_rel
    assert "prt-001" in sc.used_in_playbook_buttons

    # 3. Click reverse "Used in Playbooks" pill back to Playbooks mode
    sc.used_in_playbook_buttons["prt-001"].click()
    qapp.processEvents()
    assert win.current_mode == MODE_PLAYBOOKS
    assert win.playbooks_workspace.viewer.current_playbook_id == "prt-001"

    # 4. StartupService generates valid frozen .exe and source launch commands
    svc = StartupService(main_script_path=REPO_ROOT / "main.py")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    src_cmd = svc.get_launch_command("--startup")
    assert "main.py" in src_cmd
    assert src_cmd.endswith(" --startup")

    exe_path = tmp_path / "GuideIT_Master.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_path))
    frozen_cmd = svc.get_launch_command("--startup")
    assert frozen_cmd == f'"{exe_path}" --startup'


def test_pyinstaller_spec_and_build_ps1_audit() -> None:
    spec_path = REPO_ROOT / "guideit_master.spec"
    assert spec_path.is_file()
    spec_text = spec_path.read_text(encoding="utf-8")
    tree = ast.parse(spec_text, filename=str(spec_path))

    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value

    bundled = ast.literal_eval(assignments["BUNDLED_DATA_DIRS"])
    excluded = set(ast.literal_eval(assignments["EXCLUDED_ROOT_DIRS"]))
    assert {src for src, _ in bundled} == {
        "playbooks",
        "powershell_scripts",
        "taxonomy",
        "templates",
        "docs",
    }
    assert {"data", "_ref_GuideIT", "_ref_PowerShellStore", "tests"}.issubset(excluded)

    collect_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "COLLECT"
    ]
    assert len(collect_calls) == 1
    assert any(
        kw.arg == "name" and ast.literal_eval(kw.value) == "GuideIT_Master"
        for kw in collect_calls[0].keywords
    )

    build_ps1 = REPO_ROOT / "build.ps1"
    assert build_ps1.is_file()
    raw_bytes = build_ps1.read_bytes()
    ascii_text = raw_bytes.decode("ascii")  # Pure 7-bit ASCII required for PS 5.1 safety
    assert "-VerifyOnly" in ascii_text
    assert "-Package" in ascii_text
    assert "TickCount64" not in ascii_text

    # Parse build.ps1 using Windows PowerShell 5.1 AST parser
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                f"$t=$null;$e=$null;[void][System.Management.Automation.Language.Parser]::"
                f"ParseFile('{build_ps1}',[ref]$t,[ref]$e);"
                "if($e.Count -gt 0){$e | ForEach-Object {$_.Message}; exit 1}"
            ),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, f"build.ps1 PS 5.1 AST errors: {proc.stderr} {proc.stdout}"


def test_docs_and_readonly_reference_audit(shell_window_factory) -> None:
    ref_guideit = REPO_ROOT / "_ref_GuideIT"
    ref_psstore = REPO_ROOT / "_ref_PowerShellStore"
    assert ref_guideit.is_dir()
    assert ref_psstore.is_dir()

    git_res = subprocess.run(
        ["git", "status", "--porcelain", "_ref_GuideIT", "_ref_PowerShellStore"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert git_res.returncode == 0
    assert git_res.stdout.strip() == "", f"Reference archives modified:\n{git_res.stdout}"

    readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    # All built-in scripts on disk documented
    ps1_files = sorted((REPO_ROOT / "powershell_scripts").rglob("*.ps1"))
    assert len(ps1_files) >= 38
    for ps1 in ps1_files:
        assert ps1.name in readme_text, f"Script {ps1.name} missing from README.md"

    # All playbook domains and files on disk accounted for and domains documented
    pb_dirs = sorted(p for p in (REPO_ROOT / "playbooks").iterdir() if p.is_dir())
    assert len(pb_dirs) >= 9
    total_pbs = 0
    for domain_dir in pb_dirs:
        assert domain_dir.name in readme_text, f"Domain {domain_dir.name} missing from README.md"
        total_pbs += sum(
            1 for f in domain_dir.glob("*.md") if f.name.lower() != "readme.md"
        )
    assert total_pbs >= 65

    # Phase 4 overlay & packaging docs present
    assert "user_scripts/" in readme_text
    assert "guideit_master.spec" in readme_text
    assert "build.ps1" in readme_text
    assert "-VerifyOnly" in readme_text
    assert "-Package" in readme_text

    # Every shortcut registered in UnifiedShellWindow is documented in README.md
    win = shell_window_factory()
    assert "Win+F8" in readme_text
    for name, sc in win.shortcuts.items():
        for seq in sc.keys():
            label = seq.toString()
            if label == "Ctrl++":
                assert "Ctrl++" in readme_text
            elif label == "Ctrl+Return":
                assert "Ctrl+Enter" in readme_text or "Ctrl+Return" in readme_text
            else:
                assert label in readme_text, (
                    f"Shortcut '{label}' ({name}) missing from README.md"
                )
