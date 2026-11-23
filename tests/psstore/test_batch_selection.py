"""Multi-script batch selection, header sorting, parameter memory & batch runner tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QMessageBox

from guideit_master.psstore.repositories.catalog_repo import CatalogRepo, ScriptRecord
from guideit_master.psstore.services.clipboard_service import ClipboardService, combine_scripts_bundle
from guideit_master.psstore.services.runner import ScriptRunner
from guideit_master.psstore.services.scanner import ScriptScanner
from guideit_master.psstore.ui.catalog_table_view import CatalogTableView


def _write_test_ps1(
    path: Path,
    title: str,
    risk: str = "read_only",
    admin: bool = False,
    param_name: str = "Label",
    param_default: str = "OK",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<#
.SYNOPSIS
    {title} test script.
.PSSTORE_META
    {{
        "title": "{title}",
        "risk_level": "{risk}",
        "ps_edition": "Desktop",
        "requires_admin": {"true" if admin else "false"},
        "timeout_seconds": 20,
        "output_mode": "json",
        "params": [
            {{"name": "{param_name}", "type": "string", "default": "{param_default}"}}
        ]
    }}
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]${param_name} = '{param_default}'
)
$ErrorActionPreference = 'Stop'
$status = 'pass'
$errors = @()
$results = @()
try {{
    $results = @([PSCustomObject]@{{ Label = ${param_name} }})
    $results | Format-Table -AutoSize | Out-String -Width 4096 | Write-Output
}} catch {{
    $status = 'error'
    $errors += $_.Exception.Message
}} finally {{
    [PSCustomObject]@{{
        status = $status
        summary = "Completed with ${{param_name}}"
        data = @($results)
        errors = @($errors)
    }} | ConvertTo-Json -Depth 4 -Compress
}}
""",
        encoding="utf-8",
    )


def test_combine_scripts_bundle_valid_ps51_ast(tmp_path: Path) -> None:
    s1 = tmp_path / "01_System" / "Get-First.ps1"
    s2 = tmp_path / "02_Network" / "Get-Second.ps1"
    _write_test_ps1(s1, "First Task", param_name="Node", param_default="WEB01")
    _write_test_ps1(s2, "Second Task", param_name="Port", param_default="443")

    bundle = combine_scripts_bundle(
        [
            ("First Task", "01_System/Get-First.ps1", s1.read_text(encoding="utf-8")),
            ("Second Task", "02_Network/Get-Second.ps1", s2.read_text(encoding="utf-8")),
        ],
        mode_label="RMM-Ready",
    )
    assert "===== [1/2] First Task =====" in bundle
    assert "===== [2/2] Second Task =====" in bundle
    assert bundle.count("& {") == 2

    bundle_file = tmp_path / "bundle.ps1"
    bundle_file.write_text(bundle, encoding="utf-8")
    proc = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"$t=$null;$e=$null;[void][System.Management.Automation.Language.Parser]::ParseFile('{bundle_file}',[ref]$t,[ref]$e); if($e.Count -gt 0){{ $e | ForEach-Object {{ $_.Message }}; exit 1 }}",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 0, f"PS 5.1 AST errors: {proc.stderr} {proc.stdout}"


def test_catalog_table_checkbox_memory_sorting_and_prune(qapp) -> None:
    catalog = CatalogTableView()
    s10 = ScriptRecord(
        id=1,
        relative_path="01_System/Task-10.ps1",
        category="System",
        filename="Task-10.ps1",
        title="Task 10",
        risk_level="read_only",
        requires_admin=False,
    )
    s2 = ScriptRecord(
        id=2,
        relative_path="01_System/Task-2.ps1",
        category="System",
        filename="Task-2.ps1",
        title="Task 2",
        risk_level="remediation",
        requires_admin=True,
    )
    s_net = ScriptRecord(
        id=3,
        relative_path="02_Network/Check-Dns.ps1",
        category="Network",
        filename="Check-Dns.ps1",
        title="Check DNS",
        risk_level="read_only",
        requires_admin=False,
    )

    catalog.set_scripts([s10, s2, s_net])
    # Natural alphanumeric sort on Title column (0): Check DNS, Task 2, Task 10
    catalog._on_header_clicked(0)
    titles_asc = [catalog.table.item(r, 0).text() for r in range(3)]
    assert titles_asc == ["Check DNS", "Task 2", "Task 10"]

    # Sort by Risk Level (1) descending -> REMEDIATION first
    catalog.sort_by_column(1, Qt.SortOrder.DescendingOrder)
    assert catalog.table.item(0, 1).text() == "REMEDIATION"

    # Sort by Admin (2) descending -> Admin Yes first
    catalog.sort_by_column(2, Qt.SortOrder.DescendingOrder)
    assert "Yes" in catalog.table.item(0, 2).text()

    # Check only read-only visible scripts
    ro_count = catalog.check_read_only_visible()
    assert ro_count == 2
    checked_paths = {s.relative_path for s in catalog.get_checked_scripts()}
    assert checked_paths == {"01_System/Task-10.ps1", "02_Network/Check-Dns.ps1"}

    # Checkbox memory persists when switching filter subset and back
    catalog.set_scripts([s2])
    assert len(catalog.get_checked_scripts()) == 2
    catalog.set_scripts([s10, s2, s_net])
    assert catalog.table.item(1, 0).checkState() == Qt.CheckState.Checked or catalog.get_checked_count() == 2

    # Prune missing script removes stale checkbox
    catalog.prune_checked_scripts({"01_System/Task-10.ps1", "01_System/Task-2.ps1"})
    assert {s.relative_path for s in catalog.get_checked_scripts()} == {"01_System/Task-10.ps1"}
    catalog.deleteLater()


def test_parameter_memory_across_selection_and_bundle_copy(
    shell_window_factory, tmp_path: Path
) -> None:
    scripts_dir = tmp_path / "powershell_scripts"
    _write_test_ps1(scripts_dir / "01_System" / "A.ps1", "Script A", param_name="Target", param_default="DefaultA")
    _write_test_ps1(scripts_dir / "01_System" / "B.ps1", "Script B", param_name="Node", param_default="DefaultB")

    win = shell_window_factory(scripts_dir=scripts_dir)
    ws = win.scripts_workspace
    ws.clipboard_service.copy_to_clipboard = MagicMock(return_value=True)

    scripts = ws.repo.get_all_scripts()
    assert len(scripts) == 2
    ws._on_script_selected(scripts[0])
    ws.param_form._input_widgets["Target"].setText("CustomA")
    ws._on_script_selected(scripts[1])
    ws.param_form._input_widgets["Node"].setText("CustomB")

    ws.catalog_view.check_all_visible()
    ws._on_copy_rmm_clicked()
    ws.clipboard_service.copy_to_clipboard.assert_called_once()
    copied = ws.clipboard_service.copy_to_clipboard.call_args[0][0]
    assert "CustomA" in copied
    assert "CustomB" in copied


def test_runner_execute_batch_real_powershell_and_history(tmp_path: Path, qapp) -> None:
    scripts_dir = tmp_path / "powershell_scripts"
    _write_test_ps1(scripts_dir / "01_System" / "One.ps1", "Batch One", param_default="Alpha")
    _write_test_ps1(scripts_dir / "01_System" / "Two.ps1", "Batch Two", param_default="Beta")

    repo = CatalogRepo(db_path=tmp_path / "batch.db")
    scanner = ScriptScanner(scripts_dir=scripts_dir, repo=repo)
    scanner.sync_catalog()
    scripts = repo.get_all_scripts()

    runner = ScriptRunner(scripts_dir=scripts_dir, repo=repo)
    progress_steps: list[int] = []
    finished_results = []

    loop = QEventLoop()
    runner.batch_progress.connect(lambda step, total, s: progress_steps.append(step))

    def _on_batch_done(res) -> None:
        finished_results.append(res)
        loop.quit()

    runner.batch_finished.connect(_on_batch_done)
    started = runner.execute_batch([(scripts[0], {"Label": "AlphaRun"}), (scripts[1], {"Label": "BetaRun"})])
    assert started is True

    QTimer.singleShot(25000, loop.quit)
    loop.exec()

    assert progress_steps == [1, 2]
    assert len(finished_results) == 1
    assert finished_results[0].status == "pass"
    assert len(repo.get_history_for_script(scripts[0].id)) == 1
    assert len(repo.get_history_for_script(scripts[1].id)) == 1


def test_batch_remediation_confirmation_and_uac_prompt(
    shell_window_factory, tmp_path: Path, monkeypatch
) -> None:
    scripts_dir = tmp_path / "powershell_scripts"
    _write_test_ps1(scripts_dir / "01_System" / "Fix.ps1", "Remediate One", risk="remediation", admin=True)
    _write_test_ps1(scripts_dir / "01_System" / "Inspect.ps1", "Inspect Two", risk="read_only", admin=False)

    win = shell_window_factory(scripts_dir=scripts_dir)
    ws = win.scripts_workspace
    ws.catalog_view.check_all_visible()

    monkeypatch.setattr(
        "guideit_master.psstore.ui.launcher_view.is_running_as_admin",
        lambda: False,
    )
    mock_msg = MagicMock()
    mock_msg.StandardButton = QMessageBox.StandardButton
    mock_msg.Icon = QMessageBox.Icon
    mock_msg.ButtonRole = QMessageBox.ButtonRole
    mock_msg.warning.return_value = QMessageBox.StandardButton.No
    monkeypatch.setattr("guideit_master.psstore.ui.launcher_view.QMessageBox", mock_msg)

    ws.runner.execute_batch = MagicMock()
    ws._on_run_local_clicked()
    mock_msg.warning.assert_called_once()
    ws.runner.execute_batch.assert_not_called()

    # Now confirm remediation, then choose Elevated in UAC dialog
    mock_msg.warning.return_value = QMessageBox.StandardButton.Yes
    elevated_btn = MagicMock()
    unelevated_btn = MagicMock()
    cancel_btn = MagicMock()

    dialog_inst = MagicMock()
    dialog_inst.addButton.side_effect = [elevated_btn, unelevated_btn, cancel_btn]
    dialog_inst.clickedButton.return_value = elevated_btn
    mock_msg.return_value = dialog_inst

    ws.runner.execute_batch_elevated = MagicMock(return_value=True)
    ws._on_run_local_clicked()
    ws.runner.execute_batch_elevated.assert_called_once()
