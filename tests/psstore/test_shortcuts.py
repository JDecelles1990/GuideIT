"""Keyboard shortcuts, tooltips & documentation sync verification tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QUrl

from guideit_master.ui.shell_window import MODE_PLAYBOOKS, MODE_SCRIPTS, MODE_SPLIT


def test_all_shortcuts_registered_and_unique(shell_window_factory) -> None:
    win = shell_window_factory()
    assert len(win.shortcuts) == 34
    assert win.shortcut_sidebar is win.shortcuts["toggle_sidebar"]
    assert "focus_playbook_search" in win.shortcuts
    assert "focus_unified_search" in win.shortcuts
    assert "useful_tools" in win.shortcuts
    assert "reset_playbook_filters" in win.shortcuts
    assert "playbook_back" in win.shortcuts
    assert "copy_linked_readonly_bundle" in win.shortcuts
    assert "toggle_pin_favorite" in win.shortcuts

    seen_sequences: dict[str, str] = {}
    for name, sc in win.shortcuts.items():
        for seq in sc.keys():
            key_text = seq.toString()
            assert key_text not in seen_sequences, (
                f"Duplicate shortcut sequence '{key_text}' between '{seen_sequences[key_text]}' and '{name}'"
            )
            seen_sequences[key_text] = name


def test_mode_search_escape_tab_and_parameter_shortcuts(shell_window_factory) -> None:
    win = shell_window_factory()
    win.show()
    ws = win.scripts_workspace

    # Mode switching
    win.set_mode(MODE_PLAYBOOKS)
    assert win.current_mode == MODE_PLAYBOOKS
    assert win.playbooks_workspace.isVisible()
    assert not ws.isVisible()

    win.set_mode(MODE_SPLIT)
    assert win.current_mode == MODE_SPLIT
    assert win.playbooks_workspace.isVisible()
    assert ws.isVisible()
    assert ws.is_compact_mode is True

    # Focus search automatically exits Playbooks/Split to show Scripts sidebar
    win._focus_search_input()
    assert win.current_mode == MODE_SCRIPTS
    assert ws.is_compact_mode is False
    assert ws.sidebar.isVisible()

    # Focus playbook search automatically switches to Playbooks mode
    win._focus_playbook_search()
    assert win.current_mode == MODE_PLAYBOOKS
    assert win.playbooks_workspace.isVisible()
    assert not ws.isVisible()
    win.playbooks_workspace.search_input.setText("4740")
    win._handle_escape()
    assert win.playbooks_workspace.search_input.text() == ""
    win.set_mode(MODE_SCRIPTS)

    # Escape clears search filter
    ws.sidebar.search_input.setText("Disk")
    ws._handle_escape()
    assert ws.sidebar.search_input.text() == ""

    # Console tab shortcuts
    for idx in range(4):
        ws._switch_console_tab(idx)
        assert ws.console_view.currentIndex() == idx

    # Reset parameters to defaults
    disk_script = ws.repo.get_script_by_path("01_System/Get-DiskSpaceReport.ps1")
    assert disk_script is not None
    ws._on_script_selected(disk_script)
    ws.param_form.set_parameter_values({"LowSpaceThresholdPercent": 55})
    assert ws.param_form.get_parameter_values()["LowSpaceThresholdPercent"] == 55
    ws._shortcut_reset_parameters()
    assert ws.param_form.get_parameter_values()["LowSpaceThresholdPercent"] == 15


def test_action_opacity_folder_and_quit_shortcuts(shell_window_factory, monkeypatch) -> None:
    win = shell_window_factory()
    ws = win.scripts_workspace

    ws.clipboard_service.copy_to_clipboard = MagicMock(return_value=True)
    ws._on_copy_raw_clicked()
    ws._on_copy_rmm_clicked()
    assert ws.clipboard_service.copy_to_clipboard.call_count == 2

    # Opacity shortcuts
    win._adjust_opacity(-10)
    assert win.opacity_slider.value() == 90
    win._adjust_opacity(25)
    assert win.opacity_slider.value() == 100
    win._adjust_opacity(-50)
    assert win.opacity_slider.value() == 60
    win._reset_opacity()
    assert win.opacity_slider.value() == 100

    # Clear console shortcut
    ws.console_view.append_raw_output("Sample output line\n")
    assert "Sample output line" in ws.console_view.raw_console.toPlainText()
    ws._shortcut_clear_console()
    assert ws.console_view.raw_console.toPlainText() == ""

    # Open scripts folder shortcut
    mock_open = MagicMock(return_value=True)
    monkeypatch.setattr(
        "guideit_master.psstore.ui.launcher_view.QDesktopServices.openUrl",
        mock_open,
    )
    ws.open_scripts_folder()
    mock_open.assert_called_once()
    called_url = mock_open.call_args[0][0]
    assert isinstance(called_url, QUrl)

    mock_warn = MagicMock()
    monkeypatch.setattr(
        "guideit_master.psstore.ui.launcher_view.QDesktopServices.openUrl",
        lambda url: False,
    )
    monkeypatch.setattr("guideit_master.psstore.ui.launcher_view.QMessageBox.warning", mock_warn)
    ws.open_scripts_folder()
    mock_warn.assert_called_once()

    # Quit app shortcut
    mock_app = MagicMock()
    monkeypatch.setattr(
        "guideit_master.ui.shell_window.QApplication.instance",
        lambda: mock_app,
    )
    win.quit_application()
    assert win._force_quit is True
    mock_app.quit.assert_called_once()


def test_tooltips_and_docs_advertise_shortcuts_and_38_scripts(shell_window_factory) -> None:
    win = shell_window_factory()
    ws = win.scripts_workspace

    assert "Alt+1" in win.btn_mode_playbooks.toolTip()
    assert "Alt+2" in win.btn_mode_scripts.toolTip()
    assert "Alt+3" in win.btn_mode_split.toolTip()
    assert "Ctrl+T" in win.btn_useful_tools.toolTip()
    assert "Ctrl+Shift+K" in win.omnibox_input.toolTip()
    assert "Ctrl+K" in win.playbooks_workspace.search_input.toolTip()
    assert "Ctrl+R" in win.playbooks_workspace.filter_sidebar.reset_button.toolTip()
    assert "Ctrl+=" in win.opacity_slider.toolTip()
    assert "Ctrl+B" in ws.catalog_view.toggle_sidebar_btn.toolTip()
    assert "Ctrl+O" in ws.catalog_view.open_folder_btn.toolTip()
    assert "Ctrl+F" in ws.sidebar.search_input.toolTip()
    assert "F5" in ws.sidebar.sync_button.toolTip()
    assert "Ctrl+Shift+A" in ws.catalog_view.check_all_btn.toolTip()
    assert "Ctrl+Shift+O" in ws.catalog_view.check_readonly_btn.toolTip()
    assert "Ctrl+Shift+D" in ws.catalog_view.clear_checked_btn.toolTip()
    assert "Ctrl+Shift+C" in ws.copy_raw_btn.toolTip()
    assert "Ctrl+Shift+R" in ws.copy_rmm_btn.toolTip()
    assert "Ctrl+D" in ws.pin_script_btn.toolTip()
    assert "Ctrl+Enter" in ws.run_local_btn.toolTip()
    assert "Shift+F5" in ws.stop_btn.toolTip()
    assert "Ctrl+Alt+R" in ws.param_form.reset_btn.toolTip()
    assert "Ctrl+Shift+T" in ws.console_view.copy_report_btn.toolTip()
    assert "Ctrl+S" in ws.console_view.save_report_btn.toolTip()
    assert "Ctrl+L" in ws.console_view.clear_console_btn.toolTip()

    repo_root = Path(__file__).resolve().parents[2]
    readme_text = (repo_root / "README.md").read_text(encoding="utf-8")
    gemini_text = (repo_root / "GEMINI.md").read_text(encoding="utf-8")

    expected_shortcuts = [
        "Win+F8",
        "Alt+1",
        "Alt+2",
        "Alt+3",
        "Ctrl+B",
        "Ctrl+O",
        "Ctrl+F",
        "Ctrl+K",
        "Ctrl+Shift+K",
        "Ctrl+T",
        "Ctrl+R",
        "Alt+Left",
        "Ctrl+Shift+B",
        "Ctrl+D",
        "F5",
        "Esc",
        "Ctrl+Shift+A",
        "Ctrl+Shift+O",
        "Ctrl+Shift+D",
        "Ctrl+Shift+C",
        "Ctrl+Shift+R",
        "Ctrl+Enter",
        "Shift+F5",
        "Ctrl+Alt+R",
        "Ctrl+1",
        "Ctrl+2",
        "Ctrl+3",
        "Ctrl+4",
        "Ctrl+Shift+T",
        "Ctrl+S",
        "Ctrl+L",
        "Ctrl+=",
        "Ctrl+-",
        "Ctrl+0",
        "Ctrl+Q",
    ]
    for label in expected_shortcuts:
        assert label in readme_text, f"Shortcut {label} missing from README.md"

    ps1_names = [p.name for p in (repo_root / "powershell_scripts").rglob("*.ps1")]
    assert len(ps1_names) >= 38
    for name in ps1_names:
        assert name in readme_text, f"Script {name} missing from README.md"

    assert "powershell_scripts/" in gemini_text
    assert "Keyboard Shortcuts Documentation Rule" in gemini_text
