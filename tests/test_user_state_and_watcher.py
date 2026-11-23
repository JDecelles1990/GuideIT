"""Tests for persistent UserStateService, debounced live playbook watcher, and Favorites/Recents UI."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QEventLoop, QTimer

from guideit_master import paths
from guideit_master.core.event_bus import AppEventBus
from guideit_master.guideit.indexer import build_index
from guideit_master.guideit.ui.main_window import PlaybooksWorkspaceWidget
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo
from guideit_master.psstore.services.scanner import ScriptScanner
from guideit_master.services.cross_link_service import CrossLinkService
from guideit_master.services.user_state_service import MAX_RECENT_ITEMS, UserStateService
from guideit_master.ui.shell_window import MODE_PLAYBOOKS, MODE_SCRIPTS, MODE_SPLIT

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_test_playbook(
    path: Path,
    *,
    pb_id: str,
    domain: str,
    subject: str,
    subcategory: str,
    title: str,
    linked_scripts: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    linked_yaml = ""
    if linked_scripts:
        items = "\n".join(f"  - {item}" for item in linked_scripts)
        linked_yaml = f"linked_scripts:\n{items}\n"
    path.write_text(
        (
            "---\n"
            f"id: {pb_id}\n"
            f"domain: {domain}\n"
            f'subject: "{subject}"\n'
            f"subcategory: {subcategory}\n"
            f"title: {title}\n"
            "tier: L1\n"
            "keywords_en: [printer stuck, spooler]\n"
            "keywords_fr: [imprimante bloquee]\n"
            'error_codes: ["0x0000011b"]\n'
            "tags: [print_spooler]\n"
            "os: [windows]\n"
            "environment: [local_endpoint]\n"
            "tools: [PowerShell]\n"
            "risk_level: low\n"
            "requires_admin: false\n"
            "last_verified: 2026-11-22\n"
            "related_ids: []\n"
            f"{linked_yaml}"
            "---\n\n"
            "## Fast Triage (Under 2 Minutes)\n"
            "- Check impact scope.\n\n"
            "## Read-Only Diagnostics (L1-L2)\n"
            "- Inspect queue state.\n\n"
            "## Deep-Dive Investigation (L3)\n"
            "- Inspect spooler trace.\n\n"
            "## Remediation (Confirm Before Running)\n"
            "- **[REMEDIATION — CONFIRM BEFORE RUNNING]** Restart spooler.\n\n"
            "## Verification & Post-Fix Checks\n"
            "- Confirm test page prints.\n"
        ),
        encoding="utf-8",
    )


def _create_watch_repo(root: Path) -> tuple[Path, Path]:
    shutil.copytree(REPO_ROOT / "taxonomy", root / "taxonomy")
    scripts_src = paths.get_ps_scripts_dir(REPO_ROOT) / "04_Devices"
    scripts_dst = root / "powershell_scripts" / "04_Devices"
    scripts_dst.mkdir(parents=True, exist_ok=True)
    for name in ("Get-PrintQueues.ps1", "Reset-PrintSpooler.ps1"):
        shutil.copy2(scripts_src / name, scripts_dst / name)

    pb_prt = root / "playbooks" / "05_Printers_Devices" / "prt-001-spooler-watch.md"
    _write_test_playbook(
        pb_prt,
        pb_id="prt-001",
        domain="05_Printers_Devices",
        subject="Printers & Peripherals",
        subcategory="printers_spooler_scan",
        title="Original Spooler Title",
        linked_scripts=["04_Devices/Get-PrintQueues.ps1"],
    )

    pb_id = root / "playbooks" / "01_Identity_AD_Entra" / "id-001-lockout-watch.md"
    _write_test_playbook(
        pb_id,
        pb_id="id-001",
        domain="01_Identity_AD_Entra",
        subject="Identity / AD & Entra ID",
        subcategory="lockout_mfa_recovery",
        title="Lockout Watch Playbook",
        linked_scripts=[],
    )
    return pb_prt, pb_id


def test_user_state_service_persistence_mru_cap_and_atomic_write(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv(paths.ENV_DATA_DIR, raising=False)
    local_app_data = tmp_path / "local_appdata"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "meipass"), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    expected_frozen_state = (local_app_data / paths.APP_NAME / "user_state.json").resolve()
    assert paths.get_user_state_path() == expected_frozen_state

    svc = UserStateService(state_path=expected_frozen_state)
    assert svc.get_favorite_playbooks() == []
    assert svc.get_recent_playbooks() == []
    assert svc.get_favorite_scripts() == []
    assert svc.get_recent_scripts() == []

    # Toggle favorites
    assert svc.toggle_favorite_playbook("prt-001") is True
    assert svc.toggle_favorite_playbook("net-001") is True
    assert svc.toggle_favorite_script("04_Devices\\Get-PrintQueues.ps1") is True
    assert svc.is_favorite_playbook("prt-001") is True
    assert svc.is_favorite_script("04_Devices/Get-PrintQueues.ps1") is True

    # Record more than MAX_RECENT_ITEMS (8) entries in MRU order and verify capping + promotion
    for idx in range(1, 12):
        svc.record_recent_playbook(f"pb-{idx:03d}")
        svc.record_recent_script(f"01_System/Script-{idx:02d}.ps1")
    svc.record_recent_playbook("pb-005")
    svc.record_recent_script("01_System/Script-06.ps1")

    assert len(svc.get_recent_playbooks()) == MAX_RECENT_ITEMS
    assert svc.get_recent_playbooks()[0] == "pb-005"
    assert "pb-001" not in svc.get_recent_playbooks()
    assert len(svc.get_recent_scripts()) == MAX_RECENT_ITEMS
    assert svc.get_recent_scripts()[0] == "01_System/Script-06.ps1"
    assert "01_System/Script-01.ps1" not in svc.get_recent_scripts()

    # No leftover .tmp file after atomic os.replace()
    tmp_sibling = expected_frozen_state.with_name("user_state.json.tmp")
    assert expected_frozen_state.is_file()
    assert not tmp_sibling.exists()

    # Survives DB deletion/rebuild and fresh UserStateService reload
    db_file = local_app_data / paths.APP_NAME / "guideit.db"
    build_index(REPO_ROOT, db_path=db_file)
    db_file.unlink()
    build_index(REPO_ROOT, db_path=db_file)

    reloaded = UserStateService(state_path=expected_frozen_state)
    assert reloaded.get_favorite_playbooks() == ["prt-001", "net-001"]
    assert reloaded.get_favorite_scripts() == ["04_Devices/Get-PrintQueues.ps1"]
    assert reloaded.get_recent_playbooks()[0] == "pb-005"
    assert reloaded.get_recent_scripts()[0] == "01_System/Script-06.ps1"


def test_user_state_service_missing_and_corrupt_json_recovery(tmp_path: Path) -> None:
    missing_path = tmp_path / "does_not_exist" / "user_state.json"
    svc_missing = UserStateService(state_path=missing_path)
    assert svc_missing.get_favorite_playbooks() == []
    assert svc_missing.get_recent_scripts() == []

    corrupt_path = tmp_path / "corrupt_user_state.json"
    corrupt_path.write_text("{not valid json!!!", encoding="utf-8")
    svc_corrupt = UserStateService(state_path=corrupt_path)
    assert svc_corrupt.get_favorite_playbooks() == []
    assert svc_corrupt.get_recent_playbooks() == []

    # Non-dict JSON root recovers cleanly
    corrupt_path.write_text('["not", "an", "object"]', encoding="utf-8")
    svc_list = UserStateService(state_path=corrupt_path)
    assert svc_list.get_favorite_playbooks() == []

    # Dirty values inside dict are normalized and sanitized
    corrupt_path.write_text(
        json.dumps(
            {
                "favorite_playbooks": [" prt-001 ", 123, "", "prt-001", "net-001"],
                "recent_playbooks": [f"id-{i:03d}" for i in range(15)],
                "favorite_scripts": ["\\04_Devices\\Get-PrintQueues.ps1", None],
                "recent_scripts": "not-a-list",
            }
        ),
        encoding="utf-8",
    )
    svc_dirty = UserStateService(state_path=corrupt_path)
    assert svc_dirty.get_favorite_playbooks() == ["prt-001", "net-001"]
    assert len(svc_dirty.get_recent_playbooks()) == MAX_RECENT_ITEMS
    assert svc_dirty.get_favorite_scripts() == ["04_Devices/Get-PrintQueues.ps1"]
    assert svc_dirty.get_recent_scripts() == []

    # Saving self-heals file cleanly
    svc_dirty.toggle_favorite_playbook("win-001")
    reloaded = UserStateService(state_path=corrupt_path)
    assert reloaded.get_favorite_playbooks() == ["prt-001", "net-001", "win-001"]


def test_playbook_watcher_recursive_dirs_dynamic_domain_and_frozen_skip(
    tmp_path: Path, monkeypatch, qapp
) -> None:
    _create_watch_repo(tmp_path)
    db_path = tmp_path / "guideit.db"
    ws = PlaybooksWorkspaceWidget(root_dir=tmp_path, db_path=db_path)
    try:
        watched_dirs = {Path(p).resolve() for p in ws.watcher.directories()}
        assert (tmp_path / "playbooks").resolve() in watched_dirs
        assert (tmp_path / "playbooks" / "05_Printers_Devices").resolve() in watched_dirs
        assert (tmp_path / "playbooks" / "01_Identity_AD_Entra").resolve() in watched_dirs
        assert (tmp_path / "taxonomy").resolve() in watched_dirs

        # Dynamically created domain subdirectory is registered on _on_fs_changed
        new_domain = tmp_path / "playbooks" / "09_Apps_LOB"
        new_domain.mkdir(parents=True, exist_ok=True)
        ws._on_fs_changed(str(tmp_path / "playbooks"))
        ws._reindex_debounce_timer.stop()
        watched_after = {Path(p).resolve() for p in ws.watcher.directories()}
        assert new_domain.resolve() in watched_after
    finally:
        ws.shutdown_workers()
        ws.close()
        ws.deleteLater()
        qapp.processEvents()

    # Frozen PyInstaller mode skips watching read-only _MEIPASS paths cleanly
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    ws_frozen = PlaybooksWorkspaceWidget(
        root_dir=tmp_path,
        db_path=tmp_path / "frozen_guideit.db",
    )
    try:
        assert ws_frozen.watcher.directories() == []
        assert ws_frozen.watcher.files() == []
    finally:
        ws_frozen.shutdown_workers()
        ws_frozen.close()
        ws_frozen.deleteLater()
        qapp.processEvents()


def test_playbook_watcher_500ms_debounce_coalescing_and_pending_reindex(
    tmp_path: Path, qapp
) -> None:
    pb_prt, _pb_id = _create_watch_repo(tmp_path)
    db_path = tmp_path / "guideit.db"

    ps_repo = CatalogRepo(db_path=tmp_path / "psstore.db")
    ScriptScanner(scripts_dir=tmp_path / "powershell_scripts", repo=ps_repo).sync_catalog()
    bus = AppEventBus()
    cross_link = CrossLinkService(guideit_db_path=db_path, catalog_repo=ps_repo)

    ws = PlaybooksWorkspaceWidget(
        root_dir=tmp_path,
        db_path=db_path,
        event_bus=bus,
        cross_link_service=cross_link,
    )
    try:
        # Default debounce interval must be 500ms
        assert ws._reindex_debounce_timer.interval() == 500

        # 5 rapid filesystem bursts coalesce into a single start_reindex(auto_triggered=True)
        calls: list[bool] = []
        orig_start = ws.start_reindex
        ws.start_reindex = lambda *, auto_triggered=False: calls.append(auto_triggered)
        ws._reindex_debounce_timer.setInterval(40)
        for _ in range(5):
            ws._on_fs_changed(str(pb_prt))

        loop_coalesce = QEventLoop()
        QTimer.singleShot(140, loop_coalesce.quit)
        loop_coalesce.exec()
        assert calls == [True]

        # In-flight worker queues _pending_reindex and runs one follow-up reindex on completion
        calls.clear()
        fake_worker = MagicMock()
        fake_worker.isRunning.return_value = True
        ws._worker = fake_worker
        ws._on_fs_changed(str(pb_prt))
        ws._on_reindex_debounce_timeout()
        assert ws._pending_reindex is True
        assert calls == []

        ws._worker = None
        ws._on_reindex_completed(ws.last_report, MagicMock(indexed_count=2))
        qapp.processEvents()
        assert calls == [True]
        assert ws._pending_reindex is False
        ws.start_reindex = orig_start

        # Real live QFileSystemWatcher test on disk edit refreshes viewer, health, cross-link & toast
        ws._reindex_debounce_timer.setInterval(80)
        ws.navigate_to_playbook("prt-001")
        qapp.processEvents()
        assert ws.viewer.current_playbook_id == "prt-001"
        assert ws.viewer.current_record is not None
        assert ws.viewer.current_record["title"] == "Original Spooler Title"

        toasts: list[str] = []
        ws.status_message_requested.connect(lambda msg, _t: toasts.append(msg))
        cross_link.invalidate_cache = MagicMock(wraps=cross_link.invalidate_cache)

        reindex_loop = QEventLoop()
        bus.playbooks_reindexed.connect(reindex_loop.quit)
        QTimer.singleShot(5000, reindex_loop.quit)

        _write_test_playbook(
            pb_prt,
            pb_id="prt-001",
            domain="05_Printers_Devices",
            subject="Printers & Peripherals",
            subcategory="printers_spooler_scan",
            title="Live Updated Spooler Title",
            linked_scripts=[
                "04_Devices/Get-PrintQueues.ps1",
                "04_Devices/Reset-PrintSpooler.ps1",
            ],
        )
        reindex_loop.exec()
        qapp.processEvents()

        assert ws.viewer.current_record["title"] == "Live Updated Spooler Title"
        assert "04_Devices/Reset-PrintSpooler.ps1" in ws.viewer.linked_script_cards
        assert ws.last_report is not None
        assert ws.last_report.errors == []
        assert ws.last_report.checked_files == 2
        if ws.last_report.warnings:
            assert ws.health_button.text() == f"⚠ {len(ws.last_report.warnings)} Warning(s)"
        else:
            assert ws.health_button.text() == f"✓ {ws.last_report.checked_files} Valid"
        assert cross_link.invalidate_cache.call_count >= 1
        assert any(
            msg == "Auto-reindexed playbooks after file change" for msg in toasts
        )
    finally:
        ws.shutdown_workers()
        ws.close()
        ws.deleteLater()
        qapp.processEvents()


def test_favorites_recents_strip_pin_buttons_ctrl_d_and_reload_persistence(
    shell_window_factory, tmp_path: Path, qapp
) -> None:
    state_file = tmp_path / "shared_user_state.json"
    shared_state = UserStateService(state_path=state_file)
    db_file = tmp_path / "live_guideit.db"
    build_index(REPO_ROOT, db_path=db_file)

    win = shell_window_factory(guideit_db=db_file, user_state_service=shared_state)
    win.show()
    pb = win.playbooks_workspace
    sc = win.scripts_workspace
    viewer = pb.viewer

    # Initial population must NOT pollute recent lists
    assert shared_state.get_recent_playbooks() == []
    assert shared_state.get_recent_scripts() == []
    assert pb.favorites_strip.isVisible() is False
    assert sc.favorites_strip.isVisible() is False

    # 1. Playbooks: navigating records MRU recents and shows strip
    win.set_mode(MODE_PLAYBOOKS)
    pb.navigate_to_playbook("prt-001")
    pb.navigate_to_playbook("net-001")
    pb.navigate_to_playbook("win-003")
    qapp.processEvents()

    assert shared_state.get_recent_playbooks()[:3] == ["win-003", "net-001", "prt-001"]
    assert pb.favorites_strip.isVisible() is True
    assert {"win-003", "net-001", "prt-001"}.issubset(pb.recent_playbook_buttons.keys())
    assert "Print Spooler" in pb.recent_playbook_buttons["prt-001"].toolTip()

    # 2. Pin via PlaybookViewer header button + Ctrl+D shortcut
    assert viewer.pin_button is not None
    assert viewer.pin_button.text() == "☆ Pin"
    viewer.pin_button.click()  # pins win-003
    qapp.processEvents()
    assert viewer.pin_button.text() == "★ Pinned"
    assert viewer.pin_button.property("pinned") is True
    assert "win-003" in pb.favorite_playbook_buttons
    assert "win-003" not in pb.recent_playbook_buttons
    assert (
        pb.favorite_playbook_buttons["win-003"].x()
        < pb.recent_playbook_buttons["net-001"].x()
    )

    pb.navigate_to_playbook("id-001")
    qapp.processEvents()
    win.shortcuts["toggle_pin_favorite"].activated.emit()  # Ctrl+D pins id-001
    qapp.processEvents()
    assert viewer.pin_button.text() == "★ Pinned"
    assert set(shared_state.get_favorite_playbooks()) == {"win-003", "id-001"}

    # Clicking favorite pill jumps directly to that playbook
    pb.favorite_playbook_buttons["win-003"].click()
    qapp.processEvents()
    assert viewer.current_playbook_id == "win-003"

    # Collapsing & expanding strip toggles pill container cleanly
    pb.favorites_strip_toggle_btn.click()
    qapp.processEvents()
    assert pb.favorites_pills_scroll.isVisible() is False
    assert "▸" in pb.favorites_strip_toggle_btn.text()
    pb.favorites_strip_toggle_btn.click()
    qapp.processEvents()
    assert pb.favorites_pills_scroll.isVisible() is True
    assert "▾" in pb.favorites_strip_toggle_btn.text()

    # Split View hides quick strips cleanly; exiting restores Playbooks strip
    win.set_mode(MODE_SPLIT)
    qapp.processEvents()
    assert pb.favorites_strip.isVisible() is False
    assert sc.favorites_strip.isVisible() is False

    # 3. Scripts: selection records MRU, Pin button & Ctrl+D work, ★ Pinned Only filters catalog
    win.set_mode(MODE_SCRIPTS)
    qapp.processEvents()
    assert sc.select_and_preload_script("04_Devices/Get-PrintQueues.ps1")
    assert sc.select_and_preload_script("02_Network/Test-PortConnectivity.ps1")
    qapp.processEvents()

    assert shared_state.get_recent_scripts()[:2] == [
        "02_Network/Test-PortConnectivity.ps1",
        "04_Devices/Get-PrintQueues.ps1",
    ]
    assert sc.favorites_strip.isVisible() is True
    assert sc.pin_script_btn.isEnabled() is True
    assert sc.pin_script_btn.text() == "☆ Pin"

    sc.pin_script_btn.click()  # pins Test-PortConnectivity.ps1
    qapp.processEvents()
    assert sc.pin_script_btn.text() == "★ Pinned"
    assert "02_Network/Test-PortConnectivity.ps1" in sc.favorite_script_buttons

    assert sc.select_and_preload_script("01_System/Get-OSInformation.ps1")
    qapp.processEvents()
    win.shortcuts["toggle_pin_favorite"].activated.emit()  # Ctrl+D pins Get-OSInformation.ps1
    qapp.processEvents()
    assert sc.pin_script_btn.text() == "★ Pinned"

    # ★ Pinned Only filter restricts CatalogTableView to pinned scripts only
    total_before = len(sc.catalog_view._scripts)
    assert total_before > 2
    sc.sidebar.pinned_only_checkbox.setChecked(True)
    qapp.processEvents()
    pinned_visible = {s.relative_path for s in sc.catalog_view._scripts}
    assert pinned_visible == {
        "02_Network/Test-PortConnectivity.ps1",
        "01_System/Get-OSInformation.ps1",
    }

    # Clicking a recent unpinned script pill auto-clears filter and selects it
    sc.recent_script_buttons["04_Devices/Get-PrintQueues.ps1"].click()
    qapp.processEvents()
    assert sc.sidebar.pinned_only_checkbox.isChecked() is False
    assert sc._current_script is not None
    assert sc._current_script.relative_path == "04_Devices/Get-PrintQueues.ps1"

    # 4. Persistence across DB rebuild & fresh UnifiedShellWindow
    db_file.unlink()
    build_index(REPO_ROOT, db_path=db_file)
    reloaded_state = UserStateService(state_path=state_file)
    win2 = shell_window_factory(guideit_db=db_file, user_state_service=reloaded_state)
    win2.show()
    win2.set_mode(MODE_PLAYBOOKS)
    qapp.processEvents()

    assert set(win2.playbooks_workspace.favorite_playbook_buttons.keys()) == {
        "win-003",
        "id-001",
    }
    assert set(win2.scripts_workspace.favorite_script_buttons.keys()) == {
        "02_Network/Test-PortConnectivity.ps1",
        "01_System/Get-OSInformation.ps1",
    }
    win2.playbooks_workspace.navigate_to_playbook("win-003")
    qapp.processEvents()
    assert win2.playbooks_workspace.viewer.pin_button is not None
    assert win2.playbooks_workspace.viewer.pin_button.text() == "★ Pinned"
