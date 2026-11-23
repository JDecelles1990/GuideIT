"""PowerShellStore 3-pane workspace widget embedded inside UnifiedShellWindow."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QFileSystemWatcher, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from guideit_master.core.event_bus import AppEventBus
from guideit_master.paths import is_frozen
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo, ScriptRecord
from guideit_master.psstore.services.clipboard_service import ClipboardService
from guideit_master.psstore.services.report_service import ReportService
from guideit_master.psstore.services.runner import (
    RunResult,
    ScriptRunner,
    is_running_as_admin,
)
from guideit_master.psstore.services.scanner import ScriptScanner
from guideit_master.psstore.ui.catalog_table_view import CatalogTableView
from guideit_master.psstore.ui.console_view import ConsoleView
from guideit_master.psstore.ui.parameter_form import ParameterFormWidget
from guideit_master.psstore.ui.sidebar_view import SidebarView
from guideit_master.services.cross_link_service import (
    CrossLinkService,
    coerce_param_overrides,
)
from guideit_master.services.user_state_service import UserStateService
from guideit_master.ui.flow_layout import FlowLayout

logger = logging.getLogger(__name__)


class ScriptsWorkspaceWidget(QWidget):
    """Pure QWidget hosting the 3-pane PowerShellStore script workstation.

    Shell-level concerns (QSystemTrayIcon, closeEvent minimize-to-tray, opacity
    slider, StartupService, and GlobalHotkeyManager) live exclusively on
    UnifiedShellWindow.
    """

    status_message_requested = Signal(str, int)
    startup_toggled = Signal(bool)
    playbook_link_clicked = Signal(str, bool)

    def __init__(
        self,
        repo: CatalogRepo | None = None,
        scanner: ScriptScanner | None = None,
        clipboard_service: ClipboardService | None = None,
        runner: ScriptRunner | None = None,
        report_service: ReportService | None = None,
        event_bus: AppEventBus | None = None,
        cross_link_service: CrossLinkService | None = None,
        user_state_service: UserStateService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.repo = repo if repo is not None else CatalogRepo()
        self.scanner = scanner if scanner is not None else ScriptScanner(repo=self.repo)
        self.clipboard_service = (
            clipboard_service
            if clipboard_service is not None
            else ClipboardService(
                scripts_dir=self.scanner.scripts_dir,
                user_scripts_dir=self.scanner.user_scripts_dir,
            )
        )
        self.runner = (
            runner
            if runner is not None
            else ScriptRunner(
                scripts_dir=self.scanner.scripts_dir,
                repo=self.repo,
                user_scripts_dir=self.scanner.user_scripts_dir,
            )
        )
        self.report_service = (
            report_service if report_service is not None else ReportService()
        )
        self.event_bus = event_bus
        self.cross_link_service = cross_link_service
        self.user_state_service = (
            user_state_service if user_state_service is not None else UserStateService()
        )

        self._current_script: ScriptRecord | None = None
        self._saved_params: dict[str, dict[str, Any]] = {}
        self._sidebar_expanded: bool = True
        self._compact_mode: bool = False
        self._is_bulk_refreshing: bool = False
        self._favorites_strip_collapsed: bool = False
        self.used_in_playbook_buttons: dict[str, QPushButton] = {}
        self.favorite_script_buttons: dict[str, QPushButton] = {}
        self.recent_script_buttons: dict[str, QPushButton] = {}

        self._init_ui()
        self._init_watcher()
        self._connect_signals()
        self.sync_and_refresh(show_toast=False)

    @property
    def is_compact_mode(self) -> bool:
        return self._compact_mode

    def _emit_status(self, message: str, timeout_ms: int = 0) -> None:
        self.status_message_requested.emit(message, timeout_ms)
        if self.event_bus is not None:
            self.event_bus.status_toast_requested.emit(message, timeout_ms)

    def _init_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)

        self.favorites_strip = QFrame(self)
        self.favorites_strip.setObjectName("favoritesStrip")
        strip_layout = QHBoxLayout(self.favorites_strip)
        strip_layout.setContentsMargins(12, 4, 12, 4)
        strip_layout.setSpacing(6)
        strip_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.favorites_strip_toggle_btn = QPushButton("▾ ★ Quick Access", self.favorites_strip)
        self.favorites_strip_toggle_btn.setObjectName("stripToggleButton")
        self.favorites_strip_toggle_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.favorites_strip_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorites_strip_toggle_btn.setToolTip(
            "Collapse or expand pinned Favorites & Recents script strip"
        )
        self.favorites_strip_toggle_btn.clicked.connect(self._toggle_favorites_strip)
        strip_layout.addWidget(self.favorites_strip_toggle_btn)

        self.favorites_pills_scroll = QScrollArea(self.favorites_strip)
        self.favorites_pills_scroll.setWidgetResizable(True)
        self.favorites_pills_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.favorites_pills_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.favorites_pills_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.favorites_pills_scroll.setFixedHeight(30)
        self.favorites_pills_scroll.viewport().setStyleSheet("background: transparent;")

        self.favorites_pills_container = QWidget(self.favorites_pills_scroll)
        self.favorites_pills_container.setStyleSheet("background: transparent;")
        self._favorites_pills_layout = QHBoxLayout(self.favorites_pills_container)
        self._favorites_pills_layout.setContentsMargins(0, 0, 0, 0)
        self._favorites_pills_layout.setSpacing(6)
        self.favorites_pills_scroll.setWidget(self.favorites_pills_container)

        strip_layout.addWidget(self.favorites_pills_scroll, 1)
        self.favorites_strip.setVisible(False)
        root_layout.addWidget(self.favorites_strip)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.sidebar = SidebarView()
        self.splitter.addWidget(self.sidebar)

        self.catalog_view = CatalogTableView()
        self.splitter.addWidget(self.catalog_view)

        self.inspector_frame = QFrame()
        self.inspector_frame.setObjectName("InspectorFrame")
        self._init_inspector_ui()
        self.splitter.addWidget(self.inspector_frame)

        self.splitter.setCollapsible(0, True)
        self.splitter.setCollapsible(1, False)
        self.splitter.setCollapsible(2, False)
        self.splitter.setSizes([240, 450, 670])
        root_layout.addWidget(self.splitter, 1)

    def _init_inspector_ui(self) -> None:
        layout = QVBoxLayout(self.inspector_frame)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top_header_layout = QHBoxLayout()
        top_header_layout.setContentsMargins(0, 0, 0, 0)
        top_header_layout.setSpacing(12)

        self.script_title_label = QLabel("Select a Script")
        self.script_title_label.setObjectName("HeaderTitle")
        self.script_title_label.setWordWrap(True)
        top_header_layout.addWidget(self.script_title_label, 1)

        self.pin_script_btn = QPushButton("☆ Pin")
        self.pin_script_btn.setObjectName("pinButton")
        self.pin_script_btn.setCheckable(True)
        self.pin_script_btn.setEnabled(False)
        self.pin_script_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_script_btn.setToolTip("Pin script to Favorites (Ctrl+D)")
        self.pin_script_btn.clicked.connect(self.toggle_current_script_favorite)
        top_header_layout.addWidget(self.pin_script_btn)

        layout.addLayout(top_header_layout)

        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)

        self.category_chip = QLabel("Category")
        self.category_chip.setStyleSheet(
            "background-color: #374151; color: #93c5fd; padding: 2px 8px; "
            "border-radius: 4px; font-weight: 500;"
        )
        chips_layout.addWidget(self.category_chip)

        self.risk_chip = QLabel("READ-ONLY")
        self.risk_chip.setStyleSheet(
            "background-color: #065f46; color: #34d399; padding: 2px 8px; "
            "border-radius: 4px; font-weight: 500;"
        )
        chips_layout.addWidget(self.risk_chip)

        self.admin_chip = QLabel("ADMIN NOT REQUIRED")
        self.admin_chip.setStyleSheet(
            "background-color: #374151; color: #9ca3af; padding: 2px 8px; border-radius: 4px;"
        )
        chips_layout.addWidget(self.admin_chip)

        self.edition_chip = QLabel("Desktop 5.1")
        self.edition_chip.setStyleSheet(
            "background-color: #374151; color: #9ca3af; padding: 2px 8px; border-radius: 4px;"
        )
        chips_layout.addWidget(self.edition_chip)

        self.timeout_chip = QLabel("30s Timeout")
        self.timeout_chip.setStyleSheet(
            "background-color: #374151; color: #9ca3af; padding: 2px 8px; border-radius: 4px;"
        )
        chips_layout.addWidget(self.timeout_chip)

        self.source_chip = QLabel("👤 USER SCRIPT")
        self.source_chip.setStyleSheet(
            "background-color: #3b0764; color: #e9d5ff; padding: 2px 8px; "
            "border-radius: 4px; font-weight: 600;"
        )
        self.source_chip.setToolTip("Custom user script loaded from user_scripts/ overlay")
        self.source_chip.setVisible(False)
        chips_layout.addWidget(self.source_chip)

        chips_layout.addStretch()
        layout.addLayout(chips_layout)

        self.used_in_playbooks_container = QWidget(self.inspector_frame)
        self.used_in_playbooks_container.setStyleSheet("background: transparent;")
        self._used_in_playbooks_layout = FlowLayout(self.used_in_playbooks_container, spacing=6)
        self._used_in_playbooks_layout.setContentsMargins(0, 2, 0, 2)
        self.used_in_playbooks_container.setVisible(False)
        layout.addWidget(self.used_in_playbooks_container)

        self.synopsis_label = QLabel(
            "Select a script from the catalog to configure parameters and run or copy."
        )
        self.synopsis_label.setWordWrap(True)
        self.synopsis_label.setStyleSheet("color: #9ca3af; font-size: 12px; margin-top: 4px;")
        layout.addWidget(self.synopsis_label)

        self.param_form = ParameterFormWidget()
        layout.addWidget(self.param_form)

        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        self.copy_raw_btn = QPushButton("📋 Copy Raw Script")
        self.copy_raw_btn.setToolTip(
            "Copies exact .ps1 file from disk to the Windows Clipboard (Ctrl+Shift+C)"
        )
        self.copy_raw_btn.clicked.connect(self._on_copy_raw_clicked)
        action_bar.addWidget(self.copy_raw_btn)

        self.copy_rmm_btn = QPushButton("⚡ Copy RMM-Ready Script")
        self.copy_rmm_btn.setObjectName("PrimaryButton")
        self.copy_rmm_btn.setToolTip(
            "Injects custom UI parameter values into param() defaults and copies to clipboard (Ctrl+Shift+R)"
        )
        self.copy_rmm_btn.clicked.connect(self._on_copy_rmm_clicked)
        action_bar.addWidget(self.copy_rmm_btn)

        self.run_local_btn = QPushButton("▶ Test Locally on My PC")
        self.run_local_btn.setObjectName("SuccessButton")
        self.run_local_btn.setToolTip(
            "Executes script in non-blocking test sandbox via QProcess (Ctrl+Enter)"
        )
        self.run_local_btn.clicked.connect(self._on_run_local_clicked)
        action_bar.addWidget(self.run_local_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setObjectName("DangerButton")
        self.stop_btn.setToolTip("Stops the currently running local script (Shift+F5 or Esc)")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.runner.stop_execution)
        action_bar.addWidget(self.stop_btn)

        layout.addLayout(action_bar)

        self.console_view = ConsoleView(report_service=self.report_service)
        layout.addWidget(self.console_view, 1)

    def _refresh_watched_dirs(self) -> None:
        """Registers bundled and writable user script directories in QFileSystemWatcher."""
        candidate_roots = [
            d
            for d in (self.scanner.scripts_dir, self.scanner.user_scripts_dir)
            if d is not None
        ]
        desired: set[str] = set()
        for root_path in candidate_roots:
            if root_path.exists():
                desired.add(str(root_path.resolve()))
                for sub in root_path.glob("*/"):
                    if sub.is_dir():
                        desired.add(str(sub.resolve()))
        existing = set(self.watcher.directories())
        to_add = sorted(desired - existing)
        if to_add:
            self.watcher.addPaths(to_add)

    def _init_watcher(self) -> None:
        """Sets up live filesystem watching for automatic catalog reload."""
        self.watcher = QFileSystemWatcher(self)
        self._refresh_watched_dirs()

        self.watcher.directoryChanged.connect(self._on_fs_changed)
        self.watcher.fileChanged.connect(self._on_fs_changed)

    def _on_fs_changed(self, path: str) -> None:
        logger.info("Filesystem change detected at %s. Syncing catalog...", path)
        self._refresh_watched_dirs()
        self.sync_and_refresh(show_toast=False)

    def _connect_signals(self) -> None:
        self.sidebar.filter_changed.connect(self._on_filters_changed)
        self.sidebar.sync_requested.connect(self.sync_and_refresh)
        self.sidebar.startup_toggled.connect(self.startup_toggled.emit)
        self.catalog_view.toggle_sidebar_requested.connect(self.toggle_sidebar)
        self.catalog_view.open_scripts_folder_requested.connect(self.open_scripts_folder)
        self.catalog_view.script_selected.connect(self._on_script_selected)
        self.catalog_view.checked_scripts_changed.connect(self._on_checked_scripts_changed)

        self.param_form.values_changed.connect(self._on_param_values_changed)
        self.console_view.status_message_requested.connect(self._emit_status)

        self.runner.started.connect(self._on_run_started)
        self.runner.batch_progress.connect(self._on_batch_progress)
        self.runner.output_received.connect(self.console_view.append_raw_output)
        self.runner.finished.connect(self._on_run_finished)
        self.runner.error_occurred.connect(self._on_run_error)

    def set_compact_mode(self, compact: bool) -> None:
        """Toggles compact Split View layout without reparenting widgets."""
        self._compact_mode = bool(compact)
        if self._compact_mode:
            self.favorites_strip.setVisible(False)
            self.sidebar.setVisible(False)
            self.catalog_view.setVisible(False)
        else:
            self.refresh_favorites_and_recents_strip()
            self.catalog_view.setVisible(True)
            self.sidebar.setVisible(self._sidebar_expanded)
            self.catalog_view.set_sidebar_button_state(self._sidebar_expanded)
            self.splitter.setSizes([240, 450, 670])

    def _toggle_favorites_strip(self) -> None:
        self._favorites_strip_collapsed = not self._favorites_strip_collapsed
        self.refresh_favorites_and_recents_strip()

    def refresh_favorites_and_recents_strip(self) -> None:
        """Rebuild the single-row Favorites & Recents script pills strip."""
        while self._favorites_pills_layout.count():
            item = self._favorites_pills_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.favorite_script_buttons.clear()
        self.recent_script_buttons.clear()

        scripts_by_path = {s.relative_path: s for s in self.repo.get_all_scripts()}
        favs = [
            p for p in self.user_state_service.get_favorite_scripts() if p in scripts_by_path
        ]
        fav_set = set(favs)
        recents = [
            p
            for p in self.user_state_service.get_recent_scripts()
            if p in scripts_by_path and p not in fav_set
        ]

        if not favs and not recents:
            self.favorites_strip.setVisible(False)
            return

        if favs:
            fav_lbl = QLabel("★ Favorites:", self.favorites_pills_container)
            fav_lbl.setStyleSheet(
                "color: #FBBF24; font-size: 11.5px; font-weight: 700; background: transparent;"
            )
            self._favorites_pills_layout.addWidget(fav_lbl)
            for rel_path in favs:
                rec = scripts_by_path[rel_path]
                btn = QPushButton(f"★ {rec.title}", self.favorites_pills_container)
                btn.setObjectName("favoritePill")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(f"★ {rec.title} ({rel_path}) — Click to select")
                btn.clicked.connect(
                    lambda _checked=False, target=rel_path: self._on_quick_script_pill_clicked(
                        target
                    )
                )
                self._favorites_pills_layout.addWidget(btn)
                self.favorite_script_buttons[rel_path] = btn

        if recents:
            rec_lbl = QLabel("🕒 Recent:", self.favorites_pills_container)
            rec_lbl.setStyleSheet(
                "color: #9ca3af; font-size: 11.5px; font-weight: 600; background: transparent;"
            )
            self._favorites_pills_layout.addWidget(rec_lbl)
            for rel_path in recents:
                rec = scripts_by_path[rel_path]
                btn = QPushButton(rec.title, self.favorites_pills_container)
                btn.setObjectName("recentPill")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(f"{rec.title} ({rel_path}) — Click to select")
                btn.clicked.connect(
                    lambda _checked=False, target=rel_path: self._on_quick_script_pill_clicked(
                        target
                    )
                )
                self._favorites_pills_layout.addWidget(btn)
                self.recent_script_buttons[rel_path] = btn

        self._favorites_pills_layout.addStretch(1)

        if self._favorites_strip_collapsed:
            self.favorites_strip_toggle_btn.setText(
                f"▸ ★ Quick Access ({len(favs)}★ · {len(recents)}🕒)"
            )
        else:
            self.favorites_strip_toggle_btn.setText("▾ ★ Quick Access")
        self.favorites_pills_scroll.setVisible(not self._favorites_strip_collapsed)
        self.favorites_strip.setVisible(not self._compact_mode)

    def _on_quick_script_pill_clicked(self, relative_path: str) -> None:
        visible_paths = {s.relative_path for s in self.catalog_view._scripts}
        if relative_path not in visible_paths and self.sidebar.has_active_filters():
            self.sidebar.reset_filters(emit_signal=True)
        self.select_and_preload_script(relative_path)

    def _update_pin_button_state(self) -> None:
        if self._current_script is None:
            self.pin_script_btn.blockSignals(True)
            try:
                self.pin_script_btn.setEnabled(False)
                self.pin_script_btn.setChecked(False)
                self.pin_script_btn.setText("☆ Pin")
                self.pin_script_btn.setProperty("pinned", False)
                self.pin_script_btn.setToolTip("Pin script to Favorites (Ctrl+D)")
                self.pin_script_btn.style().unpolish(self.pin_script_btn)
                self.pin_script_btn.style().polish(self.pin_script_btn)
            finally:
                self.pin_script_btn.blockSignals(False)
            return

        pinned = self.user_state_service.is_favorite_script(self._current_script.relative_path)
        self.pin_script_btn.blockSignals(True)
        try:
            self.pin_script_btn.setEnabled(True)
            self.pin_script_btn.setChecked(pinned)
            self.pin_script_btn.setText("★ Pinned" if pinned else "☆ Pin")
            self.pin_script_btn.setProperty("pinned", pinned)
            self.pin_script_btn.setToolTip(
                "Unpin script from Favorites (Ctrl+D)"
                if pinned
                else "Pin script to Favorites (Ctrl+D)"
            )
            self.pin_script_btn.style().unpolish(self.pin_script_btn)
            self.pin_script_btn.style().polish(self.pin_script_btn)
        finally:
            self.pin_script_btn.blockSignals(False)

    def _record_recent_script(self, relative_path: str) -> None:
        self.user_state_service.record_recent_script(relative_path)
        self.refresh_favorites_and_recents_strip()
        if self.event_bus is not None:
            self.event_bus.user_state_changed.emit()

    def toggle_script_favorite(self, relative_path: str) -> bool:
        """Toggle Favorite pin for a script and refresh pin button, strip, and filters."""
        norm_rel = relative_path.strip().replace("\\", "/")
        if not norm_rel:
            return False
        pinned = self.user_state_service.toggle_favorite_script(norm_rel)
        self._update_pin_button_state()
        self.refresh_favorites_and_recents_strip()
        if self.sidebar.pinned_only_checkbox.isChecked():
            self._on_filters_changed(
                self.sidebar._current_category,
                self.sidebar.search_input.text(),
                self.sidebar.risk_combo.currentText(),
                self.sidebar.edition_combo.currentText(),
            )
        if self.event_bus is not None:
            self.event_bus.user_state_changed.emit()
        script = self.repo.get_script_by_path(norm_rel)
        label = script.title if script is not None else norm_rel
        action = "★ Pinned" if pinned else "☆ Unpinned"
        self._emit_status(f"{action} '{label}' {'to' if pinned else 'from'} Favorites", 3000)
        return pinned

    def toggle_current_script_favorite(self) -> bool:
        """Toggle Favorite pin for the currently selected script."""
        if self._current_script is None:
            return False
        return self.toggle_script_favorite(self._current_script.relative_path)

    def set_startup_checked(self, enabled: bool) -> None:
        self.sidebar.set_startup_checked(enabled)

    def toggle_sidebar(self) -> None:
        """Toggles sidebar visibility to expand workspace for the other two panes."""
        self._sidebar_expanded = not self._sidebar_expanded
        if not self._compact_mode:
            self.sidebar.setVisible(self._sidebar_expanded)
            self.catalog_view.set_sidebar_button_state(self._sidebar_expanded)
        state_msg = (
            "Sidebar expanded"
            if self._sidebar_expanded
            else "Sidebar collapsed (more space for catalog & workstation)"
        )
        self._emit_status(state_msg, 2500)

    def open_scripts_folder(self) -> None:
        """Opens user_scripts/ overlay when frozen or powershell_scripts/ in development."""
        if is_frozen() and self.scanner.user_scripts_dir is not None:
            scripts_dir = self.scanner.user_scripts_dir.resolve()
            create_if_missing = True
        else:
            scripts_dir = self.scanner.scripts_dir.resolve()
            create_if_missing = not is_frozen()

        try:
            if create_if_missing:
                scripts_dir.mkdir(parents=True, exist_ok=True)
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(scripts_dir)))
        except Exception as exc:
            logger.warning("Failed to open scripts folder %s: %s", scripts_dir, exc)
            opened = False

        if opened:
            self._emit_status(f"📂 Opened scripts catalog folder: {scripts_dir}", 4000)
        else:
            QMessageBox.warning(
                self,
                "Open Folder Failed",
                f"Could not open the scripts catalog folder:\n{scripts_dir}",
            )
            self._emit_status("Failed to open scripts catalog folder.", 4000)

    def _focus_search_input(self) -> None:
        """Restores catalog & sidebar if needed and focuses the script search input."""
        if self._compact_mode:
            self.set_compact_mode(False)
        if not self._sidebar_expanded:
            self.toggle_sidebar()
        self.sidebar.search_input.setFocus()
        self.sidebar.search_input.selectAll()

    def _handle_escape(self) -> None:
        """Stops a running script if executing; otherwise clears active search filter."""
        if self.runner.is_running:
            self.runner.stop_execution()
            self._emit_status("Stopping running script...", 2500)
        elif self.sidebar.search_input.text():
            self.sidebar.search_input.clear()
            self.catalog_view.table.setFocus()
            self._emit_status("Search filter cleared", 2000)
        elif self.sidebar.search_input.hasFocus():
            self.catalog_view.table.setFocus()

    def _shortcut_run_local(self) -> None:
        """Runs the checked scripts or selected script locally via shortcut when idle."""
        targets = self.catalog_view.get_checked_scripts() or (
            [self._current_script] if self._current_script else []
        )
        if targets and not self.runner.is_running:
            self._on_run_local_clicked()

    def _shortcut_check_all_visible(self) -> None:
        self.catalog_view.check_all_visible()
        count = len(self.catalog_view._scripts)
        self._emit_status(f"Checked {count} visible script(s)", 2500)

    def _shortcut_check_read_only_visible(self) -> None:
        count = self.catalog_view.check_read_only_visible()
        self._emit_status(f"Checked {count} visible READ-ONLY script(s)", 2500)

    def _shortcut_clear_checked(self) -> None:
        self.catalog_view.clear_checked_scripts()
        self._emit_status("Cleared all checked scripts", 2500)

    def _on_param_values_changed(self, values: dict[str, Any]) -> None:
        if self._current_script:
            self._saved_params[self._current_script.relative_path] = dict(values)

    def _get_effective_params(self, script: ScriptRecord) -> dict[str, Any]:
        if (
            self._current_script
            and script.relative_path == self._current_script.relative_path
        ):
            return self.param_form.get_parameter_values()
        if script.relative_path in self._saved_params:
            return dict(self._saved_params[script.relative_path])
        return {
            p["name"]: p.get("default")
            for p in (script.params or [])
            if p.get("name")
        }

    def _on_checked_scripts_changed(self, checked: list[ScriptRecord]) -> None:
        count = len(checked)
        if count == 0:
            self.copy_raw_btn.setText("📋 Copy Raw Script")
            self.copy_rmm_btn.setText("⚡ Copy RMM-Ready Script")
            self.run_local_btn.setText("▶ Test Locally on My PC")
        else:
            suffix = f"({count} Script)" if count == 1 else f"({count} Scripts)"
            self.copy_raw_btn.setText(f"📋 Copy Raw {suffix}")
            self.copy_rmm_btn.setText(f"⚡ Copy RMM-Ready {suffix}")
            self.run_local_btn.setText(f"▶ Run {count} Checked Locally")

    def _shortcut_stop_execution(self) -> None:
        if self.runner.is_running:
            self.runner.stop_execution()

    def _shortcut_reset_parameters(self) -> None:
        if self._current_script and self._current_script.params:
            self.param_form.reset_to_defaults()
            self._emit_status("↺ Parameters reset to script defaults", 2500)

    def _switch_console_tab(self, index: int) -> None:
        if 0 <= index < self.console_view.count():
            self.console_view.setCurrentIndex(index)

    def _shortcut_copy_report(self) -> None:
        if self.console_view.copy_report_btn.isEnabled():
            self.console_view._on_copy_report_clicked()
        else:
            self._emit_status("No execution result loaded to copy as a ticket report.", 3000)

    def _shortcut_save_report(self) -> None:
        if self.console_view.save_report_btn.isEnabled():
            self.console_view._on_save_report_clicked()
        else:
            self._emit_status("No execution result loaded to save.", 3000)

    def _shortcut_clear_console(self) -> None:
        self.console_view.clear_raw_output()
        self._emit_status("Raw console cleared", 2000)

    def set_cross_link_service(self, service: CrossLinkService | None) -> None:
        """Attach CrossLinkService and refresh reverse 'Used in Playbooks' badges."""
        self.cross_link_service = service
        self.refresh_reverse_playbook_links()

    def refresh_reverse_playbook_links(self) -> None:
        """Update the 'Used in Playbooks:' pill row for the currently selected script."""
        self._used_in_playbooks_layout.clear_widgets()
        self.used_in_playbook_buttons.clear()

        if self.cross_link_service is None or self._current_script is None:
            self.used_in_playbooks_container.setVisible(False)
            return

        playbooks = self.cross_link_service.get_playbooks_for_script(
            self._current_script.relative_path
        )
        if not playbooks:
            self.used_in_playbooks_container.setVisible(False)
            return

        prefix_lbl = QLabel("📘 Used in Playbooks:", self.used_in_playbooks_container)
        prefix_lbl.setStyleSheet(
            "color: #9ca3af; font-size: 12px; font-weight: 600; background: transparent;"
        )
        self._used_in_playbooks_layout.addWidget(prefix_lbl)

        for pb in playbooks:
            btn = QPushButton(f"[{pb.id}]", self.used_in_playbooks_container)
            btn.setObjectName("relatedPill")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(
                f"[{pb.id}] {pb.title} ({pb.tier} • {pb.subject})\n"
                "Click to open playbook (Shift+Click for Split View)"
            )
            btn.clicked.connect(
                lambda _checked=False, target_id=pb.id: self._on_reverse_playbook_clicked(
                    target_id
                )
            )
            self._used_in_playbooks_layout.addWidget(btn)
            self.used_in_playbook_buttons[pb.id] = btn

        self.used_in_playbooks_container.setVisible(True)

    def _on_reverse_playbook_clicked(self, playbook_id: str) -> None:
        split_view = bool(
            QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        self.playbook_link_clicked.emit(playbook_id, split_view)
        if self.event_bus is not None:
            self.event_bus.open_playbook_requested.emit(playbook_id, split_view)

    def select_and_preload_script(
        self,
        relative_path: str,
        param_overrides: dict[str, Any] | None = None,
    ) -> bool:
        """Selects a script by relative path and preloads validated parameter overrides."""
        norm_rel = relative_path.replace("\\", "/")
        script = self.repo.get_script_by_path(norm_rel)
        if script is None:
            self._emit_status(f"Linked script not found: {norm_rel}", 4000)
            return False

        validated_overrides = coerce_param_overrides(script.params, param_overrides)
        if validated_overrides:
            merged = self._get_effective_params(script)
            merged.update(validated_overrides)
            self._saved_params[script.relative_path] = merged

        if script.id is not None:
            self.catalog_view.select_script_by_id(script.id)
        if (
            self._current_script is None
            or self._current_script.relative_path != script.relative_path
        ):
            self._on_script_selected(script)
        else:
            self._record_recent_script(script.relative_path)
            if validated_overrides:
                self.param_form.set_parameter_values(validated_overrides)
                self._on_param_values_changed(self.param_form.get_parameter_values())

        return True

    def _resolve_readonly_scripts(
        self,
        relative_paths: list[str],
        *,
        excluded_remediation_count: int = 0,
    ) -> tuple[list[ScriptRecord], int]:
        """Resolve canonical paths to read-only ScriptRecords, strictly excluding remediations."""
        readonly_scripts: list[ScriptRecord] = []
        seen: set[str] = set()
        excluded_in_input = 0

        for raw in relative_paths:
            norm_rel = str(raw).strip().replace("\\", "/")
            if not norm_rel or norm_rel in seen:
                continue
            seen.add(norm_rel)
            script = self.repo.get_script_by_path(norm_rel)
            if script is None:
                continue
            if script.risk_level == "remediation":
                excluded_in_input += 1
                continue
            if script.risk_level == "read_only":
                readonly_scripts.append(script)

        effective_excluded = (
            excluded_in_input
            if excluded_in_input > 0
            else max(0, int(excluded_remediation_count))
        )
        return readonly_scripts, effective_excluded

    @staticmethod
    def _format_readonly_toast(
        action: str,
        count: int,
        excluded_remediation: int,
        *,
        rmm_ready: bool = True,
    ) -> str:
        script_word = "script" if count == 1 else "scripts"
        rem_note = (
            f" (excluded {excluded_remediation} remediation script"
            f"{'s' if excluded_remediation != 1 else ''})"
            if excluded_remediation > 0
            else ""
        )
        if action == "copy":
            mode_str = "RMM" if rmm_ready else "raw"
            return f"📦 Copied {count} read-only {mode_str} {script_word} as bundle{rem_note}"
        return f"☑ Loaded {count} read-only {script_word} into batch{rem_note}"

    def copy_readonly_scripts_bundle(
        self,
        relative_paths: list[str],
        *,
        rmm_ready: bool = True,
        excluded_remediation_count: int = 0,
        emit_status: bool = True,
    ) -> str:
        """Bundle and copy ONLY linked read_only scripts, respecting saved parameters."""
        readonly_scripts, excluded = self._resolve_readonly_scripts(
            relative_paths,
            excluded_remediation_count=excluded_remediation_count,
        )
        if not readonly_scripts:
            if emit_status:
                self._emit_status(
                    "No read-only scripts available to bundle (remediation scripts are excluded).",
                    4000,
                )
            return ""

        try:
            if rmm_ready:
                items = [
                    (s.title, s.relative_path, self._get_effective_params(s))
                    for s in readonly_scripts
                ]
                content = self.clipboard_service.copy_rmm_ready_scripts(items)
            else:
                items_raw = [(s.title, s.relative_path) for s in readonly_scripts]
                content = self.clipboard_service.copy_raw_scripts(items_raw)
        except Exception as exc:
            logger.warning("Failed to copy read-only script bundle: %s", exc)
            if emit_status:
                self._emit_status(f"Failed to copy read-only script bundle: {exc}", 5000)
            return ""

        msg = self._format_readonly_toast(
            "copy",
            len(readonly_scripts),
            excluded,
            rmm_ready=rmm_ready,
        )
        if emit_status:
            self._emit_status(msg, 5000)
        return content

    def load_readonly_scripts_batch(
        self,
        relative_paths: list[str],
        *,
        excluded_remediation_count: int = 0,
        emit_status: bool = True,
    ) -> tuple[int, int, str]:
        """Clear prior checkboxes, check ONLY linked read_only scripts, and select the first."""
        readonly_scripts, excluded = self._resolve_readonly_scripts(
            relative_paths,
            excluded_remediation_count=excluded_remediation_count,
        )
        if not readonly_scripts:
            msg = "No read-only scripts available to load into batch (remediation scripts are excluded)."
            if emit_status:
                self._emit_status(msg, 4000)
            return 0, excluded, msg

        if self.sidebar.has_active_filters():
            self.sidebar.reset_filters(emit_signal=False)
            self._on_filters_changed("All", "", "All", "All")

        self.catalog_view.set_checked_scripts(readonly_scripts)
        first = readonly_scripts[0]
        if first.id is not None:
            self.catalog_view.select_script_by_id(first.id)
        if (
            self._current_script is None
            or self._current_script.relative_path != first.relative_path
        ):
            self._on_script_selected(first)

        msg = self._format_readonly_toast("batch", len(readonly_scripts), excluded)
        if emit_status:
            self._emit_status(msg, 5000)
        return len(readonly_scripts), excluded, msg

    def sync_and_refresh(self, show_toast: bool = True) -> None:
        summary = self.scanner.sync_catalog()
        categories = self.repo.get_categories_with_counts()
        total_scripts = sum(c["count"] for c in categories)

        self.sidebar.update_categories(categories, total_scripts)
        valid_paths = {s.relative_path for s in self.repo.get_all_scripts()}
        self.catalog_view.prune_checked_scripts(valid_paths)
        self._on_filters_changed(
            self.sidebar._current_category,
            self.sidebar.search_input.text(),
            self.sidebar.risk_combo.currentText(),
            self.sidebar.edition_combo.currentText(),
        )
        self.refresh_favorites_and_recents_strip()
        self._update_pin_button_state()

        if self.event_bus is not None:
            self.event_bus.catalog_synced.emit()

        msg = (
            f"Catalog synced: {total_scripts} script(s) loaded "
            f"({summary.added} added, {summary.updated} updated, {summary.deleted} removed)."
        )
        if show_toast:
            self._emit_status(msg, 5000)

    def _on_filters_changed(
        self,
        category: str,
        search: str,
        risk: str,
        edition: str,
    ) -> None:
        risk_filter = risk if risk not in ("All", "All Risks") else None
        edition_filter = edition if edition not in ("All", "All Editions") else None
        scripts = self.repo.get_all_scripts(
            category=category if category != "All" else None,
            search=search if search else None,
            risk_level=risk_filter,
            ps_edition=edition_filter,
        )
        if self.sidebar.pinned_only_checkbox.isChecked():
            pinned_set = set(self.user_state_service.get_favorite_scripts())
            scripts = [s for s in scripts if s.relative_path in pinned_set]

        self._is_bulk_refreshing = True
        try:
            self.catalog_view.set_scripts(scripts)
        finally:
            self._is_bulk_refreshing = False

    def _on_script_selected(self, script: ScriptRecord) -> None:
        self._current_script = script
        self.script_title_label.setText(script.title)
        self.category_chip.setText(script.category)
        self._update_pin_button_state()
        if not self._is_bulk_refreshing:
            self._record_recent_script(script.relative_path)

        if script.risk_level == "remediation":
            self.risk_chip.setText("REMEDIATION")
            self.risk_chip.setStyleSheet(
                "background-color: #78350f; color: #fbbf24; padding: 2px 8px; "
                "border-radius: 4px; font-weight: bold;"
            )
        else:
            self.risk_chip.setText("READ-ONLY")
            self.risk_chip.setStyleSheet(
                "background-color: #065f46; color: #34d399; padding: 2px 8px; "
                "border-radius: 4px; font-weight: bold;"
            )

        if script.requires_admin:
            self.admin_chip.setText("🛡️ REQUIRES ADMIN")
            self.admin_chip.setStyleSheet(
                "background-color: #1e3a8a; color: #60a5fa; padding: 2px 8px; "
                "border-radius: 4px; font-weight: 500;"
            )
        else:
            self.admin_chip.setText("Standard User")
            self.admin_chip.setStyleSheet(
                "background-color: #374151; color: #9ca3af; padding: 2px 8px; border-radius: 4px;"
            )

        self.edition_chip.setText(f"PowerShell {script.ps_edition}")
        self.timeout_chip.setText(f"{script.timeout_seconds}s Timeout")
        self.source_chip.setVisible(script.source == "user")

        self.synopsis_label.setText(script.synopsis or "No synopsis available.")
        self.console_view.set_script_context(script.title, script.category)
        self.refresh_reverse_playbook_links()

        self.param_form.load_script(script)
        if script.relative_path in self._saved_params:
            self.param_form.set_parameter_values(self._saved_params[script.relative_path])

        try:
            raw_code = self.clipboard_service.get_raw_script(script.relative_path)
            self.console_view.set_script_source(raw_code)
        except Exception as e:
            self.console_view.set_script_source(f"# Error reading script source: {e}")

        if script.id:
            history = self.repo.get_history_for_script(script.id)
            self.console_view.display_history(history)

    def _on_copy_raw_clicked(self) -> None:
        checked = self.catalog_view.get_checked_scripts()
        try:
            if len(checked) >= 2:
                items = [(s.title, s.relative_path) for s in checked]
                self.clipboard_service.copy_raw_scripts(items)
                self._emit_status(
                    f"📋 Copied {len(checked)} Raw Scripts as a combined PowerShell bundle!",
                    4000,
                )
            elif len(checked) == 1:
                self.clipboard_service.copy_raw_script(checked[0].relative_path)
                self._emit_status(
                    f"📋 Copied Raw Script '{checked[0].title}' to Windows Clipboard!",
                    4000,
                )
            elif self._current_script:
                self.clipboard_service.copy_raw_script(self._current_script.relative_path)
                self._emit_status("📋 Copied Raw Script to Windows Clipboard!", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Copy Failed", f"Failed to copy raw script: {e}")

    def _on_copy_rmm_clicked(self) -> None:
        checked = self.catalog_view.get_checked_scripts()
        try:
            if len(checked) >= 2:
                items = [
                    (s.title, s.relative_path, self._get_effective_params(s))
                    for s in checked
                ]
                self.clipboard_service.copy_rmm_ready_scripts(items)
                self._emit_status(
                    f"⚡ Copied {len(checked)} RMM-Ready Scripts (with injected parameters) as a combined bundle!",
                    4000,
                )
            elif len(checked) == 1:
                params = self._get_effective_params(checked[0])
                self.clipboard_service.copy_rmm_ready_script(
                    checked[0].relative_path, params
                )
                self._emit_status(
                    f"⚡ Copied RMM-Ready Script '{checked[0].title}' (with injected parameters) to Clipboard!",
                    4000,
                )
            elif self._current_script:
                params = self.param_form.get_parameter_values()
                self.clipboard_service.copy_rmm_ready_script(
                    self._current_script.relative_path, params
                )
                self._emit_status(
                    "⚡ Copied RMM-Ready Script (with injected parameters) to Clipboard!",
                    4000,
                )
        except Exception as e:
            QMessageBox.critical(self, "Copy Failed", f"Failed to copy RMM-ready script: {e}")

    def run_current_script_locally(self) -> None:
        """Executes only the active script through remediation and UAC safety gates."""
        if self._current_script is not None and not self.runner.is_running:
            self._on_run_local_clicked(target_script=self._current_script)

    def _on_run_local_clicked(
        self,
        _checked: bool = False,
        *,
        target_script: ScriptRecord | None = None,
    ) -> None:
        if target_script is not None:
            targets = [target_script]
        else:
            checked = self.catalog_view.get_checked_scripts()
            targets = checked if checked else ([self._current_script] if self._current_script else [])
        if not targets:
            return

        if len(targets) == 1:
            target = targets[0]
            if target.risk_level == "remediation":
                confirm = QMessageBox.warning(
                    self,
                    "Remediation Script Confirmation",
                    f"'{target.title}' is marked as REMEDIATION and will alter system state on this PC.\n\n"
                    "Are you sure you want to test this script locally?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if confirm != QMessageBox.StandardButton.Yes:
                    return

            if target.requires_admin and not is_running_as_admin():
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Administrator Privileges Required")
                msg_box.setIcon(QMessageBox.Icon.Warning)
                msg_box.setText(
                    f"'{target.title}' requires Administrator privileges, but GuideIT Master is currently running un-elevated.\n\n"
                    "How would you like to execute this test?"
                )
                elevated_btn = msg_box.addButton(
                    "🛡️ Run Elevated (UAC Prompt)", QMessageBox.ButtonRole.AcceptRole
                )
                msg_box.addButton(
                    "Run Un-elevated (May Fail)", QMessageBox.ButtonRole.ActionRole
                )
                cancel_btn = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                msg_box.setDefaultButton(elevated_btn)

                msg_box.exec()
                clicked_btn = msg_box.clickedButton()

                if clicked_btn == cancel_btn:
                    return
                if clicked_btn == elevated_btn:
                    params = self._get_effective_params(target)
                    self.runner.execute_script_elevated(target, params)
                    self._emit_status("Launched in elevated PowerShell session (UAC)", 5000)
                    return

            params = self._get_effective_params(target)
            self.console_view.clear_raw_output()
            self.runner.execute_script(target, params)
            return

        remediations = [s for s in targets if s.risk_level == "remediation"]
        if remediations:
            rem_list = "\n".join(f"• {s.title}" for s in remediations)
            confirm = QMessageBox.warning(
                self,
                "Batch Remediation Confirmation",
                f"{len(remediations)} of the {len(targets)} checked scripts are marked as REMEDIATION and will alter system state on this PC:\n\n"
                f"{rem_list}\n\n"
                f"Are you sure you want to run all {len(targets)} checked scripts locally?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        batch_items = [(s, self._get_effective_params(s)) for s in targets]
        admin_scripts = [s for s in targets if s.requires_admin]
        if admin_scripts and not is_running_as_admin():
            admin_list = "\n".join(f"• {s.title}" for s in admin_scripts)
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Administrator Privileges Required")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText(
                f"{len(admin_scripts)} checked script(s) require Administrator privileges, but GuideIT Master is running un-elevated:\n\n"
                f"{admin_list}\n\n"
                "How would you like to execute this batch?"
            )
            elevated_btn = msg_box.addButton(
                "🛡️ Run All Elevated (Single UAC Prompt)", QMessageBox.ButtonRole.AcceptRole
            )
            msg_box.addButton(
                "Run Un-elevated (May Fail)", QMessageBox.ButtonRole.ActionRole
            )
            cancel_btn = msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            msg_box.setDefaultButton(elevated_btn)

            msg_box.exec()
            clicked_btn = msg_box.clickedButton()

            if clicked_btn == cancel_btn:
                return
            if clicked_btn == elevated_btn:
                self.runner.execute_batch_elevated(batch_items)
                self._emit_status(
                    f"Launched {len(batch_items)} scripts in elevated PowerShell session (UAC)",
                    5000,
                )
                return

        self.console_view.clear_raw_output()
        self.runner.execute_batch(batch_items)

    def _on_run_started(self) -> None:
        if not self.runner._batch_active:
            title = self._current_script.title if self._current_script else ""
            self._emit_status(f"Executing '{title}'...", 0)
        self.run_local_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

    def _on_batch_progress(self, step: int, total: int, script: ScriptRecord) -> None:
        self._emit_status(f"Batch [{step}/{total}]: Executing '{script.title}'...", 0)

    def _on_run_finished(self, result: RunResult) -> None:
        self.run_local_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.console_view.display_run_result(
            result,
            script_title=result.script_title
            or (self._current_script.title if self._current_script else ""),
            script_category=result.script_category
            or (self._current_script.category if self._current_script else ""),
        )

        if self._current_script and self._current_script.id:
            history = self.repo.get_history_for_script(self._current_script.id)
            self.console_view.display_history(history)

        self._emit_status(
            f"Execution finished with status '{result.status.upper()}' in {result.duration_ms} ms.",
            5000,
        )

    def _on_run_error(self, message: str) -> None:
        self.run_local_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        QMessageBox.critical(self, "Execution Error", message)
        self._emit_status(f"Execution Error: {message}", 5000)
