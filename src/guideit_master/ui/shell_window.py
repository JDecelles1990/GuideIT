"""Unified desktop shell window hosting Playbooks, Scripts, and Split View."""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from guideit_master.core.event_bus import AppEventBus
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo
from guideit_master.psstore.services.clipboard_service import ClipboardService
from guideit_master.psstore.services.hotkey_service import (
    GlobalHotkeyManager,
    bring_window_to_foreground,
)
from guideit_master.psstore.services.report_service import ReportService
from guideit_master.psstore.services.runner import ScriptRunner
from guideit_master.psstore.services.scanner import ScriptScanner
from guideit_master.psstore.services.startup_service import StartupService
from guideit_master.psstore.ui.launcher_view import ScriptsWorkspaceWidget
from guideit_master.ui.backdrop_fx import install_backdrop_fx
from guideit_master.ui.effects import install_item_view_glow_recursive

logger = logging.getLogger(__name__)

MODE_PLAYBOOKS = 0
MODE_SCRIPTS = 1
MODE_SPLIT = 2


class PlaybooksPlaceholderWidget(QFrame):
    """Phase 1 placeholder inside the permanent splitter prior to Phase 2 GuideIT integration."""

    def __init__(
        self,
        on_open_scripts: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PlaybooksPlaceholderFrame")
        self._on_open_scripts = on_open_scripts
        self._compact_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addStretch(1)

        badge = QLabel("PHASE 2 MODULE PREVIEW")
        badge.setObjectName("SectionTitle")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(badge)

        title = QLabel("📘 GuideIT Troubleshooting Playbooks")
        title.setObjectName("HeaderTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.description_label = QLabel(
            "65 L1–L3 bilingual (EN/FR) MSP playbooks, domain taxonomy filters, FTS5 symptom search, "
            "and bidirectional PowerShell script deep links will mount into this workspace pane in Phase 2."
        )
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setStyleSheet("color: #cbd5e1; font-size: 13px;")
        layout.addWidget(self.description_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.switch_scripts_btn = QPushButton("⚡ Open Scripts Workstation (Alt+2)")
        self.switch_scripts_btn.setObjectName("PrimaryButton")
        self.switch_scripts_btn.setToolTip("Return to the PowerShellStore script workstation (Alt+2)")
        if self._on_open_scripts is not None:
            self.switch_scripts_btn.clicked.connect(self._on_open_scripts)
        btn_row.addWidget(self.switch_scripts_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        layout.addStretch(1)

    @property
    def is_compact_mode(self) -> bool:
        return self._compact_mode

    def set_compact_mode(self, compact: bool) -> None:
        self._compact_mode = bool(compact)

    def toggle_sidebar(self) -> None:
        """No-op sidebar toggle preserved for uniform shell delegation."""


class UnifiedShellWindow(QMainWindow):
    """Unified main window owning navigation modes, tray icon, opacity, startup, and Win+F8."""

    def __init__(
        self,
        repo: CatalogRepo | None = None,
        scanner: ScriptScanner | None = None,
        clipboard_service: ClipboardService | None = None,
        runner: ScriptRunner | None = None,
        report_service: ReportService | None = None,
        startup_service: StartupService | None = None,
        hotkey_manager: GlobalHotkeyManager | None = None,
        event_bus: AppEventBus | None = None,
        initial_mode: int = MODE_SCRIPTS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("GuideIT Master — Unified MSP Knowledge & Script Workstation")
        self.resize(1400, 860)

        self.app_icon = self._create_app_icon()
        self.setWindowIcon(self.app_icon)

        self.event_bus = event_bus if event_bus is not None else AppEventBus(self)
        self.startup_service = (
            startup_service if startup_service is not None else StartupService()
        )
        self.hotkey_manager = (
            hotkey_manager if hotkey_manager is not None else GlobalHotkeyManager(parent=self)
        )

        self._force_quit = False
        self._current_mode = MODE_SCRIPTS
        self._workspaces_kw = {
            "repo": repo,
            "scanner": scanner,
            "clipboard_service": clipboard_service,
            "runner": runner,
            "report_service": report_service,
        }

        self._init_ui()
        self._connect_signals()
        self._init_shortcuts()
        self._init_tray_icon()

        self.scripts_workspace.set_startup_checked(self.startup_service.is_startup_enabled())
        self.set_mode(initial_mode)

        install_item_view_glow_recursive(self)
        install_backdrop_fx(self)

    def _init_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("CentralBackdrop")
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(8, 8, 8, 6)
        central_layout.setSpacing(8)

        # Top unified shell navigation header
        self.shell_header = QFrame(central)
        self.shell_header.setObjectName("ShellHeaderFrame")
        self.shell_header.setFixedHeight(52)
        header_layout = QHBoxLayout(self.shell_header)
        header_layout.setContentsMargins(14, 6, 14, 6)
        header_layout.setSpacing(12)

        brand_label = QLabel("⚡ GuideIT Master")
        brand_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(brand_label)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.btn_mode_playbooks = QPushButton("📘 Playbooks")
        self.btn_mode_playbooks.setObjectName("ModeSwitchButton")
        self.btn_mode_playbooks.setCheckable(True)
        self.btn_mode_playbooks.setToolTip("Switch to GuideIT Playbooks workspace (Alt+1)")
        self.btn_mode_playbooks.clicked.connect(lambda: self.set_mode(MODE_PLAYBOOKS))
        self.mode_group.addButton(self.btn_mode_playbooks, MODE_PLAYBOOKS)
        header_layout.addWidget(self.btn_mode_playbooks)

        self.btn_mode_scripts = QPushButton("⚡ Scripts")
        self.btn_mode_scripts.setObjectName("ModeSwitchButton")
        self.btn_mode_scripts.setCheckable(True)
        self.btn_mode_scripts.setToolTip("Switch to PowerShellStore Scripts workstation (Alt+2)")
        self.btn_mode_scripts.clicked.connect(lambda: self.set_mode(MODE_SCRIPTS))
        self.mode_group.addButton(self.btn_mode_scripts, MODE_SCRIPTS)
        header_layout.addWidget(self.btn_mode_scripts)

        self.btn_mode_split = QPushButton("🔀 Split View")
        self.btn_mode_split.setObjectName("ModeSwitchButton")
        self.btn_mode_split.setCheckable(True)
        self.btn_mode_split.setToolTip(
            "Show Playbooks and PowerShell Scripts side by side without leaving context (Alt+3)"
        )
        self.btn_mode_split.clicked.connect(lambda: self.set_mode(MODE_SPLIT))
        self.mode_group.addButton(self.btn_mode_split, MODE_SPLIT)
        header_layout.addWidget(self.btn_mode_split)

        header_layout.addStretch(1)

        opacity_container = QWidget(self.shell_header)
        opacity_layout = QHBoxLayout(opacity_container)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(6)

        self.opacity_title = QLabel("Opacity:")
        self.opacity_title.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 500;")
        opacity_layout.addWidget(self.opacity_title)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(60, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(84)
        self.opacity_slider.setToolTip(
            "Adjust window opacity (60% - 100%) — Ctrl+= / Ctrl+- / Ctrl+0"
        )
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider)

        self.opacity_label = QLabel("100%")
        self.opacity_label.setFixedWidth(36)
        self.opacity_label.setStyleSheet(
            "color: #9ca3af; font-size: 11px; font-family: Consolas, monospace;"
        )
        opacity_layout.addWidget(self.opacity_label)

        header_layout.addWidget(opacity_container)
        central_layout.addWidget(self.shell_header)

        # Permanent top-level splitter hosting both workspaces (zero reparenting on mode switch)
        self.mode_splitter = QSplitter(Qt.Orientation.Horizontal, central)
        self.mode_splitter.setChildrenCollapsible(False)

        self.playbooks_workspace = PlaybooksPlaceholderWidget(
            on_open_scripts=lambda: self.set_mode(MODE_SCRIPTS),
            parent=self.mode_splitter,
        )
        self.scripts_workspace = ScriptsWorkspaceWidget(
            **self._workspaces_kw,
            event_bus=self.event_bus,
            parent=self.mode_splitter,
        )

        self.mode_splitter.addWidget(self.playbooks_workspace)
        self.mode_splitter.addWidget(self.scripts_workspace)
        central_layout.addWidget(self.mode_splitter, 1)

        self.setCentralWidget(central)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _connect_signals(self) -> None:
        self.scripts_workspace.status_message_requested.connect(self.status_bar.showMessage)
        self.scripts_workspace.startup_toggled.connect(self._on_sidebar_startup_toggled)
        self.event_bus.status_toast_requested.connect(self.status_bar.showMessage)
        self.event_bus.open_script_requested.connect(self._on_open_script_requested)
        self.event_bus.copy_script_requested.connect(self._on_copy_script_requested)
        self.event_bus.run_script_requested.connect(self._on_run_script_requested)
        self.event_bus.open_playbook_requested.connect(self._on_open_playbook_requested)
        self.hotkey_manager.triggered.connect(self.toggle_window_visibility)

    def _register_shortcut(
        self,
        name: str,
        keys: str | list[str],
        callback: Callable[[], None],
    ) -> QShortcut:
        """Registers a window-scoped keyboard shortcut and tracks it in self.shortcuts."""
        key_list = [keys] if isinstance(keys, str) else keys
        shortcut = QShortcut(self)
        shortcut.setKeys([QKeySequence(k) for k in key_list])
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(callback)
        self.shortcuts[name] = shortcut
        return shortcut

    def _init_shortcuts(self) -> None:
        self.shortcuts: dict[str, QShortcut] = {}

        # Shell view mode switcher shortcuts
        self._register_shortcut("mode_playbooks", "Alt+1", lambda: self.set_mode(MODE_PLAYBOOKS))
        self._register_shortcut("mode_scripts", "Alt+2", lambda: self.set_mode(MODE_SCRIPTS))
        self._register_shortcut("mode_split", "Alt+3", lambda: self.set_mode(MODE_SPLIT))

        # Navigation & catalog shortcuts
        self.shortcut_sidebar = self._register_shortcut(
            "toggle_sidebar", "Ctrl+B", self._toggle_active_sidebar
        )
        self._register_shortcut(
            "open_scripts_folder", "Ctrl+O", self.scripts_workspace.open_scripts_folder
        )
        self._register_shortcut("focus_search", "Ctrl+F", self._focus_search_input)
        self._register_shortcut(
            "sync_catalog", "F5", self.scripts_workspace.sync_and_refresh
        )
        self._register_shortcut("escape_action", "Esc", self.scripts_workspace._handle_escape)
        self._register_shortcut(
            "check_all_visible",
            "Ctrl+Shift+A",
            self.scripts_workspace._shortcut_check_all_visible,
        )
        self._register_shortcut(
            "check_read_only_visible",
            "Ctrl+Shift+O",
            self.scripts_workspace._shortcut_check_read_only_visible,
        )
        self._register_shortcut(
            "clear_checked_scripts",
            "Ctrl+Shift+D",
            self.scripts_workspace._shortcut_clear_checked,
        )

        # Core technician script actions & parameters
        self._register_shortcut(
            "copy_raw_script", "Ctrl+Shift+C", self.scripts_workspace._on_copy_raw_clicked
        )
        self._register_shortcut(
            "copy_rmm_script", "Ctrl+Shift+R", self.scripts_workspace._on_copy_rmm_clicked
        )
        self._register_shortcut(
            "run_local",
            ["Ctrl+Return", "Ctrl+Enter"],
            self.scripts_workspace._shortcut_run_local,
        )
        self._register_shortcut(
            "stop_execution", "Shift+F5", self.scripts_workspace._shortcut_stop_execution
        )
        self._register_shortcut(
            "reset_parameters",
            "Ctrl+Alt+R",
            self.scripts_workspace._shortcut_reset_parameters,
        )

        # Workstation tab switching & reporting shortcuts
        self._register_shortcut(
            "tab_results", "Ctrl+1", lambda: self.scripts_workspace._switch_console_tab(0)
        )
        self._register_shortcut(
            "tab_raw_console", "Ctrl+2", lambda: self.scripts_workspace._switch_console_tab(1)
        )
        self._register_shortcut(
            "tab_script_source", "Ctrl+3", lambda: self.scripts_workspace._switch_console_tab(2)
        )
        self._register_shortcut(
            "tab_run_history", "Ctrl+4", lambda: self.scripts_workspace._switch_console_tab(3)
        )
        self._register_shortcut(
            "copy_ticket_report",
            "Ctrl+Shift+T",
            self.scripts_workspace._shortcut_copy_report,
        )
        self._register_shortcut(
            "save_html_report", "Ctrl+S", self.scripts_workspace._shortcut_save_report
        )
        self._register_shortcut(
            "clear_console", "Ctrl+L", self.scripts_workspace._shortcut_clear_console
        )

        # Window opacity & application lifecycle shortcuts
        self._register_shortcut(
            "opacity_increase", ["Ctrl+=", "Ctrl++"], lambda: self._adjust_opacity(5)
        )
        self._register_shortcut("opacity_decrease", "Ctrl+-", lambda: self._adjust_opacity(-5))
        self._register_shortcut("opacity_reset", "Ctrl+0", self._reset_opacity)
        self._register_shortcut("quit_app", "Ctrl+Q", self.quit_application)

        try:
            self.hotkey_manager.register(int(self.winId()))
        except Exception as exc:
            logger.warning("Could not register global Win+F8 hotkey: %s", exc)

    @property
    def current_mode(self) -> int:
        return self._current_mode

    def set_mode(self, mode: int) -> None:
        """Switches between Playbooks (0), Scripts (1), and Split View (2) without reparenting."""
        if mode not in (MODE_PLAYBOOKS, MODE_SCRIPTS, MODE_SPLIT):
            mode = MODE_SCRIPTS
        self._current_mode = mode

        if mode == MODE_PLAYBOOKS:
            self.btn_mode_playbooks.setChecked(True)
            self.playbooks_workspace.setVisible(True)
            self.scripts_workspace.setVisible(False)
            self.playbooks_workspace.set_compact_mode(False)
            self.scripts_workspace.set_compact_mode(False)
            self.mode_splitter.setSizes([1, 0])
            self.status_bar.showMessage("View mode: Playbooks", 2000)
        elif mode == MODE_SCRIPTS:
            self.btn_mode_scripts.setChecked(True)
            self.playbooks_workspace.setVisible(False)
            self.scripts_workspace.setVisible(True)
            self.playbooks_workspace.set_compact_mode(False)
            self.scripts_workspace.set_compact_mode(False)
            self.mode_splitter.setSizes([0, 1])
            self.status_bar.showMessage("View mode: PowerShell Scripts", 2000)
        else:
            self.btn_mode_split.setChecked(True)
            self.playbooks_workspace.setVisible(True)
            self.scripts_workspace.setVisible(True)
            self.playbooks_workspace.set_compact_mode(True)
            self.scripts_workspace.set_compact_mode(True)
            half = max(480, self.width() // 2)
            self.mode_splitter.setSizes([half, half])
            self.status_bar.showMessage("View mode: Split View (Playbook + Script Runner)", 2500)

    def _toggle_active_sidebar(self) -> None:
        if self._current_mode == MODE_PLAYBOOKS:
            self.playbooks_workspace.toggle_sidebar()
        else:
            if self._current_mode == MODE_SPLIT:
                self.set_mode(MODE_SCRIPTS)
            self.scripts_workspace.toggle_sidebar()

    def _focus_search_input(self) -> None:
        if self._current_mode != MODE_SCRIPTS:
            self.set_mode(MODE_SCRIPTS)
        self.scripts_workspace._focus_search_input()

    # ------------------------------------------------------------------
    # EventBus Cross-Module Orchestration
    # ------------------------------------------------------------------

    def _on_open_script_requested(
        self, relative_path: str, params: dict[str, Any], split_view: bool
    ) -> None:
        found = self.scripts_workspace.select_and_preload_script(relative_path, params or None)
        if found:
            self.set_mode(MODE_SPLIT if split_view else MODE_SCRIPTS)

    def _on_copy_script_requested(
        self, relative_path: str, params: dict[str, Any], inject_params: bool
    ) -> None:
        script = self.scripts_workspace.repo.get_script_by_path(relative_path)
        if script is None:
            self.status_bar.showMessage(f"Linked script not found: {relative_path}", 4000)
            return
        if inject_params:
            merged = {
                p["name"]: p.get("default")
                for p in (script.params or [])
                if p.get("name")
            }
            merged.update(params or {})
            self.scripts_workspace.clipboard_service.copy_rmm_ready_script(
                script.relative_path, merged
            )
            self.status_bar.showMessage(f"⚡ Copied RMM-ready '{script.title}' to clipboard", 4000)
        else:
            self.scripts_workspace.clipboard_service.copy_raw_script(script.relative_path)
            self.status_bar.showMessage(f"📋 Copied raw '{script.title}' to clipboard", 4000)

    def _on_run_script_requested(self, relative_path: str, params: dict[str, Any]) -> None:
        found = self.scripts_workspace.select_and_preload_script(relative_path, params or None)
        if found:
            self.set_mode(MODE_SPLIT)
            self.scripts_workspace._on_run_local_clicked()

    def _on_open_playbook_requested(self, playbook_id: str, split_view: bool) -> None:
        self.set_mode(MODE_SPLIT if split_view else MODE_PLAYBOOKS)
        self.status_bar.showMessage(f"Requested playbook: {playbook_id}", 3000)

    # ------------------------------------------------------------------
    # Window Opacity, Tray Icon, Global Hotkey & Lifecycle
    # ------------------------------------------------------------------

    def _on_opacity_changed(self, value: int) -> None:
        clamped = max(60, min(100, value))
        self.opacity_label.setText(f"{clamped}%")
        self.setWindowOpacity(clamped / 100.0)

    def _adjust_opacity(self, delta: int) -> None:
        new_val = max(
            self.opacity_slider.minimum(),
            min(self.opacity_slider.maximum(), self.opacity_slider.value() + delta),
        )
        self.opacity_slider.setValue(new_val)
        self.status_bar.showMessage(f"Window opacity: {new_val}%", 2000)

    def _reset_opacity(self) -> None:
        self.opacity_slider.setValue(100)
        self.status_bar.showMessage("Window opacity reset to 100%", 2000)

    def _create_app_icon(self) -> QIcon:
        """Draws a crisp dark-blue badge with a terminal prompt symbol (>_) for window and tray."""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#2563eb"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Consolas", 22, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, ">_")
        painter.end()
        return QIcon(pixmap)

    def _init_tray_icon(self) -> None:
        """Initializes the Windows notification area (System Tray) icon and context menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.info("System tray is not available on this platform.")
            return

        self.tray_icon = QSystemTrayIcon(self.app_icon, self)
        self.tray_icon.setToolTip("GuideIT Master — Press Win+F8 to Open or Minimize")

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1f2937; color: #f3f4f6; border: 1px solid #374151; padding: 4px; } "
            "QMenu::item { padding: 6px 20px; } "
            "QMenu::item:selected { background-color: #2563eb; border-radius: 4px; } "
            "QMenu::separator { height: 1px; background-color: #374151; margin: 4px 0px; }"
        )

        self.action_tray_toggle = QAction("Show / Minimize GuideIT Master (Win+F8)", self)
        font = self.action_tray_toggle.font()
        font.setBold(True)
        self.action_tray_toggle.setFont(font)
        self.action_tray_toggle.triggered.connect(self.toggle_window_visibility)
        menu.addAction(self.action_tray_toggle)

        self.action_tray_startup = QAction("Start at Windows Startup", self)
        self.action_tray_startup.setCheckable(True)
        self.action_tray_startup.setChecked(self.startup_service.is_startup_enabled())
        self.action_tray_startup.toggled.connect(self._on_tray_startup_toggled)
        menu.addAction(self.action_tray_startup)

        menu.addSeparator()

        action_quit = QAction("Exit GuideIT Master (Ctrl+Q)", self)
        action_quit.triggered.connect(self.quit_application)
        menu.addAction(action_quit)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_window_visibility()

    def _on_sidebar_startup_toggled(self, enabled: bool) -> None:
        success = self.startup_service.toggle_startup(enabled)
        actual = self.startup_service.is_startup_enabled()
        self.scripts_workspace.set_startup_checked(actual)
        if hasattr(self, "action_tray_startup"):
            self.action_tray_startup.blockSignals(True)
            self.action_tray_startup.setChecked(actual)
            self.action_tray_startup.blockSignals(False)
        state_str = "enabled" if enabled else "disabled"
        status_msg = (
            f"Windows startup {state_str}."
            if success
            else "Failed to update Windows startup registry."
        )
        self.status_bar.showMessage(status_msg, 3000)

    def _on_tray_startup_toggled(self, enabled: bool) -> None:
        success = self.startup_service.toggle_startup(enabled)
        actual = self.startup_service.is_startup_enabled()
        self.scripts_workspace.set_startup_checked(actual)
        if hasattr(self, "action_tray_startup"):
            self.action_tray_startup.blockSignals(True)
            self.action_tray_startup.setChecked(actual)
            self.action_tray_startup.blockSignals(False)
        state_str = "enabled" if enabled else "disabled"
        status_msg = (
            f"Windows startup {state_str}."
            if success
            else "Failed to update Windows startup registry."
        )
        self.status_bar.showMessage(status_msg, 3000)

    def toggle_window_visibility(self) -> None:
        """Toggles the window between active foreground on screen and minimized."""
        if self.isHidden() or self.isMinimized() or not self.isActiveWindow():
            self.setWindowState(
                (self.windowState() & ~Qt.WindowState.WindowMinimized)
                | Qt.WindowState.WindowActive
            )
            self.show()
            self.raise_()
            self.activateWindow()
            bring_window_to_foreground(int(self.winId()))
        else:
            self.showMinimized()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Intercepts close: minimizes to system tray unless force quit was invoked."""
        if (
            self._force_quit
            or not hasattr(self, "tray_icon")
            or not self.tray_icon.isVisible()
        ):
            self.hotkey_manager.unregister()
            event.accept()
        else:
            event.ignore()
            self.hide()
            try:
                if self.tray_icon.supportsMessages():
                    self.tray_icon.showMessage(
                        "GuideIT Master",
                        "Application minimized to system tray. Press Win+F8 anytime to open.",
                        QSystemTrayIcon.MessageIcon.Information,
                        2000,
                    )
            except Exception:
                pass

    def quit_application(self) -> None:
        """Completely terminates the application and unregisters global hotkeys."""
        self._force_quit = True
        self.hotkey_manager.unregister()
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        self.close()
        app = QApplication.instance()
        if app:
            app.quit()
