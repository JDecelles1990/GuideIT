"""Searchable dark dialog listing curated MSP websites, lookup tools, and usage instructions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from guideit_master.guideit.taxonomy import load_resources
from guideit_master.guideit.ui.theme import ACCENT, ACCENT_BG, TEXT_DIM, TEXT_MUTED


class ResourcesDialog(QDialog):
    """Dark searchable modal of essential IT troubleshooting websites and instructions."""

    def __init__(self, root_dir: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.root_dir = root_dir
        self.setWindowTitle("GuideIT — Useful Websites & External Tools (Ctrl+T)")
        self.resize(900, 680)
        self.setMinimumSize(720, 500)

        self._resources: list[dict[str, object]] = load_resources(self.root_dir)
        self.copy_buttons: dict[str, QPushButton] = {}
        self.open_buttons: dict[str, QPushButton] = {}
        self._visible_names: list[str] = []

        self._build_ui()
        self._render_cards()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        intro = QLabel(
            "Curated MSP & Data Center websites (MXToolbox, VirusTotal, Subnet Calculators, "
            "Microsoft/Windows Licensing, Google Workspace, Adobe). Filter in EN or FR:",
            self,
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12.5px;")
        layout.addWidget(intro)

        # Filter bar
        bar = QHBoxLayout()
        bar.setSpacing(10)

        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("searchInput")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setPlaceholderText(
            "Filter tools (e.g., MXToolbox, VirusTotal, Subnet, Adobe, KMS, DisplayLink)..."
        )
        self.search_input.textChanged.connect(lambda _txt: self._render_cards())
        bar.addWidget(self.search_input, stretch=1)

        self.category_combo = QComboBox(self)
        self.category_combo.addItem("All Categories", None)
        categories = sorted({str(r.get("category", "")) for r in self._resources if r.get("category")})
        for cat in categories:
            self.category_combo.addItem(cat, cat)
        self.category_combo.currentIndexChanged.connect(lambda _idx: self._render_cards())
        bar.addWidget(self.category_combo)

        layout.addLayout(bar)

        self.count_label = QLabel("", self)
        self.count_label.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; font-weight: 600;")
        layout.addWidget(self.count_label)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(self.scroll_area, stretch=1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close_btn = QPushButton("Close", self)
        close_btn.setObjectName("accentButton")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        bottom.addWidget(close_btn)
        layout.addLayout(bottom)

    def _matches(self, res: dict[str, object], query: str, cat_filter: str | None) -> bool:
        if cat_filter and str(res.get("category", "")) != cat_filter:
            return False
        if not query:
            return True
        haystack = " ".join(
            [
                str(res.get("name", "")),
                str(res.get("category", "")),
                str(res.get("url", "")),
                str(res.get("when_to_use", "")),
                str(res.get("instructions", "")),
                " ".join(str(t) for t in res.get("tags", [])),
            ]
        ).lower()
        return all(tok in haystack for tok in query.split())

    def _render_cards(self) -> None:
        query = self.search_input.text().strip().lower()
        cat_filter = self.category_combo.currentData()

        filtered = [r for r in self._resources if self._matches(r, query, cat_filter)]
        self._visible_names = [str(r.get("name", "")) for r in filtered]
        self.copy_buttons.clear()
        self.open_buttons.clear()

        noun = "tool" if len(filtered) == 1 else "tools"
        self.count_label.setText(f"Showing {len(filtered)} {noun}")

        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(2, 2, 8, 8)
        vbox.setSpacing(10)

        if not filtered:
            empty = QFrame(container)
            empty.setObjectName("emptyStateCard")
            el = QVBoxLayout(empty)
            el.setContentsMargins(16, 16, 16, 16)
            lbl = QLabel("No matching external tools or websites found.", empty)
            lbl.setStyleSheet(f"color: {TEXT_MUTED};")
            el.addWidget(lbl)
            vbox.addWidget(empty)
        else:
            for res in filtered:
                vbox.addWidget(self._build_card(res, container))

        vbox.addStretch(1)
        self.scroll_area.setWidget(container)

    def _build_card(self, res: dict[str, object], parent: QWidget) -> QFrame:
        name = str(res.get("name", ""))
        category = str(res.get("category", ""))
        url = str(res.get("url", ""))
        when_to_use = str(res.get("when_to_use", ""))
        instructions = str(res.get("instructions", ""))

        card = QFrame(parent)
        card.setObjectName("sectionCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        title_lbl = QLabel(name, card)
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #F8FAFC; background: transparent;")
        top.addWidget(title_lbl)

        cat_lbl = QLabel(category, card)
        cat_lbl.setStyleSheet(
            f"background-color: {ACCENT_BG}; color: {ACCENT}; border: 1px solid #1E5D82; "
            "border-radius: 4px; padding: 1px 7px; font-size: 11px; font-weight: 700;"
        )
        top.addWidget(cat_lbl)
        top.addStretch(1)

        copy_btn = QPushButton("Copy URL", card)
        copy_btn.setObjectName("copyButton")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        timer = QTimer(copy_btn)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda b=copy_btn: b.setText("Copy URL"))
        copy_btn.clicked.connect(
            lambda _checked=False, u=url, b=copy_btn, t=timer: self._copy_url(u, b, t)
        )
        self.copy_buttons[name] = copy_btn
        top.addWidget(copy_btn)

        open_btn = QPushButton("Open ↗", card)
        open_btn.setObjectName("accentButton")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet("padding: 3px 10px; font-size: 12px;")
        open_btn.clicked.connect(lambda _checked=False, u=url: QDesktopServices.openUrl(QUrl(u)))
        self.open_buttons[name] = open_btn
        top.addWidget(open_btn)
        lay.addLayout(top)

        url_lbl = QLabel(f'<a href="{url}" style="color:#60A5FA;text-decoration:none;">{url}</a>', card)
        url_lbl.setOpenExternalLinks(True)
        url_lbl.setStyleSheet(
            "font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 11.5px; background: transparent;"
        )
        lay.addWidget(url_lbl)

        when_lbl = QLabel(f"<b>When to use:</b> {when_to_use}", card)
        when_lbl.setWordWrap(True)
        when_lbl.setStyleSheet("color: #DCE4EE; font-size: 12.5px; background: transparent;")
        lay.addWidget(when_lbl)

        inst_lbl = QLabel(f"<b>How to use:</b> {instructions}", card)
        inst_lbl.setWordWrap(True)
        inst_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; background: transparent;")
        lay.addWidget(inst_lbl)

        return card

    def _copy_url(self, url: str, button: QPushButton, timer: QTimer) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(url)
        button.setText("Copied ✓")
        timer.start(1500)

    def visible_resource_names(self) -> list[str]:
        return list(self._visible_names)
