"""Phase 4 production 38-script catalog validation & parameter injection tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from guideit_master.paths import get_ps_scripts_dir
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo
from guideit_master.psstore.services.clipboard_service import ClipboardService
from guideit_master.psstore.services.scanner import ScriptScanner
from tools.lint_scripts import run_linter


def test_production_catalog_syncs_all_38_scripts(tmp_path: Path) -> None:
    scripts_dir = get_ps_scripts_dir()
    repo = CatalogRepo(db_path=tmp_path / "prod_catalog.db")
    scanner = ScriptScanner(scripts_dir=scripts_dir, repo=repo)

    summary = scanner.sync_catalog()
    assert summary.errors == []
    assert summary.total_found >= 38
    assert summary.added >= 38

    all_scripts = repo.get_all_scripts()
    assert len(all_scripts) >= 38


@pytest.mark.parametrize(
    ("relative_path", "param_values", "expected_snippets"),
    [
        (
            "04_Devices/Reset-PrintSpooler.ps1",
            {"ClearQueueFiles": False},
            ["[bool]$ClearQueueFiles = $false"],
        ),
        (
            "01_System/Get-DiskSpaceReport.ps1",
            {"LowSpaceThresholdPercent": 25},
            ["[int]$LowSpaceThresholdPercent = 25"],
        ),
        (
            "02_Network/Test-PortConnectivity.ps1",
            {"TargetHost": "dc01.domain.local", "Port": 389, "TimeoutMs": 1500},
            [
                "[string]$TargetHost = 'dc01.domain.local'",
                "[int]$Port = 389",
                "[int]$TimeoutMs = 1500",
            ],
        ),
        (
            "01_System/Get-OSInformation.ps1",
            {"Detailed": False},
            ["[bool]$Detailed = $false"],
        ),
        (
            "01_System/Update-Windows.ps1",
            {"ScanOnly": True, "AutoReboot": False, "MaxUpdates": 10},
            ["[bool]$ScanOnly = $true", "[bool]$AutoReboot = $false", "[int]$MaxUpdates = 10"],
        ),
        (
            "03_M365/Clear-OutlookCache.ps1",
            {"CloseOutlook": False, "PreserveAutoComplete": True},
            ["[bool]$CloseOutlook = $false", "[bool]$PreserveAutoComplete = $true"],
        ),
        (
            "01_System/Get-BatteryHealthReport.ps1",
            {"WearThresholdPercent": 45},
            ["[int]$WearThresholdPercent = 45"],
        ),
        (
            "02_Network/Reset-NetworkStack.ps1",
            {"FlushDNS": True, "RenewDHCP": False, "ResetWinsock": False, "ResetTCPStack": False},
            ["[bool]$FlushDNS = $true", "[bool]$RenewDHCP = $false"],
        ),
        (
            "02_Network/Test-NetworkQuality.ps1",
            {"TargetHost": "9.9.9.9", "PingCount": 6, "MaxAcceptableLatencyMs": 150},
            ["[string]$TargetHost = '9.9.9.9'", "[int]$PingCount = 6"],
        ),
        (
            "03_M365/Reset-OneDriveSync.ps1",
            {"KillRunningProcess": True, "RunResetCommand": False, "RelaunchOneDrive": False},
            ["[bool]$KillRunningProcess = $true", "[bool]$RunResetCommand = $false"],
        ),
        (
            "01_System/Get-HighResourceProcesses.ps1",
            {"SortBy": "Memory", "TopCount": 5},
            ["[string]$SortBy = 'Memory'", "[int]$TopCount = 5"],
        ),
        (
            "01_System/Get-RecentEventErrors.ps1",
            {"HoursBack": 48, "MaxEvents": 50},
            ["[int]$HoursBack = 48", "[int]$MaxEvents = 50"],
        ),
        (
            "02_Network/Get-ListeningPorts.ps1",
            {"Protocol": "TCP", "PortFilter": 443},
            ["[string]$Protocol = 'TCP'", "[int]$PortFilter = 443"],
        ),
    ],
)
def test_production_scripts_parameter_injection(
    relative_path: str, param_values: dict, expected_snippets: list[str]
) -> None:
    clipboard = ClipboardService(scripts_dir=get_ps_scripts_dir())
    rmm = clipboard.get_rmm_ready_script(relative_path, param_values)
    for snippet in expected_snippets:
        assert snippet in rmm


def test_lint_scripts_passes_all_production_scripts() -> None:
    results = run_linter(get_ps_scripts_dir())
    assert len(results) >= 38
    failed = [(r.relative_path, r.errors) for r in results if not r.passed]
    assert failed == []
