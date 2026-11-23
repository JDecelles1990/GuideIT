"""Application entrypoint for GuideIT Master."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from guideit_master.guideit.search import get_domain_and_subcategory_counts
from guideit_master.paths import (
    get_bundle_dir,
    get_logs_dir,
    get_user_custom_scripts_dir,
    get_user_data_dir,
    is_frozen,
)
from guideit_master.ui.backdrop_fx import BACKDROP_FX_PROPERTY
from guideit_master.ui.effects import install_button_fx
from guideit_master.ui.shell_window import MODE_SPLIT, UnifiedShellWindow
from guideit_master.ui.tooltip_fx import install_tooltip_fx
from guideit_master.ui.unified_theme import DARK_THEME_QSS


def configure_logging() -> logging.FileHandler:
    """Configures console (when available) and file logging under the writable logs directory."""
    logs_dir: Path = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "guideit_master.log"

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    if root_logger.level == logging.NOTSET:
        root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    if sys.stdout is not None and not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root_logger.handlers
    ):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    return file_handler


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GuideIT Master — Unified MSP Workstation")
    parser.add_argument(
        "--startup",
        action="store_true",
        help="Launched automatically on Windows startup (starts minimized to tray).",
    )
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start the window minimized/hidden in the system tray.",
    )
    parser.add_argument(
        "--tray",
        action="store_true",
        help="Alias for --minimized.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run automated startup/bundle/DB verification, write smoke_test_result.json, and exit.",
    )
    return parser.parse_args(argv)


def _close_window_cleanly(window: UnifiedShellWindow, app: QApplication) -> None:
    """Shut down background workers, hotkeys, FX timers, and tray icon cleanly."""
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
    app.processEvents()


def run_smoke_test(app: QApplication) -> int:
    """Verify bundled assets, writable DB isolation, search, and Split View without GUI blocking."""
    bundle_dir = get_bundle_dir()
    data_dir = get_user_data_dir()
    errors: list[str] = []

    required_bundle_dirs = (
        "playbooks",
        "powershell_scripts",
        "taxonomy",
        "templates",
        "docs",
    )
    for rel_dir in required_bundle_dirs:
        if not (bundle_dir / rel_dir).is_dir():
            errors.append(f"Missing bundled asset directory: {bundle_dir / rel_dir}")

    playbook_count = 0
    script_count = 0
    user_script_count = 0
    unified_search_ok = False
    split_view_ok = False

    window: UnifiedShellWindow | None = None
    try:
        window = UnifiedShellWindow()
        app.processEvents()

        guideit_db = window.playbooks_workspace.db_path.resolve()
        ps_db = Path(window.scripts_workspace.repo.db_path).resolve()
        user_scripts_dir = get_user_custom_scripts_dir().resolve()
        log_file = (get_logs_dir() / "guideit_master.log").resolve()

        if not guideit_db.is_file() or not guideit_db.is_relative_to(data_dir):
            errors.append(f"GuideIT DB missing or outside user data dir: {guideit_db}")
        if not ps_db.is_file() or not ps_db.is_relative_to(data_dir):
            errors.append(f"PowerShellStore DB missing or outside user data dir: {ps_db}")
        if not user_scripts_dir.is_dir() or not user_scripts_dir.is_relative_to(data_dir):
            errors.append(f"user_scripts dir missing or outside user data dir: {user_scripts_dir}")
        if not log_file.is_file() or not log_file.is_relative_to(data_dir):
            errors.append(f"Log file missing or outside user data dir: {log_file}")

        domain_counts, _, _ = get_domain_and_subcategory_counts(guideit_db)
        playbook_count = sum(domain_counts.values())
        if playbook_count < 65:
            errors.append(f"Expected >= 65 indexed playbooks, found {playbook_count}")

        all_scripts = window.scripts_workspace.repo.get_all_scripts()
        script_count = len(all_scripts)
        user_script_count = sum(1 for s in all_scripts if s.source == "user")
        if script_count < 38:
            errors.append(f"Expected >= 38 indexed scripts, found {script_count}")

        search_resp = window.run_unified_search("0x0000011b")
        app.processEvents()
        unified_search_ok = any(
            h.id == "prt-001" for h in search_resp.playbook_hits
        ) and any(
            s.relative_path == "04_Devices/Reset-PrintSpooler.ps1"
            for s in search_resp.script_hits
        )
        window.omnibox_popup.hide()
        if not unified_search_ok:
            errors.append("Unified search for '0x0000011b' did not return expected playbook and script.")

        window.set_mode(MODE_SPLIT)
        app.processEvents()
        split_view_ok = (
            window.current_mode == MODE_SPLIT
            and window.playbooks_workspace.is_compact_mode
            and window.scripts_workspace.is_compact_mode
            and window.playbooks_workspace.parentWidget() is window.mode_splitter
            and window.scripts_workspace.parentWidget() is window.mode_splitter
        )
        if not split_view_ok:
            errors.append("Split View verification failed.")
    except Exception as exc:
        logging.getLogger(__name__).exception("Smoke test failed")
        errors.append(f"Exception during smoke test: {exc}")
    finally:
        if window is not None:
            _close_window_cleanly(window, app)

    result_payload = {
        "ok": len(errors) == 0,
        "frozen": is_frozen(),
        "bundle_dir": str(bundle_dir),
        "user_data_dir": str(data_dir),
        "playbook_count": playbook_count,
        "script_count": script_count,
        "user_script_count": user_script_count,
        "unified_search_ok": unified_search_ok,
        "split_view_ok": split_view_ok,
        "errors": errors,
    }
    result_path = data_dir / "smoke_test_result.json"
    result_path.write_text(
        json.dumps(result_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    if sys.stdout is not None:
        try:
            print(json.dumps(result_payload, ensure_ascii=False))
        except Exception:
            pass
    return 0 if result_payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    file_handler = configure_logging()
    try:
        args = parse_args(argv)
        start_hidden = bool(args.startup or args.minimized or args.tray)

        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("GuideIT Master")
        app.setQuitOnLastWindowClosed(False)
        app.setFont(QFont("Segoe UI", 10))
        app.setStyleSheet(DARK_THEME_QSS)

        install_button_fx(app)
        install_tooltip_fx(app)

        if args.smoke_test:
            return run_smoke_test(app)

        window = UnifiedShellWindow()
        if start_hidden:
            if hasattr(window, "tray_icon") and window.tray_icon.isVisible():
                window.hide()
            else:
                window.showMinimized()
        else:
            window.showMaximized()

        return app.exec()
    finally:
        logging.getLogger().removeHandler(file_handler)
        file_handler.close()


if __name__ == "__main__":
    raise SystemExit(main())
