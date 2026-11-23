"""Left-pane facet filter sidebar for GuideIT PySide6 desktop app."""

from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from guideit_master.guideit.taxonomy import DomainSpec
from guideit_master.guideit.ui.theme import TEXT_DIM, TEXT_MUTED

DOMAIN_ROLE = int(Qt.ItemDataRole.UserRole)
SUBCAT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class FilterSidebar(QFrame):
    """Faceted filter sidebar controlling tier, subdivided subjects tree, OS, env, and risk."""

    filters_changed = Signal()
    reset_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("filterSidebar")
        self.setMinimumWidth(250)

        self._all_expanded = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        title = QLabel("FILTERS", self)
        title.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px;"
        )
        header_row.addWidget(title)
        header_row.addStretch(1)

        self.reset_button = QPushButton("Reset", self)
        self.reset_button.setObjectName("resetButton")
        self.reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_button.setToolTip("Clear all filters and search query (Ctrl+R)")
        self.reset_button.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.reset_button.clicked.connect(self.reset_requested.emit)
        header_row.addWidget(self.reset_button)
        layout.addLayout(header_row)

        # Tier segmented pills
        layout.addWidget(self._section_label("Tier"))
        tier_row = QHBoxLayout()
        tier_row.setSpacing(4)
        self.tier_group = QButtonGroup(self)
        self.tier_group.setExclusive(True)
        self.tier_buttons: dict[str, QPushButton] = {}
        for label in ("All", "L1", "L2", "L3"):
            btn = QPushButton(label, self)
            btn.setObjectName("tierPill")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if label == "All":
                btn.setChecked(True)
            self.tier_group.addButton(btn)
            self.tier_buttons[label] = btn
            tier_row.addWidget(btn)
        self.tier_group.buttonClicked.connect(lambda _btn: self.filters_changed.emit())
        layout.addLayout(tier_row)

        # Subdivided Subjects tree header + Collapse/Expand button
        subj_row = QHBoxLayout()
        subj_row.setContentsMargins(0, 4, 0, 0)
        subj_lbl = QLabel("Subjects", self)
        subj_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600;")
        subj_row.addWidget(subj_lbl)
        subj_row.addStretch(1)

        self.toggle_expand_button = QPushButton("Collapse", self)
        self.toggle_expand_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_expand_button.setToolTip("Collapse or expand all domain sub-subjects")
        self.toggle_expand_button.setStyleSheet("padding: 1px 8px; font-size: 11px;")
        self.toggle_expand_button.clicked.connect(self._toggle_expand_all)
        subj_row.addWidget(self.toggle_expand_button)
        layout.addLayout(subj_row)

        self.domain_tree = QTreeWidget(self)
        self.domain_tree.setObjectName("domainTree")
        self.domain_tree.setProperty("_skip_glow_delegate", True)
        self.domain_tree.setHeaderHidden(True)
        self.domain_tree.setIndentation(14)
        self.domain_tree.setAnimated(False)
        self.domain_tree.setMinimumHeight(230)
        self.domain_tree.currentItemChanged.connect(lambda _cur, _prev: self.filters_changed.emit())
        layout.addWidget(self.domain_tree, stretch=1)

        # Dropdown facets
        layout.addWidget(self._section_label("Operating System"))
        self.os_combo = QComboBox(self)
        self.os_combo.currentIndexChanged.connect(lambda _idx: self.filters_changed.emit())
        layout.addWidget(self.os_combo)

        layout.addWidget(self._section_label("Environment"))
        self.env_combo = QComboBox(self)
        self.env_combo.currentIndexChanged.connect(lambda _idx: self.filters_changed.emit())
        layout.addWidget(self.env_combo)

        layout.addWidget(self._section_label("Risk Level"))
        self.risk_combo = QComboBox(self)
        self.risk_combo.currentIndexChanged.connect(lambda _idx: self.filters_changed.emit())
        layout.addWidget(self.risk_combo)

        hint = QLabel("Shortcuts: Ctrl+K search • Ctrl+T tools • F5 re-index • Ctrl+R reset", self)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px; margin-top: 4px;")
        layout.addWidget(hint)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text, self)
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; margin-top: 4px;"
        )
        return lbl

    def _toggle_expand_all(self) -> None:
        target_expanded = not self._all_expanded
        for idx in range(self.domain_tree.topLevelItemCount()):
            top_item = self.domain_tree.topLevelItem(idx)
            if top_item is not None and top_item.childCount() > 0:
                top_item.setExpanded(target_expanded)
        self._all_expanded = target_expanded
        self.toggle_expand_button.setText("Collapse" if target_expanded else "Expand")

    def populate_facets(
        self,
        facets: dict[str, list[str]],
        domain_specs: dict[str, DomainSpec],
        domain_counts: dict[str, int],
        subcategory_counts: dict[tuple[str, str], int],
        total_count: int,
    ) -> None:
        """Populate subdivided Subjects tree and dropdown facets while preserving state."""
        prev = self.current_filters()
        collapsed_domains: set[str] = set()
        for idx in range(self.domain_tree.topLevelItemCount()):
            existing = self.domain_tree.topLevelItem(idx)
            if existing is not None:
                dom_val = existing.data(0, DOMAIN_ROLE)
                if dom_val and not existing.isExpanded():
                    collapsed_domains.add(str(dom_val))

        parent_font = QFont(self.font())
        parent_font.setWeight(QFont.Weight.DemiBold)

        child_font = QFont(self.font())
        child_font.setPointSize(max(8, self.font().pointSize() - 1))

        with QSignalBlocker(self.domain_tree):
            self.domain_tree.clear()
            all_item = QTreeWidgetItem([f"All Subjects ({total_count})"])
            all_item.setData(0, DOMAIN_ROLE, None)
            all_item.setData(0, SUBCAT_ROLE, None)
            all_item.setFont(0, parent_font)
            self.domain_tree.addTopLevelItem(all_item)

            target_item: QTreeWidgetItem = all_item
            for dom in facets.get("domains", []):
                prefix_num = dom.split("_", 1)[0]
                spec = domain_specs.get(dom)
                friendly = spec.subject if spec else dom
                count = domain_counts.get(dom, 0)

                dom_item = QTreeWidgetItem([f"{prefix_num}  {friendly} ({count})"])
                dom_item.setData(0, DOMAIN_ROLE, dom)
                dom_item.setData(0, SUBCAT_ROLE, None)
                dom_item.setFont(0, parent_font)
                dom_item.setToolTip(0, f"{dom} — {count} playbook(s)")
                self.domain_tree.addTopLevelItem(dom_item)

                if prev["domain"] == dom and prev["subcategory"] is None:
                    target_item = dom_item

                if spec:
                    for sub in spec.subcategories:
                        sub_cnt = subcategory_counts.get((dom, sub.id), 0)
                        sub_item = QTreeWidgetItem([f"{sub.label} ({sub_cnt})"])
                        sub_item.setData(0, DOMAIN_ROLE, dom)
                        sub_item.setData(0, SUBCAT_ROLE, sub.id)
                        sub_item.setFont(0, child_font)
                        sub_item.setToolTip(0, f"{friendly} › {sub.label} ({sub_cnt})")
                        dom_item.addChild(sub_item)
                        if prev["domain"] == dom and prev["subcategory"] == sub.id:
                            target_item = sub_item

                should_expand = (dom not in collapsed_domains) if collapsed_domains else self._all_expanded
                dom_item.setExpanded(should_expand)

            self.domain_tree.setCurrentItem(target_item)

        self._populate_combo(self.os_combo, "All OS", facets.get("os", []), prev["os_filter"])
        self._populate_combo(
            self.env_combo,
            "All Environments",
            facets.get("environments", []),
            prev["env_filter"],
        )
        self._populate_combo(
            self.risk_combo,
            "All Risk Levels",
            facets.get("risk_levels", []),
            prev["risk_level"],
        )

    def _populate_combo(
        self,
        combo: QComboBox,
        default_label: str,
        values: list[str],
        selected_value: str | None,
    ) -> None:
        with QSignalBlocker(combo):
            combo.clear()
            combo.addItem(default_label, None)
            target_idx = 0
            for idx, val in enumerate(values, start=1):
                combo.addItem(val, val)
                if selected_value == val:
                    target_idx = idx
            combo.setCurrentIndex(target_idx)

    def current_filters(self) -> dict[str, str | None]:
        """Return active filter values matching search_playbooks parameters."""
        checked = self.tier_group.checkedButton()
        tier_val = None if checked is None or checked.text() == "All" else checked.text()

        item = self.domain_tree.currentItem()
        domain_val = item.data(0, DOMAIN_ROLE) if item else None
        subcat_val = item.data(0, SUBCAT_ROLE) if item else None

        return {
            "domain": str(domain_val) if domain_val else None,
            "subcategory": str(subcat_val) if subcat_val else None,
            "tier": tier_val,
            "os_filter": self.os_combo.currentData(),
            "env_filter": self.env_combo.currentData(),
            "risk_level": self.risk_combo.currentData(),
        }

    def reset_filters(self, *, emit_signal: bool = True) -> None:
        """Clear all active sidebar selections back to defaults."""
        with QSignalBlocker(self.tier_group):
            self.tier_buttons["All"].setChecked(True)
        with QSignalBlocker(self.domain_tree):
            if self.domain_tree.topLevelItemCount() > 0:
                self.domain_tree.setCurrentItem(self.domain_tree.topLevelItem(0))
        with QSignalBlocker(self.os_combo):
            self.os_combo.setCurrentIndex(0)
        with QSignalBlocker(self.env_combo):
            self.env_combo.setCurrentIndex(0)
        with QSignalBlocker(self.risk_combo):
            self.risk_combo.setCurrentIndex(0)
        if emit_signal:
            self.filters_changed.emit()
