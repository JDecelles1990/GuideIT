"""3-pane Dark-theme PySide6 Playbooks workspace widget for GuideIT Master."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from guideit_master.core.event_bus import AppEventBus
from guideit_master.guideit.models import IndexStats, ValidationReport
from guideit_master.guideit.search import (
    ensure_index_current,
    get_domain_and_subcategory_counts,
    get_playbook_by_id,
    get_playbook_titles,
    list_facets,
    search_playbooks,
)
from guideit_master.guideit.taxonomy import DomainSpec, load_taxonomy
from guideit_master.guideit.ui.theme import ACCENT, TEXT_DIM, TEXT_MUTED
from guideit_master.guideit.ui.widgets import (
    FilterSidebar,
    PlaybookViewer,
    ResourcesDialog,
    ResultsList,
)
from guideit_master.guideit.ui.workers import ReindexWorker
from guideit_master.guideit.validator import validate_repository
from guideit_master.paths import (
    get_bundle_dir,
    get_guideit_db_path,
    get_playbooks_dir,
    get_taxonomy_dir,
    is_frozen,
)
from guideit_master.services.cross_link_service import CrossLinkService, LinkedScriptSummary
from guideit_master.services.user_state_service import UserStateService


class ValidationDialog(QDialog):
    """Dark modal displaying strict schema, freshness, and PII validation findings."""

    def __init__(self, report: ValidationReport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("GuideIT Validation & Multi-Tenant PII Report")
        self.resize(740, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        summary = QLabel(
            f"Checked {report.checked_files} playbook(s): "
            f"{len(report.errors)} error(s), {len(report.warnings)} warning(s).",
            self,
        )
        summary.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(summary)

        log = QPlainTextEdit(self)
        log.setObjectName("reportLog")
        log.setReadOnly(True)
        if not report.issues:
            log.setPlainText(
                "All playbooks passed strict schema validation, heading order checks, "
                "related_ids verification, freshness checks, and multi-tenant PII redaction rules."
            )
        else:
            lines = []
            for issue in report.issues:
                loc = f"{issue.path}:{issue.line}" if issue.line else issue.path
                lines.append(f"[{issue.severity.upper()}] {issue.code} ({loc}): {issue.message}")
            log.setPlainText("\n".join(lines))
        layout.addWidget(log, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close_btn = QPushButton("Close", self)
        close_btn.setObjectName("accentButton")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class PlaybooksWorkspaceWidget(QWidget):
    """Pure QWidget 3-pane Dark MSP Playbooks search & copy console."""

    status_message_requested = Signal(str, int)
    validation_report_updated = Signal(object)
    index_status_updated = Signal(str)

    def __init__(
        self,
        root_dir: Path | None = None,
        db_path: Path | None = None,
        event_bus: AppEventBus | None = None,
        cross_link_service: CrossLinkService | None = None,
        user_state_service: UserStateService | None = None,
        embedded_in_shell: bool = False,
        reindex_debounce_ms: int = 500,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.root_dir = (root_dir if root_dir is not None else get_bundle_dir()).resolve()
        self.db_path = db_path.resolve() if db_path is not None else get_guideit_db_path()
        self.event_bus = event_bus
        self.cross_link_service = cross_link_service
        if user_state_service is not None:
            self.user_state_service = user_state_service
        elif db_path is not None:
            self.user_state_service = UserStateService(
                state_path=self.db_path.parent / "user_state.json"
            )
        else:
            self.user_state_service = UserStateService()
        self._embedded_in_shell = bool(embedded_in_shell)

        self._compact_mode = False
        self._sidebar_expanded = True
        self._history: list[str] = []
        self._worker: ReindexWorker | None = None
        self._pending_reindex: bool = False
        self._auto_reindex_active: bool = False
        self._pending_auto_reindex: bool = False
        self._reindex_debounce_ms: int = max(0, int(reindex_debounce_ms))
        self._last_report: ValidationReport | None = None
        self._domain_specs: dict[str, DomainSpec] = {}
        self._domain_labels: dict[str, str] = {}
        self._subcategory_labels: dict[tuple[str, str], str] = {}
        self._titles_by_id: dict[str, str] = {}
        self._index_status_text = ""
        self._favorites_strip_collapsed = False
        self.favorite_playbook_buttons: dict[str, QPushButton] = {}
        self.recent_playbook_buttons: dict[str, QPushButton] = {}

        self.setWindowTitle("GuideIT — MSP Troubleshooting Playbooks (L1–L3)")

        self.db_path = ensure_index_current(self.root_dir, db_path=self.db_path)
        self._load_domain_labels()
        self._build_ui()
        self._init_watcher()
        if not self._embedded_in_shell:
            self._setup_shortcuts()

        # Initial data population
        self._last_report = validate_repository(self.root_dir)
        self._update_health_pill(self._last_report)
        self._refresh_facets()
        self.run_search()
        self._update_index_status()
        self.refresh_favorites_and_recents_strip()

    @property
    def is_compact_mode(self) -> bool:
        return self._compact_mode

    @property
    def last_report(self) -> ValidationReport | None:
        return self._last_report

    @property
    def index_status_text(self) -> str:
        return self._index_status_text

    def _emit_status(self, message: str, timeout_ms: int = 0) -> None:
        self.status_message_requested.emit(message, timeout_ms)
        if self.event_bus is not None:
            self.event_bus.status_toast_requested.emit(message, timeout_ms)

    def _load_domain_labels(self) -> None:
        try:
            taxonomy = load_taxonomy(self.root_dir)
            self._domain_specs = dict(taxonomy.domains_by_folder)
            self._domain_labels = {
                folder: spec.subject for folder, spec in taxonomy.domains_by_folder.items()
            }
            self._subcategory_labels = {
                (folder, sub.id): sub.label
                for folder, spec in taxonomy.domains_by_folder.items()
                for sub in spec.subcategories
            }
        except Exception:
            self._domain_specs = {}
            self._domain_labels = {}
            self._subcategory_labels = {}

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Top command bar
        self.top_bar = QFrame(self)
        self.top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(14, 8, 14, 8)
        top_layout.setSpacing(10)

        self.brand_widget = QWidget(self.top_bar)
        self.brand_widget.setStyleSheet("background: transparent;")
        brand_box = QVBoxLayout(self.brand_widget)
        brand_box.setContentsMargins(0, 0, 0, 0)
        brand_box.setSpacing(0)
        brand_title = QLabel("GuideIT", self.brand_widget)
        brand_title.setStyleSheet(
            f"font-size: 16px; font-weight: 800; color: {ACCENT}; background: transparent;"
        )
        brand_sub = QLabel("L1–L3 MSP Playbooks", self.brand_widget)
        brand_sub.setStyleSheet(f"font-size: 11px; color: {TEXT_DIM}; background: transparent;")
        brand_box.addWidget(brand_title)
        brand_box.addWidget(brand_sub)
        top_layout.addWidget(self.brand_widget)

        self.search_input = QLineEdit(self.top_bar)
        self.search_input.setObjectName("searchInput")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText(
            "Search EN/FR symptoms, error codes (4740, 0x0000011b, compte verrouillé)...  [Ctrl+K]"
        )
        self.search_input.setToolTip(
            "Search EN/FR playbooks, symptoms, or error codes (Ctrl+K)"
        )
        top_layout.addWidget(self.search_input, stretch=1)

        self.tools_button = QPushButton("Useful Tools (Ctrl+T)", self.top_bar)
        self.tools_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tools_button.setToolTip(
            "Open curated MSP & Data Center websites (MXToolbox, VirusTotal, Subnet Calculator, Adobe, Licensing) (Ctrl+T)"
        )
        self.tools_button.clicked.connect(self.open_resources_dialog)
        top_layout.addWidget(self.tools_button)

        self.health_button = QPushButton("Checking...", self.top_bar)
        self.health_button.setObjectName("healthPill")
        self.health_button.setProperty("status", "unknown")
        self.health_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.health_button.setToolTip("Click to inspect validation & multi-tenant PII report")
        self.health_button.clicked.connect(self.show_validation_dialog)
        top_layout.addWidget(self.health_button)

        self.reindex_button = QPushButton("Validate & Re-Index (F5)", self.top_bar)
        self.reindex_button.setObjectName("accentButton")
        self.reindex_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reindex_button.setToolTip(
            "Validate playbooks and rebuild the SQLite FTS5 search index (F5)"
        )
        self.reindex_button.clicked.connect(lambda: self.start_reindex(auto_triggered=False))
        top_layout.addWidget(self.reindex_button)

        if self._embedded_in_shell:
            # Shell header owns brand, Useful Tools (Ctrl+T), and Health Pill globally.
            self.brand_widget.setVisible(False)
            self.tools_button.setVisible(False)
            self.health_button.setVisible(False)

        main_layout.addWidget(self.top_bar)

        # Compact single-row collapsible Favorites & Recents strip
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
            "Collapse or expand pinned Favorites & Recents strip"
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

        strip_layout.addWidget(self.favorites_pills_scroll, stretch=1)
        self.favorites_strip.setVisible(False)
        main_layout.addWidget(self.favorites_strip)

        # Expanded taxonomy strip
        self.expansion_bar = QFrame(self)
        self.expansion_bar.setObjectName("expansionBar")
        exp_layout = QHBoxLayout(self.expansion_bar)
        exp_layout.setContentsMargins(16, 5, 16, 5)
        self.expansion_label = QLabel("", self.expansion_bar)
        self.expansion_label.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;"
        )
        exp_layout.addWidget(self.expansion_label)
        exp_layout.addStretch(1)
        self.expansion_bar.setVisible(False)
        main_layout.addWidget(self.expansion_bar)

        # 3-pane splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.filter_sidebar = FilterSidebar(self.splitter)
        self.results_list = ResultsList(self.splitter)
        self.viewer = PlaybookViewer(self.splitter)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([275, 345, 740])
        main_layout.addWidget(self.splitter, stretch=1)

        # Index status label (surfaced in UnifiedShellWindow's status bar when embedded)
        self.index_status_label = QLabel("", self)
        self.index_status_label.setStyleSheet(f"color: {TEXT_DIM}; padding: 2px 10px; font-size: 12px;")
        if self._embedded_in_shell:
            self.index_status_label.setVisible(False)
        else:
            main_layout.addWidget(self.index_status_label)

        # Signals & debounced search
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(120)
        self._search_timer.timeout.connect(self.run_search)

        self.search_input.textChanged.connect(lambda _txt: self._search_timer.start())
        self.search_input.returnPressed.connect(self.run_search_now)

        self.filter_sidebar.filters_changed.connect(self.run_search)
        self.filter_sidebar.reset_requested.connect(self.reset_all)
        self.results_list.reset_requested.connect(self.reset_all)
        self.results_list.playbook_selected.connect(self._on_result_selected)
        self.viewer.related_playbook_clicked.connect(self.navigate_to_playbook)
        self.viewer.back_requested.connect(self.navigate_back)
        self.viewer.status_message.connect(lambda msg: self._emit_status(msg, 3000))
        self.viewer.open_script_requested.connect(self._on_viewer_open_script)
        self.viewer.copy_script_requested.connect(self._on_viewer_copy_script)
        self.viewer.copy_scripts_bundle_requested.connect(self._on_viewer_copy_scripts_bundle)
        self.viewer.select_scripts_batch_requested.connect(self._on_viewer_select_scripts_batch)
        self.viewer.run_script_requested.connect(self._on_viewer_run_script)
        self.viewer.pin_toggled.connect(self.toggle_playbook_favorite)

    def _init_watcher(self) -> None:
        """Set up debounced recursive live watcher on playbooks/ and taxonomy/."""
        self.watcher = QFileSystemWatcher(self)
        self._reindex_debounce_timer = QTimer(self)
        self._reindex_debounce_timer.setSingleShot(True)
        self._reindex_debounce_timer.setInterval(self._reindex_debounce_ms)
        self._reindex_debounce_timer.timeout.connect(self._on_reindex_debounce_timeout)

        self.watcher.directoryChanged.connect(self._on_fs_changed)
        self.watcher.fileChanged.connect(self._on_fs_changed)
        self._refresh_watched_dirs()

    def _refresh_watched_dirs(self) -> list[str]:
        """Register playbooks/, all domain subdirectories, and taxonomy/ when not frozen."""
        if is_frozen():
            return []

        playbooks_dir = get_playbooks_dir(self.root_dir)
        taxonomy_dir = get_taxonomy_dir(self.root_dir)
        desired: set[str] = set()
        if playbooks_dir.is_dir():
            desired.add(str(playbooks_dir.resolve()))
            for sub in playbooks_dir.rglob("*"):
                if sub.is_dir():
                    desired.add(str(sub.resolve()))
        if taxonomy_dir.is_dir():
            desired.add(str(taxonomy_dir.resolve()))

        existing = set(self.watcher.directories())
        to_add = sorted(desired - existing)
        if to_add:
            self.watcher.addPaths(to_add)
        return sorted(self.watcher.directories())

    def _on_fs_changed(self, path: str) -> None:
        if is_frozen():
            return
        self._refresh_watched_dirs()
        self._pending_auto_reindex = True
        self._reindex_debounce_timer.start()

    def _on_reindex_debounce_timeout(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._pending_reindex = True
            self._pending_auto_reindex = True
            return
        self.start_reindex(auto_triggered=True)

    def _setup_shortcuts(self) -> None:
        focus_search = QShortcut(QKeySequence("Ctrl+K"), self)
        focus_search.activated.connect(self.focus_search)

        tools_sc = QShortcut(QKeySequence("Ctrl+T"), self)
        tools_sc.activated.connect(self.open_resources_dialog)

        reindex_sc = QShortcut(QKeySequence("F5"), self)
        reindex_sc.activated.connect(lambda: self.start_reindex(auto_triggered=False))

        reset_sc = QShortcut(QKeySequence("Ctrl+R"), self)
        reset_sc.activated.connect(self.reset_all)

        back_sc = QShortcut(QKeySequence("Alt+Left"), self)
        back_sc.activated.connect(self.navigate_back)

        bundle_sc = QShortcut(QKeySequence("Ctrl+Shift+B"), self)
        bundle_sc.activated.connect(self.trigger_copy_readonly_bundle)

        pin_sc = QShortcut(QKeySequence("Ctrl+D"), self)
        pin_sc.activated.connect(self.toggle_current_playbook_favorite)

        esc_sc = QShortcut(QKeySequence("Escape"), self.search_input)
        esc_sc.activated.connect(self.handle_escape)

    def set_compact_mode(self, compact: bool) -> None:
        """Toggle compact Split View layout without reparenting widgets."""
        self._compact_mode = bool(compact)
        if self._compact_mode:
            self.top_bar.setVisible(False)
            self.favorites_strip.setVisible(False)
            self.expansion_bar.setVisible(False)
            self.filter_sidebar.setVisible(False)
            self.results_list.setVisible(False)
        else:
            self.top_bar.setVisible(True)
            self.refresh_favorites_and_recents_strip()
            self.expansion_bar.setVisible(bool(self.expansion_label.text()))
            self.results_list.setVisible(True)
            self.filter_sidebar.setVisible(self._sidebar_expanded)
            self.splitter.setSizes([275, 345, 740])

    def _toggle_favorites_strip(self) -> None:
        self._favorites_strip_collapsed = not self._favorites_strip_collapsed
        self.refresh_favorites_and_recents_strip()

    def refresh_favorites_and_recents_strip(self) -> None:
        """Rebuild single-row Favorites & Recents pills strip from UserStateService."""
        while self._favorites_pills_layout.count():
            item = self._favorites_pills_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.favorite_playbook_buttons.clear()
        self.recent_playbook_buttons.clear()

        favs = [
            pid
            for pid in self.user_state_service.get_favorite_playbooks()
            if pid in self._titles_by_id
        ]
        fav_set = set(favs)
        recents = [
            pid
            for pid in self.user_state_service.get_recent_playbooks()
            if pid in self._titles_by_id and pid not in fav_set
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
            for pid in favs:
                title = self._titles_by_id.get(pid, pid)
                btn = QPushButton(f"★ {pid}", self.favorites_pills_container)
                btn.setObjectName("favoritePill")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(f"★ [{pid}] {title} — Click to open")
                btn.clicked.connect(
                    lambda _checked=False, target=pid: self.navigate_to_playbook(target)
                )
                self._favorites_pills_layout.addWidget(btn)
                self.favorite_playbook_buttons[pid] = btn

        if recents:
            rec_lbl = QLabel("🕒 Recent:", self.favorites_pills_container)
            rec_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 11.5px; font-weight: 600; background: transparent;"
            )
            self._favorites_pills_layout.addWidget(rec_lbl)
            for pid in recents:
                title = self._titles_by_id.get(pid, pid)
                btn = QPushButton(pid, self.favorites_pills_container)
                btn.setObjectName("recentPill")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(f"[{pid}] {title} — Click to open")
                btn.clicked.connect(
                    lambda _checked=False, target=pid: self.navigate_to_playbook(target)
                )
                self._favorites_pills_layout.addWidget(btn)
                self.recent_playbook_buttons[pid] = btn

        self._favorites_pills_layout.addStretch(1)

        if self._favorites_strip_collapsed:
            self.favorites_strip_toggle_btn.setText(
                f"▸ ★ Quick Access ({len(favs)}★ · {len(recents)}🕒)"
            )
        else:
            self.favorites_strip_toggle_btn.setText("▾ ★ Quick Access")
        self.favorites_pills_scroll.setVisible(not self._favorites_strip_collapsed)
        self.favorites_strip.setVisible(not self._compact_mode)

    def toggle_sidebar(self) -> None:
        """Toggle left facet filter sidebar visibility when not in Split View."""
        self._sidebar_expanded = not self._sidebar_expanded
        if not self._compact_mode:
            self.filter_sidebar.setVisible(self._sidebar_expanded)
        msg = (
            "Playbooks filter sidebar expanded"
            if self._sidebar_expanded
            else "Playbooks filter sidebar collapsed"
        )
        self._emit_status(msg, 2500)

    def focus_search(self) -> None:
        """Focus and select all text in the playbook search input."""
        self.search_input.setFocus()
        self.search_input.selectAll()

    def handle_escape(self) -> None:
        """Clear the playbook search bar if populated."""
        if self.search_input.text():
            self.search_input.clear()
            self.run_search_now()

    def _refresh_facets(self) -> None:
        facets = list_facets(self.db_path)
        domain_counts, subcategory_counts, _ = get_domain_and_subcategory_counts(self.db_path)
        self._titles_by_id = get_playbook_titles(self.db_path)
        total_count = sum(domain_counts.values())
        self.filter_sidebar.populate_facets(
            facets,
            self._domain_specs,
            domain_counts,
            subcategory_counts,
            total_count,
        )

    def _update_index_status(self) -> None:
        domain_counts, _, built_at = get_domain_and_subcategory_counts(self.db_path)
        total = sum(domain_counts.values())
        stamp = built_at.replace("T", " ").replace("+00:00", " UTC") if built_at else "unknown"
        self._index_status_text = f"Index: {total} playbooks  •  Built: {stamp}"
        self.index_status_label.setText(self._index_status_text)
        self.index_status_updated.emit(self._index_status_text)

    def _update_health_pill(self, report: ValidationReport) -> None:
        err_cnt = len(report.errors)
        warn_cnt = len(report.warnings)
        if err_cnt > 0:
            status = "err"
            text = f"✕ {err_cnt} Error(s)"
        elif warn_cnt > 0:
            status = "warn"
            text = f"⚠ {warn_cnt} Warning(s)"
        else:
            status = "ok"
            text = f"✓ {report.checked_files} Valid"

        self.health_button.setText(text)
        self.health_button.setProperty("status", status)
        self.health_button.style().unpolish(self.health_button)
        self.health_button.style().polish(self.health_button)
        self.validation_report_updated.emit(report)

    def run_search_now(self) -> None:
        self._search_timer.stop()
        self.run_search()

    def run_search(self) -> None:
        """Query the SQLite FTS5 index with current query text and sidebar filters."""
        query = self.search_input.text().strip()
        filters = self.filter_sidebar.current_filters()
        prev_id = self.viewer.current_playbook_id

        response = search_playbooks(
            self.db_path,
            query,
            root_dir=self.root_dir,
            domain=filters["domain"],
            subcategory=filters["subcategory"],
            tier=filters["tier"],
            os_filter=filters["os_filter"],
            env_filter=filters["env_filter"],
            risk_level=filters["risk_level"],
            limit=200,
        )

        # Update taxonomy expansion strip
        if response.expanded_tags or response.suggested_domains:
            parts: list[str] = []
            if response.expanded_tags:
                parts.append("Expanded tags: " + ", ".join(response.expanded_tags))
            if response.suggested_domains:
                parts.append("Suggested domain: " + ", ".join(response.suggested_domains))
            self.expansion_label.setText("   •   ".join(parts))
            self.expansion_bar.setVisible(not self._compact_mode)
        else:
            self.expansion_label.setText("")
            self.expansion_bar.setVisible(False)

        self.results_list.set_results(response, preserve_id=prev_id)
        selected_id = self.results_list.selected_playbook_id()
        if selected_id:
            self._load_playbook_into_viewer(selected_id, push_history=False)
        else:
            self.viewer.clear_view(
                "No playbooks matched your current search or filters. "
                "Use Reset Filters to browse all playbooks."
            )

    def _on_result_selected(self, playbook_id: str) -> None:
        self._history.clear()
        self._load_playbook_into_viewer(playbook_id, push_history=False, record_recent=True)

    def toggle_playbook_favorite(self, playbook_id: str) -> bool:
        """Pin or unpin a playbook in UserStateService and refresh UI state."""
        pinned = self.user_state_service.toggle_favorite_playbook(playbook_id)
        if self.viewer.current_playbook_id == playbook_id:
            self.viewer.set_pinned_state(pinned)
        self.refresh_favorites_and_recents_strip()
        if self.event_bus is not None:
            self.event_bus.user_state_changed.emit()
        action = "★ Pinned" if pinned else "☆ Unpinned"
        self._emit_status(f"{action} [{playbook_id}] {'to' if pinned else 'from'} Favorites", 3000)
        return pinned

    def toggle_current_playbook_favorite(self) -> bool:
        """Toggle Favorite pin for whichever playbook is currently open in PlaybookViewer."""
        if not self.viewer.current_playbook_id:
            return False
        return self.toggle_playbook_favorite(self.viewer.current_playbook_id)

    def set_cross_link_service(self, service: CrossLinkService | None) -> None:
        """Attach CrossLinkService and refresh the active playbook's linked script cards."""
        self.cross_link_service = service
        self.refresh_current_playbook()

    def refresh_current_playbook(self) -> None:
        """Reload the currently displayed playbook so linked script metadata stays fresh."""
        if self.viewer.current_playbook_id:
            self._load_playbook_into_viewer(self.viewer.current_playbook_id, push_history=False)

    def refresh_validation(self) -> ValidationReport:
        """Re-run repository validation and update the Health Pill."""
        self._last_report = validate_repository(self.root_dir)
        self._update_health_pill(self._last_report)
        return self._last_report

    def _on_viewer_open_script(
        self, relative_path: str, param_overrides: dict, split_view: bool
    ) -> None:
        if self.event_bus is not None:
            self.event_bus.open_script_requested.emit(relative_path, param_overrides, split_view)

    def _on_viewer_copy_script(
        self, relative_path: str, param_overrides: dict, rmm_ready: bool
    ) -> None:
        if self.event_bus is not None:
            self.event_bus.copy_script_requested.emit(relative_path, param_overrides, rmm_ready)

    def _on_viewer_copy_scripts_bundle(
        self, relative_paths: list[str], rmm_ready: bool
    ) -> None:
        if self.event_bus is not None:
            self.event_bus.copy_scripts_bundle_requested.emit(relative_paths, rmm_ready)

    def _on_viewer_select_scripts_batch(self, relative_paths: list[str]) -> None:
        if self.event_bus is not None:
            self.event_bus.select_scripts_batch_requested.emit(relative_paths)

    def trigger_copy_readonly_bundle(self) -> bool:
        """Trigger copying the active playbook's linked read-only RMM script bundle."""
        return self.viewer.trigger_copy_readonly_bundle()

    def _on_viewer_run_script(self, relative_path: str, param_overrides: dict) -> None:
        if self.event_bus is not None:
            self.event_bus.run_script_requested.emit(relative_path, param_overrides)

    def _load_playbook_into_viewer(
        self,
        playbook_id: str,
        *,
        push_history: bool,
        record_recent: bool = False,
    ) -> None:
        if push_history and self.viewer.current_playbook_id and self.viewer.current_playbook_id != playbook_id:
            if not self._history or self._history[-1] != self.viewer.current_playbook_id:
                self._history.append(self.viewer.current_playbook_id)

        record = get_playbook_by_id(self.db_path, playbook_id)
        if record is None:
            self._emit_status(f"Playbook '{playbook_id}' was not found in index.", 3000)
            return

        linked_paths = [str(item) for item in record.get("linked_scripts", [])]
        if self.cross_link_service is not None:
            linked_summaries = self.cross_link_service.get_scripts_for_paths(linked_paths)
        else:
            linked_summaries = [
                LinkedScriptSummary(
                    relative_path=p,
                    title=Path(p).stem,
                    category=p.split("/", 1)[0] if "/" in p else "Custom",
                    risk_level="read_only",
                    requires_admin=False,
                    synopsis="",
                    exists=True,
                )
                for p in linked_paths
            ]

        subcat_label = self._subcategory_labels.get(
            (str(record.get("domain", "")), str(record.get("subcategory", ""))),
            "",
        )
        is_pinned = self.user_state_service.is_favorite_playbook(playbook_id)
        self.viewer.display_playbook(
            record,
            root_dir=self.root_dir,
            can_go_back=bool(self._history),
            titles_by_id=self._titles_by_id,
            subcategory_label=subcat_label,
            linked_scripts=linked_summaries,
            is_pinned=is_pinned,
        )
        if record_recent:
            self.user_state_service.record_recent_playbook(playbook_id)
            self.refresh_favorites_and_recents_strip()
            if self.event_bus is not None:
                self.event_bus.user_state_changed.emit()

    def navigate_to_playbook(self, playbook_id: str) -> None:
        """Navigate directly to a related playbook and record history for Back."""
        if playbook_id == self.viewer.current_playbook_id:
            return
        self._load_playbook_into_viewer(playbook_id, push_history=True, record_recent=True)
        self.results_list.select_playbook_id(playbook_id)
        self._emit_status(f"Navigated to [{playbook_id}]", 2500)

    def navigate_back(self) -> None:
        """Return to the previously viewed playbook in history."""
        if not self._history:
            return
        prev_id = self._history.pop()
        self._load_playbook_into_viewer(prev_id, push_history=False)
        self.results_list.select_playbook_id(prev_id)
        self._emit_status(f"Returned to [{prev_id}]", 2500)

    def reset_all(self) -> None:
        """Clear search text, all facet filters, and navigation history."""
        self._search_timer.stop()
        self._history.clear()
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.filter_sidebar.reset_filters(emit_signal=False)
        self.run_search()
        self._emit_status("Cleared playbook search and filters.", 2000)

    def start_reindex(self, *, auto_triggered: bool = False) -> None:
        """Run strict repository validation and rebuild data/guideit.db in background."""
        if self._worker is not None and self._worker.isRunning():
            if auto_triggered:
                self._pending_reindex = True
                self._pending_auto_reindex = True
            return
        self._auto_reindex_active = bool(auto_triggered)
        self._pending_reindex = False
        self._pending_auto_reindex = False
        self.reindex_button.setEnabled(False)
        self.reindex_button.setText("Indexing...")
        if not self._auto_reindex_active:
            self._emit_status("Validating playbooks and rebuilding SQLite FTS5 index...", 0)

        worker = ReindexWorker(self.root_dir, self.db_path, parent=self)
        worker.completed.connect(self._on_reindex_completed)
        worker.failed.connect(self._on_reindex_failed)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_reindex_completed(self, report: ValidationReport, stats: IndexStats) -> None:
        was_auto = self._auto_reindex_active
        self._auto_reindex_active = False
        self._last_report = report
        self._worker = None
        self.reindex_button.setEnabled(True)
        self.reindex_button.setText("Validate & Re-Index (F5)")

        self._load_domain_labels()
        if self.cross_link_service is not None:
            self.cross_link_service.invalidate_cache()
        self._update_health_pill(report)
        self._refresh_facets()
        self.run_search()
        self._update_index_status()
        self.refresh_favorites_and_recents_strip()

        if self.event_bus is not None:
            self.event_bus.playbooks_reindexed.emit()

        if was_auto:
            self._emit_status("Auto-reindexed playbooks after file change", 4000)
        else:
            self._emit_status(
                f"Indexed {stats.indexed_count} playbook(s) — "
                f"{len(report.errors)} error(s), {len(report.warnings)} warning(s).",
                4500,
            )

        if self._pending_reindex:
            follow_up_auto = self._pending_auto_reindex
            self._pending_reindex = False
            self._pending_auto_reindex = False
            QTimer.singleShot(0, lambda: self.start_reindex(auto_triggered=follow_up_auto))

    def _on_reindex_failed(self, error_message: str) -> None:
        self._auto_reindex_active = False
        self._worker = None
        self.reindex_button.setEnabled(True)
        self.reindex_button.setText("Validate & Re-Index (F5)")
        self._emit_status(f"Re-index failed: {error_message}", 6000)
        if self._pending_reindex:
            follow_up_auto = self._pending_auto_reindex
            self._pending_reindex = False
            self._pending_auto_reindex = False
            QTimer.singleShot(0, lambda: self.start_reindex(auto_triggered=follow_up_auto))

    def open_resources_dialog(self) -> None:
        dlg = ResourcesDialog(self.root_dir, parent=self)
        dlg.exec()

    def show_validation_dialog(self) -> None:
        if self._last_report is None:
            self._last_report = validate_repository(self.root_dir)
            self._update_health_pill(self._last_report)
        dlg = ValidationDialog(self._last_report, parent=self)
        dlg.exec()

    _show_validation_dialog = show_validation_dialog

    def shutdown_workers(self) -> None:
        """Stop watchers/timers and ensure any background indexing thread terminates before teardown."""
        self._pending_reindex = False
        self._pending_auto_reindex = False
        if hasattr(self, "_reindex_debounce_timer"):
            self._reindex_debounce_timer.stop()
        if hasattr(self, "watcher"):
            self.watcher.blockSignals(True)
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.shutdown_workers()
        super().closeEvent(event)
