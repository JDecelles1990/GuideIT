"""Shared pytest fixtures and clean Qt teardown helpers for GuideIT Master."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

import pytest
from PySide6.QtWidgets import QApplication

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from guideit_master.core.event_bus import AppEventBus
from guideit_master.guideit.indexer import build_index
from guideit_master.paths import get_bundle_dir
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo
from guideit_master.psstore.services.scanner import ScriptScanner
from guideit_master.ui.backdrop_fx import BACKDROP_FX_PROPERTY
from guideit_master.ui.shell_window import MODE_SCRIPTS, UnifiedShellWindow
from guideit_master.ui.unified_theme import DARK_THEME_QSS


class DummyStartupService:
    """In-memory StartupService test double that never touches the real HKCU Run registry."""

    def __init__(self, initial_enabled: bool = False) -> None:
        self._enabled = initial_enabled

    def is_startup_enabled(self) -> bool:
        return self._enabled

    def enable_startup(self, argument: str = "--startup") -> bool:
        self._enabled = True
        return True

    def disable_startup(self) -> bool:
        self._enabled = False
        return True

    def toggle_startup(self, enable: bool, argument: str = "--startup") -> bool:
        self._enabled = bool(enable)
        return True


def close_shell_window(window: UnifiedShellWindow) -> None:
    """Safely unregisters hotkeys, stops workers/FX timers, hides tray icon, and closes a window."""
    if window is None:
        return
    try:
        window._force_quit = True
        if hasattr(window, "playbooks_workspace") and hasattr(
            window.playbooks_workspace, "shutdown_workers"
        ):
            window.playbooks_workspace.shutdown_workers()
        if hasattr(window, "hotkey_manager") and window.hotkey_manager is not None:
            window.hotkey_manager.unregister()
        if hasattr(window, "tray_icon") and window.tray_icon is not None:
            window.tray_icon.hide()
        fx = window.property(BACKDROP_FX_PROPERTY)
        if fx is not None and hasattr(fx, "_timer"):
            fx._timer.stop()
        window.close()
        window.deleteLater()
    finally:
        app = QApplication.instance()
        if app is not None:
            app.processEvents()


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Session-wide QApplication configured identically to production."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(DARK_THEME_QSS)
    return app


@pytest.fixture(scope="session")
def guideit_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Pre-built temporary GuideIT SQLite FTS5 index shared across read-only shell tests."""
    db_file = tmp_path_factory.mktemp("guideit_db") / "guideit.db"
    build_index(get_bundle_dir(), db_path=db_file)
    return db_file


@pytest.fixture
def shell_window_factory(
    qapp: QApplication, tmp_path: Path, guideit_db_path: Path
) -> Callable[..., UnifiedShellWindow]:
    """Factory creating isolated UnifiedShellWindow instances with automatic teardown."""
    created: list[UnifiedShellWindow] = []
    counter = 0

    def _create(
        scripts_dir: Path | None = None,
        db_path: Path | None = None,
        playbooks_root_dir: Path | None = None,
        guideit_db: Path | None = None,
        initial_mode: int = MODE_SCRIPTS,
        startup_service: object | None = None,
        hotkey_manager: object | None = None,
        event_bus: AppEventBus | None = None,
    ) -> UnifiedShellWindow:
        nonlocal counter
        counter += 1
        effective_db = db_path if db_path is not None else (tmp_path / f"catalog_{counter}.db")
        repo = CatalogRepo(db_path=effective_db)
        scanner = (
            ScriptScanner(scripts_dir=scripts_dir, repo=repo)
            if scripts_dir is not None
            else ScriptScanner(repo=repo)
        )
        win = UnifiedShellWindow(
            repo=repo,
            scanner=scanner,
            startup_service=startup_service or DummyStartupService(),
            hotkey_manager=hotkey_manager,
            event_bus=event_bus,
            playbooks_root_dir=playbooks_root_dir,
            guideit_db_path=guideit_db if guideit_db is not None else guideit_db_path,
            initial_mode=initial_mode,
        )
        created.append(win)
        qapp.processEvents()
        return win

    yield _create

    for win in reversed(created):
        close_shell_window(win)
