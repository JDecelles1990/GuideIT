"""Phase 1 core persistence & .PSSTORE_META scanner tests for PowerShellStore."""

from __future__ import annotations

from pathlib import Path

from guideit_master.psstore.repositories.catalog_repo import CatalogRepo, ScriptRecord
from guideit_master.psstore.services.scanner import ScriptScanner


def _write_sample_script(
    path: Path,
    title: str = "Test Script",
    risk: str = "read_only",
    admin: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<#
.SYNOPSIS
    Sample synopsis for {title}.
.PSSTORE_META
    {{
        "title": "{title}",
        "risk_level": "{risk}",
        "ps_edition": "Desktop",
        "requires_admin": {"true" if admin else "false"},
        "timeout_seconds": 30,
        "output_mode": "json",
        "params": [
            {{"name": "TargetName", "type": "string", "default": "DefaultHost"}},
            {{"name": "MaxCount", "type": "int", "default": 10, "min": 1, "max": 50}},
            {{"name": "VerboseFlag", "type": "bool", "default": false}}
        ]
    }}
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$TargetName = 'DefaultHost',
    [Parameter(Mandatory = $false)]
    [int]$MaxCount = 10,
    [Parameter(Mandatory = $false)]
    [bool]$VerboseFlag = $false
)
$ErrorActionPreference = 'Stop'
Write-Output "$TargetName $MaxCount $VerboseFlag"
""",
        encoding="utf-8",
    )


def test_catalog_repo_crud_and_filters(tmp_path: Path) -> None:
    repo = CatalogRepo(db_path=tmp_path / "crud.db")
    rec1 = ScriptRecord(
        relative_path="01_System/Get-TestInfo.ps1",
        category="System",
        filename="Get-TestInfo.ps1",
        title="Get Test Info",
        synopsis="Collects basic OS telemetry.",
        risk_level="read_only",
        ps_edition="Desktop",
        requires_admin=False,
        timeout_seconds=25,
        output_mode="json",
        params=[{"name": "Detailed", "type": "bool", "default": True}],
        sha256="abc123",
    )
    rec2 = ScriptRecord(
        relative_path="04_Devices/Reset-TestSpooler.ps1",
        category="Devices",
        filename="Reset-TestSpooler.ps1",
        title="Reset Test Spooler",
        synopsis="Restarts the Print Spooler service.",
        risk_level="remediation",
        ps_edition="Core",
        requires_admin=True,
        timeout_seconds=30,
        output_mode="text",
        params=[],
        sha256="def456",
    )

    id1 = repo.upsert_script(rec1)
    id2 = repo.upsert_script(rec2)
    assert id1 > 0 and id2 > 0

    fetched = repo.get_script_by_path("01_System/Get-TestInfo.ps1")
    assert fetched is not None
    assert fetched.title == "Get Test Info"
    assert fetched.params == [{"name": "Detailed", "type": "bool", "default": True}]
    assert repo.get_script_by_id(id2).requires_admin is True

    assert len(repo.get_all_scripts()) == 2
    assert len(repo.get_all_scripts(category="Devices")) == 1
    assert len(repo.get_all_scripts(risk_level="remediation")) == 1
    assert len(repo.get_all_scripts(ps_edition="Core")) == 1
    assert len(repo.get_all_scripts(search="telemetry")) == 1

    counts = repo.get_categories_with_counts()
    assert counts == [{"category": "Devices", "count": 1}, {"category": "System", "count": 1}]

    deleted = repo.delete_missing_scripts(["01_System/Get-TestInfo.ps1"])
    assert deleted == 1
    assert len(repo.get_all_scripts()) == 1


def test_script_scanner_sync_lifecycle(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "powershell_scripts"
    script_a = scripts_dir / "01_System" / "Get-Alpha.ps1"
    script_b = scripts_dir / "02_Network" / "Reset-Beta.ps1"
    _write_sample_script(script_a, title="Alpha Check")
    _write_sample_script(script_b, title="Beta Reset", risk="remediation", admin=True)

    repo = CatalogRepo(db_path=tmp_path / "sync.db")
    scanner = ScriptScanner(scripts_dir=scripts_dir, repo=repo)

    assert ScriptScanner.derive_category("01_System") == "System"
    assert ScriptScanner.derive_category("05_Security_Defender") == "Security_Defender"

    first = scanner.sync_catalog()
    assert (first.total_found, first.added, first.updated, first.unchanged, first.deleted) == (
        2,
        2,
        0,
        0,
        0,
    )

    second = scanner.sync_catalog()
    assert (second.total_found, second.added, second.updated, second.unchanged, second.deleted) == (
        2,
        0,
        0,
        2,
        0,
    )

    _write_sample_script(script_a, title="Alpha Check Updated")
    script_b.unlink()
    third = scanner.sync_catalog()
    assert (third.total_found, third.added, third.updated, third.unchanged, third.deleted) == (
        1,
        0,
        1,
        0,
        1,
    )
    updated = repo.get_script_by_path("01_System/Get-Alpha.ps1")
    assert updated is not None
    assert updated.title == "Alpha Check Updated"
