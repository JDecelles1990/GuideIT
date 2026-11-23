"""Syntax-highlighted, one-click copyable command block widget."""

from __future__ import annotations

import math

from PySide6.QtCore import QRegularExpression, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
    QTextOption,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from guideit_master.guideit.ui.theme import REMEDIATION_TEXT, TEXT_MUTED


class CommandSyntaxHighlighter(QSyntaxHighlighter):
    """Lightweight dark syntax highlighter for PowerShell, CMD, and Bash snippets."""

    def __init__(self, parent: QTextDocument) -> None:
        super().__init__(parent)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = []

        def _fmt(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(True)
            return fmt

        cmdlet_fmt = _fmt("#38BDF8", bold=True)
        flag_fmt = _fmt("#C084FC")
        var_fmt = _fmt("#34D399")
        keyword_fmt = _fmt("#60A5FA", bold=True)
        string_fmt = _fmt("#FBBF24")
        comment_fmt = _fmt("#64748B", italic=True)

        # PowerShell Verb-Noun cmdlets and CLI commands
        self._rules.append((QRegularExpression(r"\b[A-Z][a-z]+-[A-Za-z0-9]+\b"), cmdlet_fmt))
        self._rules.append(
            (
                QRegularExpression(
                    r"\b(sudo|profiles|fdesetup|sw_vers|log|dsregcmd|nltest|cmdkey|"
                    r"ipconfig|netsh|vssadmin|sfc|DISM|dotnet|w32tm|msedge\.exe|outlook\.exe)\b"
                ),
                cmdlet_fmt,
            )
        )
        # Keywords / pipeline helpers
        self._rules.append(
            (
                QRegularExpression(
                    r"\b(if|else|foreach|where|Select-Object|Where-Object|Format-Table|Sort-Object|Measure-Object)\b"
                ),
                keyword_fmt,
            )
        )
        # PowerShell / CLI parameters (-FilterHashtable, --last, /Online)
        self._rules.append(
            (QRegularExpression(r"(?<!\w)(?:--?[A-Za-z][A-Za-z0-9_-]*|/[A-Za-z][A-Za-z0-9_-]*)"), flag_fmt)
        )
        # Variables ($pdc, $env:LOCALAPPDATA)
        self._rules.append((QRegularExpression(r"\$[A-Za-z_][A-Za-z0-9_:]*"), var_fmt))
        # Quoted strings
        self._rules.append((QRegularExpression(r'"[^"\n]*"|\'[^\'\n]*\''), string_fmt))
        # Comments (# ...)
        self._rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class CodeBlockWidget(QFrame):
    """Dark command block card with language badge, remediation warning, and Copy button."""

    copied = Signal(str)

    def __init__(
        self,
        language: str,
        code: str,
        *,
        is_remediation: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.language = language or "text"
        self.code_text = code
        self.is_remediation = is_remediation

        self.setObjectName("remediationCodeCard" if is_remediation else "codeCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("remediationCodeHeader" if is_remediation else "codeHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 8, 5)
        header_layout.setSpacing(8)

        lang_label = QLabel(self.language.upper(), header)
        lang_label.setStyleSheet(
            f"background: transparent; color: {TEXT_MUTED}; font-family: 'Cascadia Mono', 'Consolas', monospace; "
            "font-size: 11px; font-weight: 700; letter-spacing: 0.6px;"
        )
        header_layout.addWidget(lang_label)

        if is_remediation:
            warn_label = QLabel("⚠ CONFIRM BEFORE RUNNING", header)
            warn_label.setStyleSheet(
                f"background: transparent; color: {REMEDIATION_TEXT}; font-size: 11px; font-weight: 700;"
            )
            header_layout.addWidget(warn_label)

        header_layout.addStretch(1)

        self.copy_button = QPushButton("Copy", header)
        self.copy_button.setObjectName("remediationCopyButton" if is_remediation else "copyButton")
        self.copy_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_button.setToolTip(f"Copy {self.language.upper()} command to clipboard")
        self.copy_button.clicked.connect(self._copy_code)
        header_layout.addWidget(self.copy_button)

        layout.addWidget(header)

        self.editor = QPlainTextEdit(self)
        self.editor.setObjectName("codeEditor")
        self.editor.setReadOnly(True)
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.document().setDocumentMargin(4)
        self.editor.setPlainText(self.code_text)

        self._highlighter = CommandSyntaxHighlighter(self.editor.document())
        self.editor.document().documentLayout().documentSizeChanged.connect(
            lambda _sz: self._adjust_editor_height()
        )
        self._adjust_editor_height()

        layout.addWidget(self.editor)

        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._reset_button_label)

    def _adjust_editor_height(self) -> None:
        doc = self.editor.document()
        fm = self.editor.fontMetrics()

        layout_lines = 0
        block = doc.begin()
        while block.isValid():
            bl = block.layout()
            layout_lines += max(1, bl.lineCount()) if bl is not None else 1
            block = block.next()

        vp_w = self.editor.viewport().width()
        avail_w = vp_w - 8 if vp_w > 60 else max(240, self.width() - 40)
        est_lines = 0
        for line in self.code_text.splitlines() or [""]:
            w = fm.horizontalAdvance(line) + 4
            est_lines += max(1, math.ceil(w / avail_w))

        visual_lines = max(1, layout_lines, est_lines)
        visible_lines = min(visual_lines, 24)
        if visual_lines <= 24:
            self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        line_h = max(18, fm.lineSpacing())
        cm = self.editor.contentsMargins()
        pad_v = max(16, cm.top() + cm.bottom())
        doc_margin_v = int(doc.documentMargin() * 2)
        target_h = (visible_lines * line_h) + pad_v + doc_margin_v + 6
        if target_h != self.editor.height():
            self.editor.setFixedHeight(target_h)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._adjust_editor_height()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._adjust_editor_height()

    def _copy_code(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.code_text)
        self.copy_button.setText("Copied ✓")
        self._reset_timer.start(1500)
        self.copied.emit(f"Copied {self.language.upper()} command to clipboard.")

    def _reset_button_label(self) -> None:
        self.copy_button.setText("Copy")
