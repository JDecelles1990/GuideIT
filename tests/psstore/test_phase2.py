"""Phase 2 parameter injection, PowerShell CLI arg building & runner parser tests."""

from __future__ import annotations

import json
from pathlib import Path

from guideit_master.psstore.repositories.catalog_repo import CatalogRepo, ScriptRecord
from guideit_master.psstore.services.clipboard_service import (
    ClipboardService,
    format_powershell_literal,
    inject_parameters,
)
from guideit_master.psstore.services.runner import ScriptRunner, build_powershell_args


def test_format_powershell_literal() -> None:
    assert format_powershell_literal(True) == "$true"
    assert format_powershell_literal(False) == "$false"
    assert format_powershell_literal(42) == "42"
    assert format_powershell_literal("O'Brien") == "'O''Brien'"
    assert format_powershell_literal(["A", 2, False]) == "@('A', 2, $false)"


def test_inject_parameters_and_clipboard_service(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "powershell_scripts"
    rel = "01_System/Get-Custom.ps1"
    script_file = scripts_dir / rel
    script_file.parent.mkdir(parents=True, exist_ok=True)
    script_content = """<#
.SYNOPSIS
    Sample script for injection.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$HostName = 'localhost',
    [Parameter(Mandatory = $false)]
    [int]$Count = 5,
    [Parameter(Mandatory = $false)]
    [bool]$IncludeWarn = $false
)
Write-Output "$HostName $Count $IncludeWarn"
"""
    script_file.write_text(script_content, encoding="utf-8")

    injected = inject_parameters(
        script_content,
        {"HostName": "DC01'Lab", "Count": 25, "IncludeWarn": True},
    )
    assert "[string]$HostName = 'DC01''Lab'" in injected
    assert "[int]$Count = 25" in injected
    assert "[bool]$IncludeWarn = $true" in injected

    svc = ClipboardService(scripts_dir=scripts_dir)
    assert svc.get_raw_script(rel) == script_content
    rmm = svc.get_rmm_ready_script(rel, {"Count": 99})
    assert "[int]$Count = 99" in rmm


def test_build_powershell_args() -> None:
    args = build_powershell_args(
        {"Target": "app'01", "Retries": 3, "Force": True, "Skip": None}
    )
    assert args == ["-Target", "'app''01'", "-Retries", "3", "-Force:$true"]


def test_script_runner_parse_results(tmp_path: Path) -> None:
    repo = CatalogRepo(db_path=tmp_path / "runner.db")
    runner = ScriptRunner(scripts_dir=tmp_path, repo=repo)
    runner._current_script = ScriptRecord(
        id=7,
        relative_path="01_System/Get-OSInformation.ps1",
        category="System",
        filename="Get-OSInformation.ps1",
        title="Get OS Info",
    )

    envelope = {
        "status": "warning",
        "summary": "1 low-space drive detected.",
        "data": [{"Drive": "C:", "FreeGB": 8}],
        "errors": ["Below threshold"],
    }
    res = runner._parse_results(0, f"Human table output\n{json.dumps(envelope)}\n", "", 123)
    assert res.status == "warning"
    assert res.summary == "1 low-space drive detected."
    assert res.data == [{"Drive": "C:", "FreeGB": 8}]
    assert res.errors == ["Below threshold"]
    assert res.duration_ms == 123

    text_res = runner._parse_results(0, "[SUCCESS] Spooler restarted cleanly\n", "", 45)
    assert text_res.status == "pass"
    assert "Spooler restarted" in text_res.summary

    runner._is_timed_out = True
    timeout_res = runner._parse_results(1, "", "killed", 30000)
    assert timeout_res.status == "timeout"
