"""Left-pane categories, live search, risk/edition filters, and startup checkbox for Scripts workspace."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class SidebarView(QFrame):
    filter_changed = Signal(str, str, str, str)  # category, search, risk, edition
    pinned_only_changed = Signal(bool)
    sync_requested = Signal()
    startup_toggled = Signal(bool)

    def __init__(self, parent: QFrame | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SidebarFrame")
        self._current_category = "All"
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        title = QLabel("PowerShellStore")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        subtitle = QLabel("IT & MSP Script Workstation")
        subtitle.setStyleSheet("color: #9ca3af; font-size: 11px;")
        layout.addWidget(subtitle)

        search_label = QLabel("SEARCH")
        search_label.setObjectName("SectionTitle")
        layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter title or synopsis... (Ctrl+F)")
        self.search_input.setToolTip("Focus search with Ctrl+F; press Esc to clear")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self.search_input)

        cat_label = QLabel("CATEGORIES")
        cat_label.setObjectName("SectionTitle")
        layout.addWidget(cat_label)

        self.category_list = QListWidget()
        self.category_list.itemClicked.connect(self._on_category_clicked)
        layout.addWidget(self.category_list, 1)

        filter_label = QLabel("FILTERS")
        filter_label.setObjectName("SectionTitle")
        layout.addWidget(filter_label)

        risk_layout = QHBoxLayout()
        risk_text = QLabel("Risk:")
        risk_text.setStyleSheet("color: #9ca3af;")
        self.risk_combo = QComboBox()
        self.risk_combo.addItems(["All Risks", "read_only", "remediation"])
        self.risk_combo.currentTextChanged.connect(self._on_filter_changed)
        risk_layout.addWidget(risk_text)
        risk_layout.addWidget(self.risk_combo, 1)
        layout.addLayout(risk_layout)

        edition_layout = QHBoxLayout()
        edition_text = QLabel("Edition:")
        edition_text.setStyleSheet("color: #9ca3af;")
        self.edition_combo = QComboBox()
        self.edition_combo.addItems(["All Editions", "Desktop", "Core"])
        self.edition_combo.currentTextChanged.connect(self._on_filter_changed)
        edition_layout.addWidget(edition_text)
        edition_layout.addWidget(self.edition_combo, 1)
        layout.addLayout(edition_layout)

        self.pinned_only_checkbox = QCheckBox("★ Pinned Only")
        self.pinned_only_checkbox.setToolTip("Show only scripts pinned to Favorites")
        self.pinned_only_checkbox.toggled.connect(self._on_pinned_only_toggled)
        layout.addWidget(self.pinned_only_checkbox)

        self.sync_button = QPushButton("🔄 Sync Catalog")
        self.sync_button.setToolTip("Rescan powershell_scripts/ folder and refresh SQLite catalog (F5)")
        self.sync_button.clicked.connect(self.sync_requested.emit)
        layout.addWidget(self.sync_button)

        int_label = QLabel("STARTUP & SHORTCUTS")
        int_label.setObjectName("SectionTitle")
        layout.addWidget(int_label)

        self.startup_checkbox = QCheckBox("Start with Windows")
        self.startup_checkbox.setToolTip("Automatically launch GuideIT Master on Windows login")
        self.startup_checkbox.toggled.connect(self.startup_toggled.emit)
        layout.addWidget(self.startup_checkbox)

        hotkey_box = QFrame()
        hotkey_box.setStyleSheet(
            "background-color: #111827; border: 1px solid #374151; "
            "border-radius: 4px; padding: 4px 6px;"
        )
        hotkey_box.setToolTip("Press Win+F8 anywhere in Windows to show or minimize GuideIT Master")
        hotkey_layout = QHBoxLayout(hotkey_box)
        hotkey_layout.setContentsMargins(4, 2, 4, 2)
        hotkey_layout.setSpacing(6)

        hotkey_icon = QLabel("⚡")
        hotkey_icon.setStyleSheet("font-size: 11px;")
        hotkey_layout.addWidget(hotkey_icon)

        hotkey_text = QLabel("Hotkey: Win+F8")
        hotkey_text.setStyleSheet(
            "color: #60a5fa; font-size: 11px; font-weight: bold; font-family: Consolas, monospace;"
        )
        hotkey_layout.addWidget(hotkey_text, 1)
        layout.addWidget(hotkey_box)

    def has_active_filters(self) -> bool:
        """Return True if any category, search, risk, or edition filter is active."""
        if self._current_category != "All":
            return True
        if bool(self.search_input.text().strip()):
            return True
        if self.risk_combo.currentText() not in ("All", "All Risks"):
            return True
        if self.edition_combo.currentText() not in ("All", "All Editions"):
            return True
        if self.pinned_only_checkbox.isChecked():
            return True
        return False

    def reset_filters(self, emit_signal: bool = True) -> None:
        """Reset category, search, risk, and edition filters to show all scripts."""
        self._current_category = "All"
        self.search_input.blockSignals(True)
        self.risk_combo.blockSignals(True)
        self.edition_combo.blockSignals(True)
        self.pinned_only_checkbox.blockSignals(True)
        self.category_list.blockSignals(True)
        try:
            self.search_input.clear()
            self.risk_combo.setCurrentIndex(0)
            self.edition_combo.setCurrentIndex(0)
            self.pinned_only_checkbox.setChecked(False)
            for idx in range(self.category_list.count()):
                item = self.category_list.item(idx)
                is_all = bool(item and item.data(100) == "All")
                if item is not None:
                    item.setSelected(is_all)
                    if is_all:
                        self.category_list.setCurrentItem(item)
        finally:
            self.search_input.blockSignals(False)
            self.risk_combo.blockSignals(False)
            self.edition_combo.blockSignals(False)
            self.pinned_only_checkbox.blockSignals(False)
            self.category_list.blockSignals(False)

        if emit_signal:
            self._on_filter_changed()

    def _on_pinned_only_toggled(self, checked: bool) -> None:
        self.pinned_only_changed.emit(checked)
        self._on_filter_changed()

    def set_startup_checked(self, enabled: bool) -> None:
        """Sets the startup checkbox state without emitting signals."""
        self.startup_checkbox.blockSignals(True)
        self.startup_checkbox.setChecked(enabled)
        self.startup_checkbox.blockSignals(False)

    def update_categories(self, categories: list[dict[str, Any]], total_count: int) -> None:
        self.category_list.clear()

        all_item = QListWidgetItem(f"All Scripts ({total_count})")
        all_item.setData(100, "All")
        self.category_list.addItem(all_item)

        if self._current_category == "All":
            all_item.setSelected(True)

        for cat in categories:
            name = cat["category"]
            count = cat["count"]
            item = QListWidgetItem(f"{name} ({count})")
            item.setData(100, name)
            self.category_list.addItem(item)
            if self._current_category == name:
                item.setSelected(True)

    def _on_category_clicked(self, item: QListWidgetItem) -> None:
        category = item.data(100) or "All"
        self._current_category = category
        self._on_filter_changed()

    def _on_filter_changed(self) -> None:
        category = self._current_category
        search = self.search_input.text()
        risk = self.risk_combo.currentText()
        if risk == "All Risks":
            risk = "All"
        edition = self.edition_combo.currentText()
        if edition == "All Editions":
            edition = "All"
        self.filter_changed.emit(category, search, risk, edition)
