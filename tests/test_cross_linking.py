"""Phase 3 tests for bidirectional Playbook <-> Script cross-linking, validation, and unified search."""

from __future__ import annotations

import ast
import json
import shutil
import sqlite3
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from guideit_master.guideit.indexer import SCHEMA_VERSION, build_index
from guideit_master.guideit.search import get_playbook_by_id, search_playbooks
from guideit_master.guideit.ui.markdown_blocks import ProseBlock, parse_section_blocks
from guideit_master.guideit.validator import load_playbook_file, validate_repository
from guideit_master.paths import get_ps_scripts_dir
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo
from guideit_master.psstore.services.scanner import ScriptScanner
from guideit_master.services.cross_link_service import (
    CrossLinkService,
    coerce_param_overrides,
    parse_psstore_uri,
)
from guideit_master.services.unified_search import search_all
from guideit_master.ui.shell_window import MODE_PLAYBOOKS, MODE_SCRIPTS, MODE_SPLIT
from tools import search_cli

REPO_ROOT = Path(__file__).resolve().parents[1]

CURATED_PLAYBOOK_IDS = (
    "prt-001",
    "prt-003",
    "win-001",
    "win-002",
    "win-003",
    "win-006",
    "win-007",
    "win-008",
    "net-001",
    "net-002",
    "net-003",
    "m365-001",
    "m365-005",
    "id-001",
    "id-005",
    "sec-002",
    "sec-003",
    "srv-001",
    "app-001",
    "app-002",
)


def _create_minimal_repo(
    dst_root: Path,
    *,
    linked_scripts_yaml: str = "",
    extra_body: str = "",
    copy_scripts: list[str] | None = None,
) -> Path:
    shutil.copytree(REPO_ROOT / "taxonomy", dst_root / "taxonomy")
    pb_dir = dst_root / "playbooks" / "05_Printers_Devices"
    pb_dir.mkdir(parents=True)
    scripts_dir = dst_root / "powershell_scripts"
    scripts_dir.mkdir(parents=True)

    for rel in copy_scripts or []:
        src_file = get_ps_scripts_dir(REPO_ROOT) / rel
        target_file = scripts_dir / rel
        target_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, target_file)

    pb_file = pb_dir / "prt-001-spooler-test.md"
    pb_file.write_text(
        (
            "---\n"
            "id: prt-001\n"
            "domain: 05_Printers_Devices\n"
            'subject: "Printers & Peripherals"\n'
            "subcategory: printers_spooler_scan\n"
            "title: Print Spooler Test Playbook\n"
            "tier: L1\n"
            "keywords_en: [printer stuck]\n"
            "keywords_fr: [imprimante bloquee]\n"
            'error_codes: ["0x0000011b"]\n'
            "tags: [print_spooler]\n"
            "os: [windows]\n"
            "environment: [local_endpoint]\n"
            "tools: [PowerShell]\n"
            "risk_level: low\n"
            "requires_admin: true\n"
            "last_verified: 2026-11-22\n"
            "related_ids: []\n"
            f"{linked_scripts_yaml}"
            "---\n\n"
            "## Fast Triage (Under 2 Minutes)\n"
            "- Check single user vs global impact.\n\n"
            "## Read-Only Diagnostics (L1-L2)\n"
            "- Inspect spooler queue.\n"
            f"{extra_body}\n"
            "## Deep-Dive Investigation (L3)\n"
            "- Inspect RPC logs.\n\n"
            "## Remediation (Confirm Before Running)\n"
            "- **[REMEDIATION — CONFIRM BEFORE RUNNING]** Restart spooler.\n\n"
            "## Verification & Post-Fix Checks\n"
            "- Print test page.\n"
        ),
        encoding="utf-8",
    )
    return pb_file


def test_linked_scripts_parsed_and_indexed_across_curated_playbooks(tmp_path: Path) -> None:
    db_path = tmp_path / "guideit.db"
    stats = build_index(REPO_ROOT, db_path=db_path)
    assert stats.indexed_count >= 65

    prt_file = REPO_ROOT / "playbooks" / "05_Printers_Devices" / "prt-001-spooler-and-0x0000011b.md"
    parsed = load_playbook_file(REPO_ROOT, prt_file)
    assert parsed.linked_scripts == [
        "04_Devices/Get-PrintQueues.ps1",
        "04_Devices/Reset-PrintSpooler.ps1",
    ]

    record = get_playbook_by_id(db_path, "prt-001")
    assert record is not None
    assert record["linked_scripts"] == [
        "04_Devices/Get-PrintQueues.ps1",
        "04_Devices/Reset-PrintSpooler.ps1",
    ]

    search_res = search_playbooks(db_path, "0x0000011b", root_dir=REPO_ROOT)
    assert search_res.hits[0].id == "prt-001"
    assert search_res.hits[0].linked_scripts == [
        "04_Devices/Get-PrintQueues.ps1",
        "04_Devices/Reset-PrintSpooler.ps1",
    ]

    for pb_id in CURATED_PLAYBOOK_IDS:
        rec = get_playbook_by_id(db_path, pb_id)
        assert rec is not None, f"Missing curated playbook {pb_id}"
        assert len(rec["linked_scripts"]) >= 1, f"{pb_id} has empty linked_scripts"


@pytest.mark.parametrize(
    ("linked_yaml", "extra_body"),
    [
        ("linked_scripts:\n  - 04_Devices/Does-Not-Exist.ps1\n", ""),
        ("linked_scripts:\n  - Reset-PrintSpooler.ps1\n", ""),
        ("linked_scripts:\n  - 04_Devices\\Reset-PrintSpooler.ps1\n", ""),
        ("linked_scripts:\n  - ../04_Devices/Reset-PrintSpooler.ps1\n", ""),
        ("", "- Inline broken: [Fix](psstore://04_Devices/Missing-Script.ps1?Foo=1)\n"),
        ("", "- Inline bare name: [Fix](psstore://Reset-PrintSpooler.ps1?ClearQueueFiles=false)\n"),
    ],
)
def test_validator_rejects_broken_and_non_canonical_linked_scripts(
    tmp_path: Path, linked_yaml: str, extra_body: str
) -> None:
    _create_minimal_repo(
        tmp_path,
        linked_scripts_yaml=linked_yaml,
        extra_body=extra_body,
        copy_scripts=["04_Devices/Reset-PrintSpooler.ps1"],
    )
    report = validate_repository(tmp_path, today=date(2026, 11, 22))
    assert any(err.code == "BROKEN_LINKED_SCRIPT" for err in report.errors)


def test_validator_accepts_valid_canonical_linked_scripts_and_psstore_links(tmp_path: Path) -> None:
    _create_minimal_repo(
        tmp_path,
        linked_scripts_yaml=(
            "linked_scripts:\n"
            "  - 04_Devices/Get-PrintQueues.ps1\n"
            "  - 04_Devices/Reset-PrintSpooler.ps1\n"
        ),
        extra_body="- Quick run: [Reset Spooler](psstore://04_Devices/Reset-PrintSpooler.ps1?ClearQueueFiles=false)\n",
        copy_scripts=[
            "04_Devices/Get-PrintQueues.ps1",
            "04_Devices/Reset-PrintSpooler.ps1",
        ],
    )
    report = validate_repository(tmp_path, today=date(2026, 11, 22))
    assert report.errors == []


def test_scripts_fts_backfill_migration_and_sync(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_psstore.db"
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
        conn.execute(
            """
            INSERT INTO scripts (
                relative_path, category, filename, title, synopsis,
                risk_level, ps_edition, requires_admin, timeout_seconds,
                output_mode, params_json, sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "04_Devices/Reset-PrintSpooler.ps1",
                "Devices",
                "Reset-PrintSpooler.ps1",
                "Reset Print Spooler",
                "Clears stuck print jobs and restarts Spooler.",
                "remediation",
                "Desktop",
                1,
                30,
                "text",
                json.dumps([{"name": "ClearQueueFiles", "type": "bool", "default": True}]),
                "deadbeef",
            ),
        )
        conn.commit()

    # Initializing CatalogRepo on legacy DB must create & backfill scripts_fts
    repo = CatalogRepo(db_path=db_path)
    fts_hits = repo.search_scripts_fts('"spooler"')
    assert len(fts_hits) == 1
    assert fts_hits[0][0].relative_path == "04_Devices/Reset-PrintSpooler.ps1"

    # Parameter name search also works via params_text column
    param_hits = repo.search_scripts_fts('"ClearQueueFiles"')
    assert len(param_hits) == 1

    # Upsert updates FTS without creating duplicate entries
    updated = fts_hits[0][0]
    updated.title = "Reset Print Spooler Service"
    repo.upsert_script(updated)
    assert len(repo.search_scripts_fts('"spooler"')) == 1

    # Deleting missing scripts prunes scripts_fts as well
    assert repo.delete_missing_scripts([]) == 1
    assert repo.search_scripts_fts('"spooler"') == []


def test_playbook_action_cards_copy_open_and_split_view(
    shell_window_factory, qapp
) -> None:
    win = shell_window_factory()
    win.show()

    win.set_mode(MODE_PLAYBOOKS)
    win.playbooks_workspace.navigate_to_playbook("prt-001")
    qapp.processEvents()

    viewer = win.playbooks_workspace.viewer
    assert viewer.current_playbook_id == "prt-001"
    assert "04_Devices/Get-PrintQueues.ps1" in viewer.linked_script_cards
    assert "04_Devices/Reset-PrintSpooler.ps1" in viewer.linked_script_cards
    assert "04_Devices/Reset-PrintSpooler.ps1" in viewer.linked_script_header_pills

    # Mock clipboard to avoid external clipboard flakiness
    sc = win.scripts_workspace
    sc.clipboard_service.copy_to_clipboard = MagicMock(return_value=True)

    # 1. Copy RMM-Ready from PlaybookViewer card
    btns = viewer.linked_script_buttons["04_Devices/Reset-PrintSpooler.ps1"]
    btns["copy_rmm"].click()
    qapp.processEvents()
    sc.clipboard_service.copy_to_clipboard.assert_called_once()
    assert "[bool]$ClearQueueFiles = $true" in sc.clipboard_service.copy_to_clipboard.call_args[0][0]

    # 2. Copy Raw from PlaybookViewer card
    sc.clipboard_service.copy_to_clipboard.reset_mock()
    btns["copy_raw"].click()
    qapp.processEvents()
    sc.clipboard_service.copy_to_clipboard.assert_called_once()
    assert "Spooler" in sc.clipboard_service.copy_to_clipboard.call_args[0][0]

    # 3. Open in Workstation switches to MODE_SCRIPTS with script preloaded
    btns["open_workstation"].click()
    qapp.processEvents()
    assert win.current_mode == MODE_SCRIPTS
    assert sc._current_script is not None
    assert sc._current_script.relative_path == "04_Devices/Reset-PrintSpooler.ps1"

    # 4. Switch back to Playbooks and click Split View & Run on Get-PrintQueues.ps1
    win.set_mode(MODE_PLAYBOOKS)
    qapp.processEvents()
    queue_btns = viewer.linked_script_buttons["04_Devices/Get-PrintQueues.ps1"]
    queue_btns["split_view"].click()
    qapp.processEvents()

    assert win.current_mode == MODE_SPLIT
    assert win.playbooks_workspace.is_compact_mode is True
    assert sc.is_compact_mode is True
    assert sc._current_script is not None
    assert sc._current_script.relative_path == "04_Devices/Get-PrintQueues.ps1"
    assert win.playbooks_workspace.parentWidget() is win.mode_splitter
    assert sc.parentWidget() is win.mode_splitter


def test_inline_psstore_link_parameter_coercion_and_remediation_safety(
    shell_window_factory, qapp, monkeypatch
) -> None:
    # Markdown rendering of inline psstore:// link
    parsed = parse_section_blocks(
        "Read-Only Diagnostics (L1-L2)",
        "Run [Port Check](psstore://02_Network/Test-PortConnectivity.ps1?TargetHost=dc01.domain.local&Port=636).",
    )
    prose = [b for b in parsed.blocks if isinstance(b, ProseBlock)]
    assert len(prose) == 1
    assert 'href="psstore://02_Network/Test-PortConnectivity.ps1?TargetHost=dc01.domain.local&amp;Port=636"' in prose[0].html

    # URI parser & strict parameter coercion
    assert parse_psstore_uri("psstore://Reset-PrintSpooler.ps1?ClearQueueFiles=false") is None
    coerced = coerce_param_overrides(
        [
            {"name": "ClearQueueFiles", "type": "bool", "default": True},
            {"name": "Port", "type": "int", "default": 443, "min": 1, "max": 65535},
            {"name": "TargetHost", "type": "string", "default": "1.1.1.1"},
        ],
        {
            "clearqueuefiles": "false",
            "port": "99999",
            "TargetHost": "dc01.domain.local",
            "UnknownParam": "ignored",
        },
    )
    assert coerced == {
        "ClearQueueFiles": False,
        "Port": 65535,
        "TargetHost": "dc01.domain.local",
    }

    win = shell_window_factory()
    win.show()
    win.set_mode(MODE_PLAYBOOKS)
    win.playbooks_workspace.viewer._handle_link(
        "psstore://02_Network/Test-PortConnectivity.ps1?TargetHost=dc01.domain.local&Port=636&DropMe=1"
    )
    qapp.processEvents()

    sc = win.scripts_workspace
    assert win.current_mode == MODE_SPLIT
    assert sc._current_script is not None
    assert sc._current_script.relative_path == "02_Network/Test-PortConnectivity.ps1"
    assert sc.param_form.get_parameter_values() == {
        "TargetHost": "dc01.domain.local",
        "Port": 636,
        "TimeoutMs": 3000,
    }

    # run_script_requested on a remediation script MUST still require QMessageBox confirmation
    mock_msg = MagicMock()
    mock_msg.StandardButton = QMessageBox.StandardButton
    mock_msg.Icon = QMessageBox.Icon
    mock_msg.ButtonRole = QMessageBox.ButtonRole
    mock_msg.warning.return_value = QMessageBox.StandardButton.No
    monkeypatch.setattr("guideit_master.psstore.ui.launcher_view.QMessageBox", mock_msg)
    sc.runner.execute_script = MagicMock()

    win.event_bus.run_script_requested.emit(
        "04_Devices/Reset-PrintSpooler.ps1",
        {"ClearQueueFiles": "false"},
    )
    qapp.processEvents()

    mock_msg.warning.assert_called_once()
    sc.runner.execute_script.assert_not_called()
    assert sc.param_form.get_parameter_values()["ClearQueueFiles"] is False


def test_reverse_used_in_playbooks_navigation_and_visibility(
    shell_window_factory, qapp
) -> None:
    win = shell_window_factory()
    win.show()
    sc = win.scripts_workspace

    # 1. Script referenced by prt-001 shows clickable pill and navigates to Playbooks mode
    assert sc.select_and_preload_script("04_Devices/Reset-PrintSpooler.ps1")
    qapp.processEvents()
    assert sc.used_in_playbooks_container.isVisible()
    assert "prt-001" in sc.used_in_playbook_buttons

    sc.used_in_playbook_buttons["prt-001"].click()
    qapp.processEvents()
    assert win.current_mode == MODE_PLAYBOOKS
    assert win.playbooks_workspace.viewer.current_playbook_id == "prt-001"

    # 2. Script referenced by multiple playbooks lists all referencing playbook pills
    win.set_mode(MODE_SCRIPTS)
    assert sc.select_and_preload_script("04_Devices/Get-DeviceDrivers.ps1")
    qapp.processEvents()
    assert {"prt-003", "win-003", "win-007"}.issubset(sc.used_in_playbook_buttons.keys())

    # 3. Unlinked script hides the Used in Playbooks row
    assert sc.select_and_preload_script("99_Custom/Sample-CustomDiagnostic.ps1")
    qapp.processEvents()
    assert not sc.used_in_playbooks_container.isVisible()
    assert sc.used_in_playbook_buttons == {}


def test_unified_bilingual_search_omnibox_and_cli(
    shell_window_factory, tmp_path: Path, capsys, qapp
) -> None:
    guideit_db = tmp_path / "guideit.db"
    build_index(REPO_ROOT, db_path=guideit_db)

    ps_db = tmp_path / "psstore.db"
    ps_repo = CatalogRepo(db_path=ps_db)
    ScriptScanner(scripts_dir=get_ps_scripts_dir(REPO_ROOT), repo=ps_repo).sync_catalog()

    # French symptom query matches both id-001 and linked scripts
    fr_resp = search_all(
        "compte verrouille",
        guideit_db_path=guideit_db,
        catalog_repo=ps_repo,
        root_dir=REPO_ROOT,
    )
    assert fr_resp.playbook_hits[0].id == "id-001"
    assert any(
        h.relative_path == "05_Security_Defender/Get-LocalAccountStatus.ps1"
        for h in fr_resp.script_hits
    )

    # French OneDrive query boosts Reset-OneDriveSync.ps1
    od_resp = search_all(
        "onedrive bloque",
        guideit_db_path=guideit_db,
        catalog_repo=ps_repo,
        root_dir=REPO_ROOT,
    )
    assert od_resp.playbook_hits[0].id == "m365-005"
    assert od_resp.script_hits[0].relative_path == "03_M365/Reset-OneDriveSync.ps1"

    # CLI JSON output preserves GuideIT keys and adds script_hits
    exit_code = search_cli.main(
        ["0x0000011b", "--json", "--db", str(guideit_db), "--ps-db", str(ps_db)]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["hits"][0]["id"] == "prt-001"
    assert payload["total_script_hits"] >= 2
    assert any(
        s["relative_path"] == "04_Devices/Reset-PrintSpooler.ps1"
        for s in payload["script_hits"]
    )

    # UnifiedShellWindow Omnibox search & item activation
    win = shell_window_factory(guideit_db=guideit_db)
    win.show()
    omni_resp = win.run_unified_search("0x0000011b")
    qapp.processEvents()

    assert win.omnibox_popup.isVisible()
    assert omni_resp.playbook_hits[0].id == "prt-001"
    assert win.omnibox_results_list.count() >= 4

    # Activate the script item in omnibox_results_list
    script_item = None
    for idx in range(win.omnibox_results_list.count()):
        item = win.omnibox_results_list.item(idx)
        data = item.data(Qt.ItemDataRole.UserRole)
        if data == ("script", "04_Devices/Reset-PrintSpooler.ps1"):
            script_item = item
            break
    assert script_item is not None
    win._on_omnibox_item_activated(script_item)
    qapp.processEvents()

    assert not win.omnibox_popup.isVisible()
    assert win.current_mode == MODE_SCRIPTS
    assert win.scripts_workspace._current_script is not None
    assert (
        win.scripts_workspace._current_script.relative_path
        == "04_Devices/Reset-PrintSpooler.ps1"
    )


def test_health_pill_reflects_broken_linked_scripts(
    shell_window_factory, tmp_path: Path, qapp
) -> None:
    _create_minimal_repo(
        tmp_path,
        linked_scripts_yaml="linked_scripts:\n  - 04_Devices/Missing-Script.ps1\n",
        copy_scripts=[],
    )
    tmp_db = tmp_path / "broken_guideit.db"
    build_index(tmp_path, db_path=tmp_db)

    win = shell_window_factory(
        playbooks_root_dir=tmp_path,
        guideit_db=tmp_db,
    )
    qapp.processEvents()

    assert win.health_pill_btn.property("status") == "err"
    assert "Error" in win.health_pill_btn.text()
    assert "linked_scripts" in win.health_pill_btn.toolTip()

    # CrossLinkService gracefully flags missing script as exists=False
    svc = CrossLinkService(guideit_db_path=tmp_db, catalog_repo=win.scripts_workspace.repo)
    summaries = svc.get_scripts_for_playbook("prt-001")
    assert len(summaries) == 1
    assert summaries[0].exists is False


def test_bidirectional_zero_ui_cross_imports_and_clean_services_layer() -> None:
    src_root = REPO_ROOT / "src" / "guideit_master"
    forbidden_runtime = {"sqlite3", "subprocess", "hashlib"}

    ui_trees = [
        (src_root / "guideit" / "ui", "guideit_master.psstore"),
        (src_root / "psstore" / "ui", "guideit_master.guideit"),
        (src_root / "ui", None),
    ]

    for directory, forbidden_prefix in ui_trees:
        for py_file in sorted(directory.rglob("*.py")):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                else:
                    continue
                for mod_name in names:
                    top = mod_name.split(".")[0]
                    assert top not in forbidden_runtime, (
                        f"Forbidden import '{mod_name}' in UI module {py_file}"
                    )
                    if forbidden_prefix:
                        assert not mod_name.startswith(forbidden_prefix), (
                            f"Forbidden cross-UI import '{mod_name}' in {py_file}"
                        )

    # Services layer must remain PySide6-free and sqlite3-free
    services_dir = src_root / "services"
    for py_file in sorted(services_dir.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for mod_name in names:
                top = mod_name.split(".")[0]
                assert top not in {"PySide6", "sqlite3"}, (
                    f"Service {py_file} must stay UI/SQLite agnostic (found '{mod_name}')"
                )
