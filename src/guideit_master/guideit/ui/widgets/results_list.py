"""Center-pane ranked search results list and empty-state card."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSignalBlocker, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from guideit_master.guideit.models import SearchHit, SearchResponse
from guideit_master.guideit.ui.theme import ACCENT, ACCENT_BG, RISK_COLORS, TEXT_DIM, TEXT_MUTED, TIER_COLORS


def _make_badge(text: str, bg: str, border: str, fg: str, parent: QWidget) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    lbl.setStyleSheet(
        f"background-color: {bg}; color: {fg}; border: 1px solid {border}; "
        "border-radius: 4px; padding: 1px 6px; font-size: 11px; font-weight: 700;"
    )
    return lbl


class _ResultCardWidget(QWidget):
    """Compact dark card rendered inside each QListWidgetItem."""

    def __init__(self, hit: SearchHit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(6)

        id_badge = QLabel(f"[{hit.id}]", self)
        id_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        id_badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        id_badge.setStyleSheet(
            f"background-color: {ACCENT_BG}; color: {ACCENT}; border: 1px solid #1E5D82; "
            "border-radius: 4px; padding: 1px 6px; "
            "font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 11px; font-weight: 700;"
        )
        top.addWidget(id_badge)

        t_bg, t_border, t_fg = TIER_COLORS.get(hit.tier, ("#1E2736", "#3A475D", "#E6EDF3"))
        top.addWidget(_make_badge(hit.tier, t_bg, t_border, t_fg, self))

        r_bg, r_border, r_fg = RISK_COLORS.get(hit.risk_level, ("#1E2736", "#3A475D", "#E6EDF3"))
        top.addWidget(_make_badge(hit.risk_level.upper(), r_bg, r_border, r_fg, self))

        if hit.requires_admin:
            top.addWidget(_make_badge("ADMIN", "#251E35", "#6D28D9", "#DDD6FE", self))

        top.addStretch(1)
        layout.addLayout(top)

        text_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        title_label = QLabel(hit.title, self)
        title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        title_label.setWordWrap(True)
        title_label.setMinimumWidth(0)
        title_label.setSizePolicy(text_policy)
        title_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #F0F6FC;")
        layout.addWidget(title_label)

        meta_parts: list[str] = []
        if hit.error_codes:
            meta_parts.append("Codes: " + ", ".join(hit.error_codes[:3]))
        if hit.os:
            meta_parts.append("OS: " + ", ".join(hit.os))
        if meta_parts:
            meta_lbl = QLabel("  •  ".join(meta_parts), self)
            meta_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            meta_lbl.setWordWrap(True)
            meta_lbl.setMinimumWidth(0)
            meta_lbl.setSizePolicy(text_policy)
            meta_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_MUTED};")
            layout.addWidget(meta_lbl)

        if hit.matched_reasons and hit.matched_reasons != ["facet_filter"]:
            reasons = ", ".join(hit.matched_reasons[:3])
            reason_lbl = QLabel(f"Match: {reasons}", self)
            reason_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            reason_lbl.setWordWrap(True)
            reason_lbl.setMinimumWidth(0)
            reason_lbl.setSizePolicy(text_policy)
            reason_lbl.setStyleSheet(f"font-size: 11px; color: {TEXT_DIM};")
            layout.addWidget(reason_lbl)

    def fit_to_width(self, avail_width: int) -> QSize:
        """Constrain card width and compute wrapped multi-line height accurately."""
        w = max(180, avail_width)
        self.setFixedWidth(w)
        lay = self.layout()
        if lay is not None:
            lay.activate()
            h = lay.heightForWidth(w) if lay.hasHeightForWidth() else self.heightForWidth(w)
        else:
            h = self.heightForWidth(w)
        if h <= 0:
            h = self.sizeHint().height()
        final_h = max(h, self.minimumSizeHint().height()) + 4
        self.setFixedHeight(final_h)
        return QSize(w, final_h)


class ResultsList(QFrame):
    """Ranked FTS5 search results pane with [NO PLAYBOOK MATCH] empty-state card."""

    playbook_selected = Signal(str)
    reset_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("resultsPane")
        self.setMinimumWidth(290)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.count_label = QLabel("0 playbooks", self)
        self.count_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600;")
        header.addWidget(self.count_label)
        header.addStretch(1)
        layout.addLayout(header)

        self.stack = QStackedWidget(self)

        # Page 0: Ranked results list
        self._last_synced_width: int = 0
        self.results_widget = QListWidget(self)
        self.results_widget.setObjectName("resultsWidget")
        self.results_widget.setProperty("_skip_glow_delegate", True)
        self.results_widget.setSpacing(6)
        self.results_widget.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.results_widget.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results_widget.viewport().installEventFilter(self)
        self.results_widget.currentItemChanged.connect(self._on_current_item_changed)
        self.stack.addWidget(self.results_widget)

        # Page 1: [NO PLAYBOOK MATCH] empty-state card
        empty_container = QWidget(self)
        empty_layout = QVBoxLayout(empty_container)
        empty_layout.setContentsMargins(0, 16, 0, 0)

        empty_card = QFrame(empty_container)
        empty_card.setObjectName("emptyStateCard")
        card_layout = QVBoxLayout(empty_card)
        card_layout.setContentsMargins(16, 16, 16, 16)
        card_layout.setSpacing(10)

        badge = QLabel("[NO PLAYBOOK MATCH]", empty_card)
        badge.setStyleSheet(
            "color: #FBBF24; font-family: 'Cascadia Mono', 'Consolas', monospace; "
            "font-size: 13px; font-weight: 700;"
        )
        card_layout.addWidget(badge)

        self.empty_detail_label = QLabel(
            "No indexed playbooks matched your current query or facet filters.",
            empty_card,
        )
        self.empty_detail_label.setWordWrap(True)
        self.empty_detail_label.setStyleSheet(f"color: {TEXT_MUTED}; line-height: 1.4;")
        card_layout.addWidget(self.empty_detail_label)

        tip = QLabel(
            "Tip: Clear filters to browse all playbooks, or use the Antigravity "
            "'new-playbook' skill after resolving this ticket.",
            empty_card,
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px;")
        card_layout.addWidget(tip)

        reset_btn = QPushButton("Reset Search & Filters", empty_card)
        reset_btn.setObjectName("accentButton")
        reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_btn.clicked.connect(self.reset_requested.emit)
        card_layout.addWidget(reset_btn)

        empty_layout.addWidget(empty_card)
        empty_layout.addStretch(1)
        self.stack.addWidget(empty_container)

        layout.addWidget(self.stack, stretch=1)

    def _on_current_item_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        pb_id = current.data(Qt.ItemDataRole.UserRole)
        if pb_id:
            self.playbook_selected.emit(str(pb_id))

    def set_results(self, response: SearchResponse, *, preserve_id: str | None = None) -> None:
        """Render ranked search hits or switch to [NO PLAYBOOK MATCH] card."""
        total = response.total_hits
        noun = "playbook" if total == 1 else "playbooks"
        self.count_label.setText(f"{total} {noun}")

        if not response.hits:
            with QSignalBlocker(self.results_widget):
                self.results_widget.clear()
            if response.query.strip():
                self.empty_detail_label.setText(
                    f"No playbooks matched query \"{response.query}\" under the active filters."
                )
            else:
                self.empty_detail_label.setText(
                    "No playbooks matched the currently selected sidebar filters."
                )
            self.stack.setCurrentIndex(1)
            return

        self.stack.setCurrentIndex(0)
        selected_row = 0

        with QSignalBlocker(self.results_widget):
            self.results_widget.clear()
            avail_w = self._available_card_width()
            for idx, hit in enumerate(response.hits):
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, hit.id)
                card = _ResultCardWidget(hit, self.results_widget)
                size = card.fit_to_width(avail_w)
                item.setSizeHint(size)
                self.results_widget.addItem(item)
                self.results_widget.setItemWidget(item, card)
                if preserve_id and hit.id == preserve_id:
                    selected_row = idx

            self.results_widget.setCurrentRow(selected_row)
        self._sync_item_sizes(force=True)

    def _available_card_width(self) -> int:
        vp_w = self.results_widget.viewport().width()
        if vp_w <= 60:
            vp_w = max(240, self.width() - 40)
        spacing = self.results_widget.spacing()
        return max(180, vp_w - (2 * spacing + 6))

    def _sync_item_sizes(self, *, force: bool = False) -> None:
        if self.results_widget.count() == 0:
            return
        avail_w = self._available_card_width()
        if not force and avail_w == self._last_synced_width:
            return
        self._last_synced_width = avail_w
        for idx in range(self.results_widget.count()):
            item = self.results_widget.item(idx)
            if item is None:
                continue
            card = self.results_widget.itemWidget(item)
            if isinstance(card, _ResultCardWidget):
                item.setSizeHint(card.fit_to_width(avail_w))
        self.results_widget.doItemsLayout()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.results_widget.viewport() and event.type() == QEvent.Type.Resize:
            self._sync_item_sizes()
        return super().eventFilter(watched, event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._sync_item_sizes(force=True)

    def select_playbook_id(self, playbook_id: str) -> bool:
        """Highlight a specific playbook ID in the current list without emitting duplicate signal."""
        for idx in range(self.results_widget.count()):
            item = self.results_widget.item(idx)
            if item and item.data(Qt.ItemDataRole.UserRole) == playbook_id:
                with QSignalBlocker(self.results_widget):
                    self.results_widget.setCurrentRow(idx)
                return True
        return False

    def selected_playbook_id(self) -> str | None:
        item = self.results_widget.currentItem()
        if item is None:
            return None
        val = item.data(Qt.ItemDataRole.UserRole)
        return str(val) if val else None
