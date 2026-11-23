"""Unified desktop shell window hosting Playbooks, Scripts, and Split View."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
from guideit_master.guideit.models import ValidationReport
from guideit_master.guideit.ui.main_window import PlaybooksWorkspaceWidget
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
from guideit_master.services.cross_link_service import CrossLinkService, coerce_param_overrides
from guideit_master.services.unified_search import UnifiedSearchResponse, search_all
from guideit_master.services.user_state_service import UserStateService
from guideit_master.ui.backdrop_fx import install_backdrop_fx
from guideit_master.ui.effects import install_item_view_glow_recursive

logger = logging.getLogger(__name__)

MODE_PLAYBOOKS = 0
MODE_SCRIPTS = 1
MODE_SPLIT = 2


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
        user_state_service: UserStateService | None = None,
        playbooks_root_dir: Path | None = None,
        guideit_db_path: Path | None = None,
        initial_mode: int = MODE_SCRIPTS,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("GuideIT Master — Unified MSP Knowledge & Script Workstation")
        self.resize(1400, 860)

        self.app_icon = self._create_app_icon()
        self.setWindowIcon(self.app_icon)

        self.event_bus = event_bus if event_bus is not None else AppEventBus(self)
        self.user_state_service = (
            user_state_service if user_state_service is not None else UserStateService()
        )
        self.startup_service = (
            startup_service if startup_service is not None else StartupService()
        )
        self.hotkey_manager = (
            hotkey_manager if hotkey_manager is not None else GlobalHotkeyManager(parent=self)
        )

        self._force_quit = False
        self._current_mode = MODE_SCRIPTS
        self._last_unified_response: UnifiedSearchResponse | None = None
        self._last_unified_query: str = ""
        self._playbooks_kw = {
            "root_dir": playbooks_root_dir,
            "db_path": guideit_db_path,
        }
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
        if self.playbooks_workspace.last_report is not None:
            self._update_health_pill(self.playbooks_workspace.last_report)
        if self.playbooks_workspace.index_status_text:
            self.index_status_label.setText(self.playbooks_workspace.index_status_text)

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

        brand_label = QLabel("⚡ GuideIT Master", self.shell_header)
        brand_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #f8fafc;")
        header_layout.addWidget(brand_label)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.btn_mode_playbooks = QPushButton("📘 Playbooks", self.shell_header)
        self.btn_mode_playbooks.setObjectName("ModeSwitchButton")
        self.btn_mode_playbooks.setCheckable(True)
        self.btn_mode_playbooks.setToolTip("Switch to GuideIT Playbooks workspace (Alt+1)")
        self.btn_mode_playbooks.clicked.connect(lambda: self.set_mode(MODE_PLAYBOOKS))
        self.mode_group.addButton(self.btn_mode_playbooks, MODE_PLAYBOOKS)
        header_layout.addWidget(self.btn_mode_playbooks)

        self.btn_mode_scripts = QPushButton("⚡ Scripts", self.shell_header)
        self.btn_mode_scripts.setObjectName("ModeSwitchButton")
        self.btn_mode_scripts.setCheckable(True)
        self.btn_mode_scripts.setToolTip("Switch to PowerShellStore Scripts workstation (Alt+2)")
        self.btn_mode_scripts.clicked.connect(lambda: self.set_mode(MODE_SCRIPTS))
        self.mode_group.addButton(self.btn_mode_scripts, MODE_SCRIPTS)
        header_layout.addWidget(self.btn_mode_scripts)

        self.btn_mode_split = QPushButton("🔀 Split View", self.shell_header)
        self.btn_mode_split.setObjectName("ModeSwitchButton")
        self.btn_mode_split.setCheckable(True)
        self.btn_mode_split.setToolTip(
            "Show Playbooks and PowerShell Scripts side by side without leaving context (Alt+3)"
        )
        self.btn_mode_split.clicked.connect(lambda: self.set_mode(MODE_SPLIT))
        self.mode_group.addButton(self.btn_mode_split, MODE_SPLIT)
        header_layout.addWidget(self.btn_mode_split)

        self.omnibox_input = QLineEdit(self.shell_header)
        self.omnibox_input.setObjectName("omniboxInput")
        self.omnibox_input.setClearButtonEnabled(True)
        self.omnibox_input.setMinimumWidth(200)
        self.omnibox_input.setPlaceholderText(
            "🔍 Unified search (playbooks & scripts, EN/FR, 4740)...  [Ctrl+Shift+K]"
        )
        self.omnibox_input.setToolTip(
            "Unified EN/FR search across GuideIT playbooks and PowerShellStore scripts (Ctrl+Shift+K)"
        )
        header_layout.addWidget(self.omnibox_input, 1)

        self.btn_useful_tools = QPushButton("🌐 Useful Tools", self.shell_header)
        self.btn_useful_tools.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_useful_tools.setToolTip(
            "Open curated MSP & Data Center websites and external tools (Ctrl+T)"
        )
        header_layout.addWidget(self.btn_useful_tools)

        self.health_pill_btn = QPushButton("Checking...", self.shell_header)
        self.health_pill_btn.setObjectName("healthPill")
        self.health_pill_btn.setProperty("status", "unknown")
        self.health_pill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.health_pill_btn.setToolTip(
            "Click to inspect GuideIT playbook validation & multi-tenant PII report"
        )
        header_layout.addWidget(self.health_pill_btn)

        opacity_container = QWidget(self.shell_header)
        opacity_layout = QHBoxLayout(opacity_container)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.setSpacing(6)

        self.opacity_title = QLabel("Opacity:", opacity_container)
        self.opacity_title.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 500;")
        opacity_layout.addWidget(self.opacity_title)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal, opacity_container)
        self.opacity_slider.setRange(60, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(84)
        self.opacity_slider.setToolTip(
            "Adjust window opacity (60% - 100%) — Ctrl+= / Ctrl+- / Ctrl+0"
        )
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_layout.addWidget(self.opacity_slider)

        self.opacity_label = QLabel("100%", opacity_container)
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

        self.playbooks_workspace = PlaybooksWorkspaceWidget(
            **self._playbooks_kw,
            event_bus=self.event_bus,
            user_state_service=self.user_state_service,
            embedded_in_shell=True,
            parent=self.mode_splitter,
        )
        self.scripts_workspace = ScriptsWorkspaceWidget(
            **self._workspaces_kw,
            event_bus=self.event_bus,
            user_state_service=self.user_state_service,
            parent=self.mode_splitter,
        )

        self.mode_splitter.addWidget(self.playbooks_workspace)
        self.mode_splitter.addWidget(self.scripts_workspace)
        central_layout.addWidget(self.mode_splitter, 1)

        self.cross_link_service = CrossLinkService(
            guideit_db_path=self.playbooks_workspace.db_path,
            catalog_repo=self.scripts_workspace.repo,
        )
        self.playbooks_workspace.set_cross_link_service(self.cross_link_service)
        self.scripts_workspace.set_cross_link_service(self.cross_link_service)

        self.setCentralWidget(central)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.index_status_label = QLabel("", self)
        self.index_status_label.setStyleSheet(
            "color: #93A4B8; padding-right: 8px; font-size: 12px;"
        )
        self.status_bar.addPermanentWidget(self.index_status_label)
        self.status_bar.showMessage("Ready")

        # Unified Omnibox floating results overlay
        self.omnibox_popup = QFrame(self)
        self.omnibox_popup.setObjectName("OmniboxPopup")
        self.omnibox_popup.setVisible(False)
        popup_layout = QVBoxLayout(self.omnibox_popup)
        popup_layout.setContentsMargins(10, 8, 10, 8)
        popup_layout.setSpacing(6)

        popup_head = QHBoxLayout()
        popup_head.setContentsMargins(2, 0, 2, 0)
        self.omnibox_status_label = QLabel("Unified Search", self.omnibox_popup)
        self.omnibox_status_label.setStyleSheet(
            "color: #93A4B8; font-size: 11px; font-weight: 600; background: transparent;"
        )
        popup_head.addWidget(self.omnibox_status_label, 1)

        self.omnibox_close_btn = QPushButton("✕", self.omnibox_popup)
        self.omnibox_close_btn.setFixedSize(22, 22)
        self.omnibox_close_btn.setToolTip("Close unified search results (Esc)")
        self.omnibox_close_btn.setStyleSheet("padding: 0px; font-size: 11px;")
        self.omnibox_close_btn.clicked.connect(self.omnibox_popup.hide)
        popup_head.addWidget(self.omnibox_close_btn)
        popup_layout.addLayout(popup_head)

        self.omnibox_results_list = QListWidget(self.omnibox_popup)
        self.omnibox_results_list.setObjectName("OmniboxResultsList")
        self.omnibox_results_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        popup_layout.addWidget(self.omnibox_results_list, 1)

        self._omnibox_timer = QTimer(self)
        self._omnibox_timer.setSingleShot(True)
        self._omnibox_timer.setInterval(150)
        self._omnibox_timer.timeout.connect(self.run_unified_search)

    def _connect_signals(self) -> None:
        self.playbooks_workspace.status_message_requested.connect(self.status_bar.showMessage)
        self.playbooks_workspace.validation_report_updated.connect(self._update_health_pill)
        self.playbooks_workspace.index_status_updated.connect(self.index_status_label.setText)
        self.btn_useful_tools.clicked.connect(self.playbooks_workspace.open_resources_dialog)
        self.health_pill_btn.clicked.connect(self.playbooks_workspace.show_validation_dialog)

        self.scripts_workspace.status_message_requested.connect(self.status_bar.showMessage)
        self.scripts_workspace.startup_toggled.connect(self._on_sidebar_startup_toggled)
        self.event_bus.status_toast_requested.connect(self.status_bar.showMessage)
        self.event_bus.open_script_requested.connect(self._on_open_script_requested)
        self.event_bus.copy_script_requested.connect(self._on_copy_script_requested)
        self.event_bus.copy_scripts_bundle_requested.connect(
            self._on_copy_scripts_bundle_requested
        )
        self.event_bus.select_scripts_batch_requested.connect(
            self._on_select_scripts_batch_requested
        )
        self.event_bus.run_script_requested.connect(self._on_run_script_requested)
        self.event_bus.open_playbook_requested.connect(self._on_open_playbook_requested)
        self.event_bus.catalog_synced.connect(self._on_catalog_synced)
        self.event_bus.playbooks_reindexed.connect(self._on_playbooks_reindexed)
        self.omnibox_input.textChanged.connect(self._on_omnibox_text_changed)
        self.omnibox_input.returnPressed.connect(self._on_omnibox_return_pressed)
        self.omnibox_results_list.itemClicked.connect(self._on_omnibox_item_activated)
        self.omnibox_results_list.itemActivated.connect(self._on_omnibox_item_activated)
        self.hotkey_manager.triggered.connect(self.toggle_window_visibility)

    def _update_health_pill(self, report: ValidationReport) -> None:
        err_cnt = len(report.errors)
        warn_cnt = len(report.warnings)
        broken_links = sum(1 for err in report.errors if err.code == "BROKEN_LINKED_SCRIPT")
        if err_cnt > 0:
            status = "err"
            text = f"✕ {err_cnt} Error(s)"
        elif warn_cnt > 0:
            status = "warn"
            text = f"⚠ {warn_cnt} Warning(s)"
        else:
            status = "ok"
            text = f"✓ {report.checked_files} Valid"

        self.health_pill_btn.setText(text)
        self.health_pill_btn.setProperty("status", status)
        self.health_pill_btn.style().unpolish(self.health_pill_btn)
        self.health_pill_btn.style().polish(self.health_pill_btn)
        if broken_links > 0:
            self.health_pill_btn.setToolTip(
                f"{err_cnt} validation error(s), including {broken_links} broken linked_scripts "
                "reference(s). Click to inspect report."
            )
        elif err_cnt > 0:
            self.health_pill_btn.setToolTip(
                f"{err_cnt} validation error(s). Click to inspect GuideIT validation report."
            )
        elif warn_cnt > 0:
            self.health_pill_btn.setToolTip(
                f"{warn_cnt} validation warning(s). Click to inspect GuideIT validation report."
            )
        else:
            self.health_pill_btn.setToolTip(
                "All playbooks, linked_scripts, and multi-tenant PII rules passed. Click to inspect."
            )

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
            "focus_playbook_search", "Ctrl+K", self._focus_playbook_search
        )
        self._register_shortcut(
            "focus_unified_search", "Ctrl+Shift+K", self._focus_unified_search
        )
        self._register_shortcut(
            "useful_tools", "Ctrl+T", self.playbooks_workspace.open_resources_dialog
        )
        self._register_shortcut(
            "reset_playbook_filters", "Ctrl+R", self.playbooks_workspace.reset_all
        )
        self._register_shortcut(
            "playbook_back", "Alt+Left", self.playbooks_workspace.navigate_back
        )
        self._register_shortcut(
            "copy_linked_readonly_bundle",
            "Ctrl+Shift+B",
            self._shortcut_copy_linked_readonly_bundle,
        )
        self._register_shortcut(
            "toggle_pin_favorite",
            "Ctrl+D",
            self._shortcut_toggle_pin_favorite,
        )
        self._register_shortcut("sync_catalog", "F5", self._sync_all_libraries)
        self._register_shortcut("escape_action", "Esc", self._handle_escape)
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

    def _focus_playbook_search(self) -> None:
        if self._current_mode != MODE_PLAYBOOKS:
            self.set_mode(MODE_PLAYBOOKS)
        self.playbooks_workspace.focus_search()

    def _focus_unified_search(self) -> None:
        self.omnibox_input.setFocus()
        self.omnibox_input.selectAll()
        if self.omnibox_input.text().strip():
            self.run_unified_search()

    def _on_omnibox_text_changed(self, text: str) -> None:
        if not text.strip():
            self._omnibox_timer.stop()
            self.omnibox_popup.hide()
            return
        self._omnibox_timer.start()

    def _on_omnibox_return_pressed(self) -> None:
        self._omnibox_timer.stop()
        text = self.omnibox_input.text().strip()
        if not text:
            self.omnibox_popup.hide()
            return
        if self.omnibox_popup.isVisible() and self._last_unified_query == text:
            current = self.omnibox_results_list.currentItem()
            if current is not None and current.data(Qt.ItemDataRole.UserRole) is not None:
                self._on_omnibox_item_activated(current)
                return
        self.run_unified_search(text)

    def _position_omnibox_popup(self) -> None:
        anchor = self.omnibox_input.mapTo(self, QPoint(0, self.omnibox_input.height() + 4))
        popup_w = max(480, min(self.width() - 24, max(self.omnibox_input.width() + 140, 620)))
        popup_h = min(400, max(160, self.height() - anchor.y() - 36))
        x = max(12, min(anchor.x(), self.width() - popup_w - 12))
        y = max(self.shell_header.geometry().bottom() + 4, anchor.y())
        self.omnibox_popup.setGeometry(x, y, popup_w, popup_h)

    def run_unified_search(self, query: str | None = None) -> UnifiedSearchResponse:
        """Execute unified bilingual FTS5 search across playbooks and PowerShell scripts."""
        if query is not None:
            text = query.strip()
            if self.omnibox_input.text().strip() != text:
                self.omnibox_input.blockSignals(True)
                self.omnibox_input.setText(text)
                self.omnibox_input.blockSignals(False)
        else:
            text = self.omnibox_input.text().strip()

        if not text:
            self.omnibox_popup.hide()
            empty = UnifiedSearchResponse(
                query="",
                expanded_tags=[],
                suggested_domains=[],
                total_playbook_hits=0,
                total_script_hits=0,
                playbook_hits=[],
                script_hits=[],
            )
            self._last_unified_response = empty
            self._last_unified_query = ""
            return empty

        response = search_all(
            text,
            guideit_db_path=self.playbooks_workspace.db_path,
            catalog_repo=self.scripts_workspace.repo,
            root_dir=self.playbooks_workspace.root_dir,
            playbook_limit=6,
            script_limit=6,
        )
        self._last_unified_response = response
        self._last_unified_query = text

        self.omnibox_results_list.clear()
        tags_note = (
            f"  •  Tags: {', '.join(response.expanded_tags[:5])}"
            if response.expanded_tags
            else ""
        )
        self.omnibox_status_label.setText(
            f"{response.total_playbook_hits} playbook(s)  •  "
            f"{response.total_script_hits} script(s){tags_note}"
        )

        first_selectable_row = -1

        if response.playbook_hits:
            hdr = QListWidgetItem(f"📘 PLAYBOOKS ({response.total_playbook_hits})")
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            hdr.setForeground(QColor("#38BDF8"))
            self.omnibox_results_list.addItem(hdr)
            for pb in response.playbook_hits:
                item = QListWidgetItem(f"  [{pb.id}] {pb.title}  —  {pb.tier} • {pb.subject}")
                item.setData(Qt.ItemDataRole.UserRole, ("playbook", pb.id))
                item.setToolTip(
                    f"{pb.path}\nClick to open Playbook (Shift+Click for Split View)"
                )
                self.omnibox_results_list.addItem(item)
                if first_selectable_row == -1:
                    first_selectable_row = self.omnibox_results_list.count() - 1

        if response.script_hits:
            hdr = QListWidgetItem(f"⚡ POWERSHELL SCRIPTS ({response.total_script_hits})")
            hdr.setFlags(Qt.ItemFlag.NoItemFlags)
            hdr.setForeground(QColor("#C084FC"))
            self.omnibox_results_list.addItem(hdr)
            for sc in response.script_hits:
                admin_str = "ADMIN" if sc.requires_admin else "USER"
                item = QListWidgetItem(
                    f"  {sc.title}  —  {sc.relative_path} [{sc.risk_level.upper()} | {admin_str}]"
                )
                item.setData(Qt.ItemDataRole.UserRole, ("script", sc.relative_path))
                item.setToolTip(
                    f"{sc.synopsis}\nClick to open Script (Shift+Click for Split View)"
                )
                self.omnibox_results_list.addItem(item)
                if first_selectable_row == -1:
                    first_selectable_row = self.omnibox_results_list.count() - 1

        if first_selectable_row == -1:
            empty_item = QListWidgetItem("No matching playbooks or PowerShell scripts found.")
            empty_item.setFlags(Qt.ItemFlag.NoItemFlags)
            empty_item.setForeground(QColor("#93A4B8"))
            self.omnibox_results_list.addItem(empty_item)
        else:
            self.omnibox_results_list.setCurrentRow(first_selectable_row)

        self._position_omnibox_popup()
        self.omnibox_popup.show()
        self.omnibox_popup.raise_()
        return response

    def _on_omnibox_item_activated(self, item: QListWidgetItem) -> None:
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, tuple) or len(payload) != 2:
            return
        kind, target = payload
        split_view = bool(
            QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        self.omnibox_popup.hide()
        if kind == "playbook":
            self.event_bus.open_playbook_requested.emit(str(target), split_view)
        elif kind == "script":
            self.event_bus.open_script_requested.emit(str(target), {}, split_view)

    def _sync_all_libraries(self) -> None:
        self.scripts_workspace.sync_and_refresh()
        self.playbooks_workspace.start_reindex()

    def _handle_escape(self) -> None:
        if self.scripts_workspace.runner.is_running:
            self.scripts_workspace._handle_escape()
        elif self.omnibox_popup.isVisible():
            self.omnibox_popup.hide()
        elif self._current_mode == MODE_PLAYBOOKS:
            self.playbooks_workspace.handle_escape()
        else:
            self.scripts_workspace._handle_escape()

    # ------------------------------------------------------------------
    # EventBus Cross-Module Orchestration
    # ------------------------------------------------------------------

    def _on_catalog_synced(self) -> None:
        self.cross_link_service.invalidate_cache()
        self.playbooks_workspace.refresh_current_playbook()
        self.playbooks_workspace.refresh_validation()

    def _on_playbooks_reindexed(self) -> None:
        self.cross_link_service.invalidate_cache()
        self.scripts_workspace.refresh_reverse_playbook_links()

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
            validated = coerce_param_overrides(script.params, params)
            merged.update(validated)
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
            self.scripts_workspace.run_current_script_locally()

    def _on_open_playbook_requested(self, playbook_id: str, split_view: bool) -> None:
        self.playbooks_workspace.navigate_to_playbook(playbook_id)
        self.set_mode(MODE_SPLIT if split_view else MODE_PLAYBOOKS)

    def _shortcut_copy_linked_readonly_bundle(self) -> None:
        if self._current_mode not in (MODE_PLAYBOOKS, MODE_SPLIT):
            self.status_bar.showMessage(
                "Switch to Playbooks (Alt+1) or Split View (Alt+3) to copy a playbook's read-only script bundle.",
                3000,
            )
            return
        if not self.playbooks_workspace.trigger_copy_readonly_bundle():
            self.status_bar.showMessage(
                "Current playbook has fewer than 2 linked read-only scripts to bundle.",
                3000,
            )

    def _playbook_excluded_remediation_count(self, relative_paths: list[str]) -> int:
        normalized = [
            str(p).strip().replace("\\", "/")
            for p in relative_paths
            if str(p).strip()
        ]
        viewer = self.playbooks_workspace.viewer
        if (
            normalized
            and set(normalized) == set(viewer.linked_readonly_paths)
            and viewer.linked_remediation_count > 0
        ):
            return viewer.linked_remediation_count
        return 0

    def _on_copy_scripts_bundle_requested(
        self, relative_paths: list[str], rmm_ready: bool
    ) -> None:
        excluded_hint = self._playbook_excluded_remediation_count(relative_paths)
        self.scripts_workspace.copy_readonly_scripts_bundle(
            relative_paths,
            rmm_ready=rmm_ready,
            excluded_remediation_count=excluded_hint,
        )

    def _on_select_scripts_batch_requested(self, relative_paths: list[str]) -> None:
        excluded_hint = self._playbook_excluded_remediation_count(relative_paths)
        loaded_count, _excluded, toast_msg = self.scripts_workspace.load_readonly_scripts_batch(
            relative_paths,
            excluded_remediation_count=excluded_hint,
            emit_status=False,
        )
        if loaded_count > 0:
            self.set_mode(MODE_SCRIPTS)
        self.status_bar.showMessage(toast_msg, 5000)

    def _shortcut_toggle_pin_favorite(self) -> None:
        if self._current_mode == MODE_SCRIPTS:
            self.scripts_workspace.toggle_current_script_favorite()
        elif self._current_mode == MODE_SPLIT:
            focus_widget = QApplication.focusWidget()
            if focus_widget is not None and (
                focus_widget is self.scripts_workspace
                or self.scripts_workspace.isAncestorOf(focus_widget)
            ):
                self.scripts_workspace.toggle_current_script_favorite()
            else:
                self.playbooks_workspace.toggle_current_playbook_favorite()
        else:
            self.playbooks_workspace.toggle_current_playbook_favorite()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "omnibox_popup") and self.omnibox_popup.isVisible():
            self._position_omnibox_popup()

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
            self.playbooks_workspace.shutdown_workers()
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
        self.playbooks_workspace.shutdown_workers()
        self.hotkey_manager.unregister()
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        self.close()
        app = QApplication.instance()
        if app:
            app.quit()
