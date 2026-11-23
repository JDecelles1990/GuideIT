"""UnifiedShellWindow architecture, Split View, EventBus & refinement guard tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from guideit_master.core.event_bus import AppEventBus
from guideit_master.guideit.ui.main_window import PlaybooksWorkspaceWidget
from guideit_master.psstore.services.hotkey_service import GlobalHotkeyManager
from guideit_master.psstore.ui.launcher_view import ScriptsWorkspaceWidget
from guideit_master.ui.shell_window import (
    MODE_PLAYBOOKS,
    MODE_SCRIPTS,
    MODE_SPLIT,
)


def test_permanent_splitter_split_view_without_reparenting(shell_window_factory) -> None:
    win = shell_window_factory()
    win.show()

    pb = win.playbooks_workspace
    sc = win.scripts_workspace
    assert isinstance(pb, PlaybooksWorkspaceWidget)
    assert win.health_pill_btn.text() == "✓ 65 Valid"
    assert pb.parentWidget() is win.mode_splitter
    assert sc.parentWidget() is win.mode_splitter
    assert win.mode_splitter.indexOf(pb) == 0
    assert win.mode_splitter.indexOf(sc) == 1

    # Default Phase 1 mode: Scripts
    assert win.current_mode == MODE_SCRIPTS
    assert not pb.isVisible()
    assert sc.isVisible()
    assert sc.is_compact_mode is False
    assert sc.sidebar.isVisible()
    assert sc.catalog_view.isVisible()

    # Switch to Playbooks mode
    win.set_mode(MODE_PLAYBOOKS)
    assert win.current_mode == MODE_PLAYBOOKS
    assert pb.isVisible()
    assert not sc.isVisible()
    assert pb.is_compact_mode is False
    assert pb.top_bar.isVisible()
    assert pb.filter_sidebar.isVisible()
    assert pb.results_list.isVisible()
    assert pb.viewer.isVisible()
    assert pb.parentWidget() is win.mode_splitter
    assert sc.parentWidget() is win.mode_splitter

    # Switch to Split View (Alt+3): compact mode enabled without reparenting
    win.set_mode(MODE_SPLIT)
    assert win.current_mode == MODE_SPLIT
    assert pb.isVisible()
    assert sc.isVisible()
    assert pb.is_compact_mode is True
    assert not pb.top_bar.isVisible()
    assert not pb.filter_sidebar.isVisible()
    assert not pb.results_list.isVisible()
    assert pb.viewer.isVisible()
    assert sc.is_compact_mode is True
    assert not sc.sidebar.isVisible()
    assert not sc.catalog_view.isVisible()
    assert pb.parentWidget() is win.mode_splitter
    assert sc.parentWidget() is win.mode_splitter

    # Exit back to Scripts restores catalog & sidebar without creating duplicate workspaces
    win.set_mode(MODE_SCRIPTS)
    assert win.scripts_workspace is sc
    assert not pb.isVisible()
    assert sc.isVisible()
    assert sc.is_compact_mode is False
    assert sc.catalog_view.isVisible()
    assert sc.sidebar.isVisible()


def test_single_shell_owner_and_zero_legacy_shims(shell_window_factory) -> None:
    win = shell_window_factory()
    sc = win.scripts_workspace
    assert isinstance(sc, ScriptsWorkspaceWidget)

    # ScriptsWorkspaceWidget must NOT own shell-level services
    assert not hasattr(sc, "tray_icon")
    assert not hasattr(sc, "hotkey_manager")
    assert not hasattr(sc, "startup_service")
    assert not hasattr(sc, "opacity_slider")

    # UnifiedShellWindow is the sole owner of shell services
    assert isinstance(win.hotkey_manager, GlobalHotkeyManager)
    assert hasattr(win, "opacity_slider")
    assert hasattr(win, "startup_service")
    assert isinstance(win.event_bus, AppEventBus)

    # Zero legacy top-level compatibility shim packages under src/
    src_root = Path(__file__).resolve().parents[2] / "src"
    for forbidden_shim in ("guideit", "repositories", "services", "ui"):
        assert not (src_root / forbidden_shim).exists(), (
            f"Legacy compatibility shim src/{forbidden_shim} must not exist"
        )


def test_event_bus_open_copy_and_playbook_signals(shell_window_factory) -> None:
    win = shell_window_factory()
    win.show()
    sc = win.scripts_workspace
    sc.clipboard_service.copy_to_clipboard = MagicMock(return_value=True)

    # Open linked script with parameter overrides and Split View
    win.event_bus.open_script_requested.emit(
        "02_Network/Test-PortConnectivity.ps1",
        {"TargetHost": "dc01.domain.local", "Port": 636},
        True,
    )
    assert win.current_mode == MODE_SPLIT
    assert sc._current_script is not None
    assert sc._current_script.relative_path == "02_Network/Test-PortConnectivity.ps1"
    vals = sc.param_form.get_parameter_values()
    assert vals["TargetHost"] == "dc01.domain.local"
    assert vals["Port"] == 636

    # Copy RMM-ready via EventBus
    win.event_bus.copy_script_requested.emit(
        "04_Devices/Reset-PrintSpooler.ps1",
        {"ClearQueueFiles": False},
        True,
    )
    sc.clipboard_service.copy_to_clipboard.assert_called_once()
    copied = sc.clipboard_service.copy_to_clipboard.call_args[0][0]
    assert "[bool]$ClearQueueFiles = $false" in copied

    # Open playbook signal switches shell to Playbooks or Split mode and navigates viewer
    win.event_bus.open_playbook_requested.emit("win-001", False)
    assert win.current_mode == MODE_PLAYBOOKS
    assert win.playbooks_workspace.viewer.current_playbook_id == "win-001"
