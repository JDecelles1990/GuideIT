"""Application entrypoint for GuideIT Master."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from guideit_master.paths import get_logs_dir
from guideit_master.ui.effects import install_button_fx
from guideit_master.ui.shell_window import UnifiedShellWindow
from guideit_master.ui.tooltip_fx import install_tooltip_fx
from guideit_master.ui.unified_theme import DARK_THEME_QSS


def configure_logging() -> None:
    """Configures console and rotating file logging under the writable logs directory."""
    logs_dir: Path = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "guideit_master.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    args = parse_args(argv)
    start_hidden = bool(args.startup or args.minimized or args.tray)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GuideIT Master")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(DARK_THEME_QSS)

    install_button_fx(app)
    install_tooltip_fx(app)

    window = UnifiedShellWindow()
    if start_hidden:
        if hasattr(window, "tray_icon") and window.tray_icon.isVisible():
            window.hide()
        else:
            window.showMinimized()
    else:
        window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
