"""Windows startup registry, global Win+F8 hotkey, tray & foreground visibility tests."""

from __future__ import annotations

import ctypes
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

from guideit_master.psstore.services.hotkey_service import (
    DEFAULT_HOTKEY_ID,
    GlobalHotkeyManager,
)
from guideit_master.psstore.services.startup_service import APP_REG_NAME, StartupService


def test_startup_service_command_and_mocked_registry(monkeypatch, tmp_path: Path) -> None:
    main_py = tmp_path / "main.py"
    main_py.write_text("# stub", encoding="utf-8")

    svc = StartupService(main_script_path=main_py)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    cmd = svc.get_launch_command("--startup")
    assert str(main_py.resolve()) in cmd
    assert cmd.endswith(" --startup")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "GuideIT_Master.exe"))
    frozen_cmd = svc.get_launch_command("--startup")
    assert "GuideIT_Master.exe" in frozen_cmd
    assert frozen_cmd.endswith(" --startup")

    # Mock winreg so the real HKCU Run key is never touched
    fake_store: dict[str, str] = {}

    class _FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    fake_winreg = types.SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        KEY_READ=1,
        KEY_SET_VALUE=2,
        REG_SZ=1,
        OpenKey=lambda root, sub, res, acc: _FakeKey(),
        QueryValueEx=lambda k, name: (
            (fake_store[name], 1)
            if name in fake_store
            else (_ for _ in ()).throw(FileNotFoundError())
        ),
        SetValueEx=lambda k, name, r, t, val: fake_store.__setitem__(name, val),
        DeleteValue=lambda k, name: (
            fake_store.pop(name)
            if name in fake_store
            else (_ for _ in ()).throw(FileNotFoundError())
        ),
    )
    monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

    assert svc.is_startup_enabled() is False
    assert svc.toggle_startup(True) is True
    assert svc.is_startup_enabled() is True
    assert APP_REG_NAME in fake_store
    assert svc.toggle_startup(False) is True
    assert svc.is_startup_enabled() is False


def test_global_hotkey_manager_lifecycle(qapp, monkeypatch) -> None:
    mgr = GlobalHotkeyManager(hotkey_id=0x5099)
    fake_user32 = MagicMock()
    fake_user32.RegisterHotKey.return_value = 1
    fake_user32.UnregisterHotKey.return_value = 1

    monkeypatch.setattr(ctypes.windll, "user32", fake_user32)

    hits: list[bool] = []
    mgr.triggered.connect(lambda: hits.append(True))

    assert mgr.register(123456) is True
    assert mgr.is_registered is True
    mgr._on_hotkey_received(0x5099)
    mgr._on_hotkey_received(DEFAULT_HOTKEY_ID + 1)  # ignored mismatch
    assert hits == [True]

    assert mgr.unregister() is True
    assert mgr.is_registered is False


def test_shell_window_startup_tray_sync_and_visibility_toggle(
    shell_window_factory, monkeypatch
) -> None:
    win = shell_window_factory()
    ws = win.scripts_workspace

    # Sidebar checkbox -> Shell StartupService & tray menu stay synchronized
    assert win.startup_service.is_startup_enabled() is False
    ws.sidebar.startup_checkbox.setChecked(True)
    assert win.startup_service.is_startup_enabled() is True
    if hasattr(win, "action_tray_startup"):
        assert win.action_tray_startup.isChecked() is True
        win.action_tray_startup.setChecked(False)
        assert win.startup_service.is_startup_enabled() is False
        assert ws.sidebar.startup_checkbox.isChecked() is False

    # Foreground visibility toggle
    mock_fg = MagicMock(return_value=True)
    monkeypatch.setattr(
        "guideit_master.ui.shell_window.bring_window_to_foreground",
        mock_fg,
    )
    win.hide()
    win.toggle_window_visibility()
    assert not win.isHidden()
    mock_fg.assert_called_once()
