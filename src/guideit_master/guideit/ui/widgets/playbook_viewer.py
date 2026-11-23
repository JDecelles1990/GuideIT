"""Right-pane interactive playbook viewer with section cards, code copy, and EN/FR snippets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from guideit_master.guideit.frontmatter import extract_sections
from guideit_master.guideit.ui.markdown_blocks import (
    CodeBlock,
    ParsedSection,
    ProseBlock,
    parse_section_blocks,
)
from guideit_master.guideit.ui.theme import (
    ACCENT,
    ACCENT_BG,
    BG_ELEVATED,
    BORDER,
    REMEDIATION_TEXT,
    RISK_COLORS,
    SECTION_ACCENTS,
    TEXT_DIM,
    TEXT_MUTED,
    TIER_COLORS,
)
from guideit_master.guideit.ui.widgets.code_block import CodeBlockWidget


class _FlowLayout(QLayout):
    """Wrapping horizontal flow layout for badges, error codes, and related pills."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items = []
        self._spacing = spacing

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + self._spacing
                next_x = x + hint.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())

        return y + line_height - rect.y() + margins.bottom()


def _attach_copy_feedback(button: QPushButton, default_text: str) -> QTimer:
    """Attach a child single-shot QTimer to reset button label safely after copy."""
    timer = QTimer(button)
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: button.setText(default_text))
    return timer


def _pill_label(text: str, bg: str, border: str, fg: str, parent: QWidget) -> QLabel:
    lbl = QLabel(text, parent)
    lbl.setStyleSheet(
        f"background-color: {bg}; color: {fg}; border: 1px solid {border}; "
        "border-radius: 4px; padding: 2px 8px; font-size: 11px; font-weight: 700;"
    )
    return lbl


class PlaybookViewer(QFrame):
    """Scrollable L1–L3 playbook viewer with one-click command and client-update copy."""

    related_playbook_clicked = Signal(str)
    back_requested = Signal()
    status_message = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("viewerPane")

        self.current_playbook_id: str | None = None
        self.current_record: dict[str, object] | None = None
        self.code_widgets: list[CodeBlockWidget] = []
        self.related_buttons: dict[str, QPushButton] = {}
        self.error_code_buttons: dict[str, QPushButton] = {}
        self.copy_en_button: QPushButton | None = None
        self.copy_fr_button: QPushButton | None = None
        self.back_button: QPushButton | None = None
        self._root_dir: Path | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.viewport().setStyleSheet("background: transparent;")
        outer.addWidget(self.scroll_area)

        self.clear_view()

    def set_back_enabled(self, enabled: bool) -> None:
        if self.back_button is not None:
            self.back_button.setEnabled(enabled)

    def clear_view(
        self,
        message: str = "Select a playbook from the results pane to inspect L1–L3 diagnostics.",
    ) -> None:
        """Reset viewer state to a dark placeholder card."""
        self.current_playbook_id = None
        self.current_record = None
        self.code_widgets.clear()
        self.related_buttons.clear()
        self.error_code_buttons.clear()
        self.copy_en_button = None
        self.copy_fr_button = None
        self.back_button = None

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)

        card = QFrame(container)
        card.setObjectName("emptyStateCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        lbl = QLabel(message, card)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 14px; background: transparent;")
        card_layout.addWidget(lbl)
        layout.addWidget(card)
        layout.addStretch(1)

        self.scroll_area.setWidget(container)

    def display_playbook(
        self,
        record: dict[str, object],
        *,
        root_dir: Path,
        can_go_back: bool = False,
        titles_by_id: dict[str, str] | None = None,
        subcategory_label: str = "",
    ) -> None:
        """Render full metadata header, L1-L3 sections, code blocks, and EN/FR snippets."""
        self._root_dir = root_dir
        self.current_record = record
        self.current_playbook_id = str(record["id"])
        self.code_widgets.clear()
        self.related_buttons.clear()
        self.error_code_buttons.clear()
        self.copy_en_button = None
        self.copy_fr_button = None

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(18, 16, 18, 22)
        root_layout.setSpacing(14)

        root_layout.addWidget(
            self._build_header_card(
                record,
                can_go_back=can_go_back,
                titles_by_id=titles_by_id or {},
                subcategory_label=subcategory_label,
            )
        )

        body_markdown = str(record.get("body_markdown", ""))
        order, sections = extract_sections(body_markdown)
        for heading in order:
            parsed = parse_section_blocks(heading, sections[heading])
            root_layout.addWidget(self._build_section_card(parsed))

        root_layout.addStretch(1)
        self.scroll_area.setWidget(container)
        self.scroll_area.verticalScrollBar().setValue(0)

    def _build_header_card(
        self,
        record: dict[str, object],
        *,
        can_go_back: bool,
        titles_by_id: dict[str, str],
        subcategory_label: str,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("headerCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Top action row
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.back_button = QPushButton("← Back", card)
        self.back_button.setEnabled(can_go_back)
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setToolTip("Return to previous playbook (Alt+Left)")
        self.back_button.setStyleSheet("padding: 4px 10px; font-size: 12px;")
        self.back_button.clicked.connect(self.back_requested.emit)
        top_row.addWidget(self.back_button)

        pb_id = str(record["id"])
        id_lbl = QLabel(f"[{pb_id}]", card)
        id_lbl.setStyleSheet(
            f"background-color: {ACCENT_BG}; color: {ACCENT}; border: 1px solid #1E5D82; "
            "border-radius: 5px; padding: 3px 9px; "
            "font-family: 'Cascadia Mono', 'Consolas', monospace; font-size: 12px; font-weight: 700;"
        )
        top_row.addWidget(id_lbl)

        subject_text = str(record.get("subject", ""))
        if subcategory_label:
            subject_text = f"{subject_text}  ›  {subcategory_label}"
        subject_lbl = QLabel(subject_text, card)
        subject_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; background: transparent;"
        )
        top_row.addWidget(subject_lbl)

        top_row.addStretch(1)

        verified_lbl = QLabel(f"Verified {record.get('last_verified', '')}", card)
        verified_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 12px; background: transparent;")
        top_row.addWidget(verified_lbl)

        rel_path = str(record.get("path", ""))
        copy_path_btn = QPushButton("Copy Path", card)
        copy_path_btn.setObjectName("copyButton")
        copy_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        path_timer = _attach_copy_feedback(copy_path_btn, "Copy Path")
        copy_path_btn.clicked.connect(
            lambda: self._copy_text(rel_path, copy_path_btn, path_timer, f"Copied path: {rel_path}")
        )
        top_row.addWidget(copy_path_btn)

        open_btn = QPushButton("Open .md", card)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet("padding: 3px 10px; font-size: 12px;")
        open_btn.clicked.connect(lambda: self._open_markdown_file(rel_path))
        top_row.addWidget(open_btn)

        layout.addLayout(top_row)

        # Title
        title_lbl = QLabel(str(record.get("title", "")), card)
        title_lbl.setWordWrap(True)
        title_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        title_lbl.setStyleSheet(
            "font-size: 19px; font-weight: 700; color: #F8FAFC; background: transparent;"
        )
        layout.addWidget(title_lbl)

        # Badges row
        badges_wrap = QWidget(card)
        badges_wrap.setStyleSheet("background: transparent;")
        badges_flow = _FlowLayout(badges_wrap, spacing=6)

        tier = str(record.get("tier", ""))
        t_bg, t_border, t_fg = TIER_COLORS.get(tier, (BG_ELEVATED, BORDER, "#E6EDF3"))
        badges_flow.addWidget(_pill_label(f"Tier {tier}", t_bg, t_border, t_fg, badges_wrap))

        risk = str(record.get("risk_level", ""))
        r_bg, r_border, r_fg = RISK_COLORS.get(risk, (BG_ELEVATED, BORDER, "#E6EDF3"))
        badges_flow.addWidget(_pill_label(f"Risk: {risk.upper()}", r_bg, r_border, r_fg, badges_wrap))

        if record.get("requires_admin"):
            badges_flow.addWidget(
                _pill_label("Requires Admin", "#251E35", "#6D28D9", "#DDD6FE", badges_wrap)
            )
        else:
            badges_flow.addWidget(
                _pill_label("Standard User Safe", "#132238", "#2563EB", "#93C5FD", badges_wrap)
            )

        for os_name in record.get("os", []):
            badges_flow.addWidget(
                _pill_label(f"OS: {os_name}", BG_ELEVATED, BORDER, "#CBD5E1", badges_wrap)
            )
        for env_name in record.get("environment", []):
            badges_flow.addWidget(
                _pill_label(env_name, BG_ELEVATED, BORDER, TEXT_MUTED, badges_wrap)
            )

        layout.addWidget(badges_wrap)

        # Error codes & related playbooks
        error_codes = [str(c) for c in record.get("error_codes", [])]
        if error_codes:
            codes_row = QWidget(card)
            codes_row.setStyleSheet("background: transparent;")
            codes_flow = _FlowLayout(codes_row, spacing=6)
            codes_lbl = QLabel("Error Codes (click to copy):", codes_row)
            codes_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; background: transparent;"
            )
            codes_flow.addWidget(codes_lbl)
            for code in error_codes:
                btn = QPushButton(code, codes_row)
                btn.setObjectName("codeChip")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                timer = _attach_copy_feedback(btn, code)
                btn.clicked.connect(
                    lambda _checked=False, c=code, b=btn, t=timer: self._copy_text(
                        c, b, t, f"Copied error code: {c}"
                    )
                )
                self.error_code_buttons[code] = btn
                codes_flow.addWidget(btn)
            layout.addWidget(codes_row)

        related_ids = [str(r) for r in record.get("related_ids", [])]
        if related_ids:
            rel_row = QWidget(card)
            rel_row.setStyleSheet("background: transparent;")
            rel_flow = _FlowLayout(rel_row, spacing=6)
            rel_lbl = QLabel("Related Playbooks:", rel_row)
            rel_lbl.setStyleSheet(
                f"color: {TEXT_MUTED}; font-size: 12px; font-weight: 600; background: transparent;"
            )
            rel_flow.addWidget(rel_lbl)
            for rel_id in related_ids:
                btn = QPushButton(f"[{rel_id}]", rel_row)
                btn.setObjectName("relatedPill")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                if rel_id in titles_by_id:
                    btn.setToolTip(f"[{rel_id}] {titles_by_id[rel_id]}")
                btn.clicked.connect(
                    lambda _checked=False, target=rel_id: self.related_playbook_clicked.emit(target)
                )
                self.related_buttons[rel_id] = btn
                rel_flow.addWidget(btn)
            layout.addWidget(rel_row)

        # Tools & Bilingual keywords summary
        tools = ", ".join(str(t) for t in record.get("tools", []))
        kw_en = ", ".join(str(k) for k in record.get("keywords_en", []))
        kw_fr = ", ".join(str(k) for k in record.get("keywords_fr", []))
        meta_lbl = QLabel(
            f"<b>Tools:</b> {tools}<br>"
            f"<b>Keywords (EN):</b> {kw_en}<br>"
            f"<b>Mots-clés (FR):</b> {kw_fr}",
            card,
        )
        meta_lbl.setWordWrap(True)
        meta_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meta_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 12px; line-height: 1.4; background: transparent;"
        )
        layout.addWidget(meta_lbl)

        return card

    def _build_section_card(self, section: ParsedSection) -> QFrame:
        is_remediation = section.category == "remediation"
        card = QFrame()
        card.setObjectName("remediationSectionCard" if is_remediation else "sectionCard")

        accent_color, pill_bg, pill_label = SECTION_ACCENTS.get(
            section.category, SECTION_ACCENTS["other"]
        )

        outer = QHBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        stripe = QFrame(card)
        stripe.setFixedWidth(4)
        stripe.setStyleSheet(
            f"background-color: {accent_color}; border-top-left-radius: 7px; border-bottom-left-radius: 7px;"
        )
        outer.addWidget(stripe)

        body_widget = QWidget(card)
        body_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(body_widget)
        layout.setContentsMargins(16, 13, 16, 14)
        layout.setSpacing(10)

        # Heading row
        head_row = QHBoxLayout()
        head_row.setSpacing(8)
        heading_lbl = QLabel(section.heading, body_widget)
        heading_lbl.setStyleSheet(
            "font-size: 15px; font-weight: 700; color: #F0F6FC; background: transparent;"
        )
        head_row.addWidget(heading_lbl)

        head_row.addWidget(_pill_label(pill_label, pill_bg, accent_color, accent_color, body_widget))
        head_row.addStretch(1)
        layout.addLayout(head_row)

        if is_remediation:
            banner = QLabel(
                "⚠ REMEDIATION — CONFIRM BEFORE RUNNING: Verify scope, prerequisites, and blast radius "
                "before running any state-changing command below.",
                body_widget,
            )
            banner.setWordWrap(True)
            banner.setStyleSheet(
                f"background-color: #2A1A12; color: {REMEDIATION_TEXT}; "
                "border: 1px solid #B45309; border-radius: 6px; padding: 8px 10px; "
                "font-size: 12px; font-weight: 600;"
            )
            layout.addWidget(banner)

        if section.category == "client_snippets" and section.snippets is not None:
            if section.snippets.en:
                card_en, btn_en = self._build_snippet_box(
                    "English Client Update (EN)", section.snippets.en, "Copy EN Update"
                )
                self.copy_en_button = btn_en
                layout.addWidget(card_en)
            if section.snippets.fr:
                card_fr, btn_fr = self._build_snippet_box(
                    "Mise à jour client (FR)", section.snippets.fr, "Copy FR Update"
                )
                self.copy_fr_button = btn_fr
                layout.addWidget(card_fr)
        else:
            for block in section.blocks:
                if isinstance(block, ProseBlock):
                    prose = QLabel(block.html, body_widget)
                    prose.setWordWrap(True)
                    prose.setOpenExternalLinks(False)
                    prose.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
                    prose.linkActivated.connect(self._handle_link)
                    prose.setStyleSheet("background: transparent; color: #DCE4EE; font-size: 13px;")
                    layout.addWidget(prose)
                elif isinstance(block, CodeBlock):
                    cw = CodeBlockWidget(
                        block.language,
                        block.code,
                        is_remediation=block.is_remediation,
                        parent=body_widget,
                    )
                    cw.copied.connect(self.status_message.emit)
                    self.code_widgets.append(cw)
                    layout.addWidget(cw)

        outer.addWidget(body_widget, stretch=1)
        return card

    def _build_snippet_box(
        self,
        title: str,
        text: str,
        button_label: str,
    ) -> tuple[QFrame, QPushButton]:
        box = QFrame()
        box.setObjectName("snippetCard")
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        box.setStyleSheet(
            f"QFrame#snippetCard {{ background-color: #111822; border: 1px solid {BORDER}; border-radius: 6px; }}"
        )
        vbox = QVBoxLayout(box)
        vbox.setContentsMargins(12, 10, 12, 10)
        vbox.setSpacing(6)

        row = QHBoxLayout()
        lbl = QLabel(title, box)
        lbl.setStyleSheet(f"color: {ACCENT}; font-size: 12px; font-weight: 700; background: transparent;")
        row.addWidget(lbl)
        row.addStretch(1)

        btn = QPushButton(button_label, box)
        btn.setObjectName("copyButton")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        timer = _attach_copy_feedback(btn, button_label)
        btn.clicked.connect(
            lambda _checked=False, s=text, b=btn, t=timer, cap=title: self._copy_text(
                s, b, t, f"Copied {cap} to clipboard."
            )
        )
        row.addWidget(btn)
        vbox.addLayout(row)

        body = QLabel(text, box)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet("color: #E6EDF3; font-size: 13px; line-height: 1.45; background: transparent;")
        vbox.addWidget(body)
        return box, btn

    def _copy_text(
        self,
        text: str,
        button: QPushButton,
        timer: QTimer,
        status: str,
    ) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
        button.setText("Copied ✓")
        timer.start(1500)
        self.status_message.emit(status)

    def _open_markdown_file(self, rel_path: str) -> None:
        if self._root_dir is None or not rel_path:
            return
        full_path = (self._root_dir / rel_path).resolve()
        if full_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(full_path)))
            self.status_message.emit(f"Opened {rel_path}")

    def _handle_link(self, url: str) -> None:
        if url.startswith("guideit://"):
            target_id = url.removeprefix("guideit://").strip()
            if target_id:
                self.related_playbook_clicked.emit(target_id)
            return
        QDesktopServices.openUrl(QUrl(url))
