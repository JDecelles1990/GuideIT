"""Dark-only visual theme, color tokens, and QSS stylesheet for GuideIT."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

BG_WINDOW = "#0F141B"
BG_SURFACE = "#161D27"
BG_ELEVATED = "#1E2736"
BG_CODE = "#0B0F14"
BG_HOVER = "#243044"
BORDER = "#2A3547"
BORDER_ACTIVE = "#38BDF8"

TEXT_PRIMARY = "#E6EDF3"
TEXT_MUTED = "#93A4B8"
TEXT_DIM = "#6E8096"

ACCENT = "#38BDF8"
ACCENT_HOVER = "#56CCF9"
ACCENT_BG = "#112A3E"

REMEDIATION_BG = "#2A1A12"
REMEDIATION_BORDER = "#F59E0B"
REMEDIATION_TEXT = "#FBBF24"

SUCCESS_BG = "#0F2922"
SUCCESS_BORDER = "#10B981"
SUCCESS_TEXT = "#34D399"

ERROR_BG = "#2D1518"
ERROR_BORDER = "#EF4444"
ERROR_TEXT = "#F87171"

TIER_COLORS: dict[str, tuple[str, str, str]] = {
    "L1": ("#0F2922", "#10B981", "#34D399"),
    "L2": ("#112A3E", "#38BDF8", "#7DD3FC"),
    "L3": ("#211938", "#A78BFA", "#C4B5FD"),
}

RISK_COLORS: dict[str, tuple[str, str, str]] = {
    "low": ("#0F2922", "#10B981", "#34D399"),
    "medium": ("#2A2111", "#F59E0B", "#FBBF24"),
    "high": ("#2D1518", "#EF4444", "#F87171"),
}

SECTION_ACCENTS: dict[str, tuple[str, str, str]] = {
    "triage": ("#38BDF8", "#112A3E", "TRIAGE"),
    "diagnostics": ("#10B981", "#0F2922", "READ-ONLY"),
    "deep_dive": ("#A78BFA", "#211938", "L3 DEEP-DIVE"),
    "remediation": ("#F59E0B", "#2A1A12", "CONFIRM BEFORE RUNNING"),
    "verification": ("#34D399", "#0F2922", "VERIFICATION"),
    "pivots": ("#22D3EE", "#0E2A35", "PIVOT MATRIX"),
    "links": ("#38BDF8", "#112A3E", "TOOLS & LINKS"),
    "client_snippets": ("#60A5FA", "#132238", "CLIENT UPDATES"),
    "linked_scripts": ("#8B5CF6", "#211938", "POWERSHELLSTORE"),
    "other": ("#64748B", "#1E2736", "NOTES"),
}


DARK_QSS = f"""
QWidget {{
    background-color: {BG_WINDOW};
    color: {TEXT_PRIMARY};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {BG_WINDOW};
}}

QFrame#topBar {{
    background-color: {BG_SURFACE};
    border-bottom: 1px solid {BORDER};
}}

QFrame#expansionBar {{
    background-color: #121B28;
    border-bottom: 1px solid {BORDER};
}}

QFrame#filterSidebar, QFrame#resultsPane, QFrame#viewerPane {{
    background-color: {BG_WINDOW};
}}

QFrame#filterSidebar {{
    border-right: 1px solid {BORDER};
}}

QFrame#resultsPane {{
    border-right: 1px solid {BORDER};
}}

QFrame#headerCard, QFrame#sectionCard, QFrame#snippetCard, QFrame#emptyStateCard {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QFrame#linkedScriptsSectionCard {{
    background-color: #141827;
    border: 1px solid #6D28D9;
    border-radius: 8px;
}}

QFrame#linkedScriptCard {{
    background-color: #0E1525;
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QPushButton#linkedScriptPill {{
    background-color: #211938;
    color: #DDD6FE;
    border: 1px solid #6D28D9;
    border-radius: 12px;
    padding: 3px 10px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#linkedScriptPill:hover {{
    background-color: #2E224F;
    border-color: #A78BFA;
    color: #FFFFFF;
}}

QPushButton#readOnlyBundleButton {{
    background-color: #0F2922;
    color: #34D399;
    border: 1px solid #10B981;
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#readOnlyBundleButton:hover {{
    background-color: #133A2E;
    border-color: #34D399;
    color: #FFFFFF;
}}

QPushButton#readOnlyBatchButton {{
    background-color: #112A3E;
    color: #38BDF8;
    border: 1px solid #1E5D82;
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#readOnlyBatchButton:hover {{
    background-color: #163954;
    border-color: #38BDF8;
    color: #FFFFFF;
}}

QFrame#favoritesStrip {{
    background-color: #111824;
    border-bottom: 1px solid {BORDER};
}}

QPushButton#pinButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#pinButton:hover {{
    background-color: #2A2111;
    border-color: #F59E0B;
    color: #FDE68A;
}}

QPushButton#pinButton[pinned="true"] {{
    background-color: #2A2111;
    color: #FBBF24;
    border: 1px solid #F59E0B;
}}

QPushButton#favoritePill {{
    background-color: #2A2111;
    color: #FBBF24;
    border: 1px solid #B45309;
    border-radius: 11px;
    padding: 2px 9px;
    font-size: 11.5px;
    font-weight: 600;
}}

QPushButton#favoritePill:hover {{
    background-color: #3B2D14;
    border-color: #F59E0B;
    color: #FFFFFF;
}}

QPushButton#recentPill {{
    background-color: {BG_ELEVATED};
    color: #CBD5E1;
    border: 1px solid {BORDER};
    border-radius: 11px;
    padding: 2px 9px;
    font-size: 11.5px;
    font-weight: 500;
}}

QPushButton#recentPill:hover {{
    background-color: {ACCENT_BG};
    border-color: {ACCENT};
    color: #FFFFFF;
}}

QPushButton#stripToggleButton {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 2px 8px;
    font-size: 11.5px;
    font-weight: 600;
}}

QPushButton#stripToggleButton:hover {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border-color: {ACCENT};
}}

QFrame#remediationSectionCard {{
    background-color: #1B1715;
    border: 1px solid {REMEDIATION_BORDER};
    border-radius: 8px;
}}

QFrame#codeCard {{
    background-color: {BG_CODE};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}

QFrame#remediationCodeCard {{
    background-color: {BG_CODE};
    border: 1px solid {REMEDIATION_BORDER};
    border-radius: 6px;
}}

QFrame#codeHeader {{
    background-color: #131922;
    border-bottom: 1px solid {BORDER};
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}

QFrame#remediationCodeHeader {{
    background-color: {REMEDIATION_BG};
    border-bottom: 1px solid {REMEDIATION_BORDER};
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}}

QLineEdit#searchInput {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 14px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    selection-color: #091017;
}}

QLineEdit#searchInput:focus {{
    border: 1px solid {BORDER_ACTIVE};
    background-color: #212C3D;
}}

QComboBox {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
}}

QComboBox:hover {{
    border-color: #3D4E68;
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT_BG};
    selection-color: {ACCENT};
    outline: 0;
}}

QListWidget {{
    background-color: transparent;
    border: none;
    outline: 0;
}}

QListWidget#domainList::item {{
    padding: 6px 10px;
    border-radius: 5px;
    margin: 1px 0px;
    color: {TEXT_MUTED};
}}

QListWidget#domainList::item:hover {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
}}

QListWidget#domainList::item:selected {{
    background-color: {ACCENT_BG};
    color: {ACCENT};
    font-weight: 600;
}}

QTreeWidget#domainTree {{
    background-color: transparent;
    border: none;
    outline: 0;
    show-decoration-selected: 1;
}}

QTreeWidget#domainTree::item {{
    padding: 4px 6px;
    border-radius: 5px;
    margin: 1px 0px;
    color: {TEXT_MUTED};
}}

QTreeWidget#domainTree::item:hover {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
}}

QTreeWidget#domainTree::item:selected {{
    background-color: {ACCENT_BG};
    color: {ACCENT};
    font-weight: 600;
}}

QListWidget#resultsWidget::item {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
}}

QListWidget#resultsWidget::item:hover {{
    border-color: #3D4E68;
    background-color: #1A222E;
}}

QListWidget#resultsWidget::item:selected {{
    border: 1px solid {ACCENT};
    background-color: #162231;
}}

QPushButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: #3D4E68;
}}

QPushButton:disabled {{
    color: {TEXT_DIM};
    background-color: #141A23;
    border-color: #202937;
}}

QPushButton#accentButton {{
    background-color: {ACCENT_BG};
    color: {ACCENT};
    border: 1px solid #1E5D82;
    font-weight: 600;
}}

QPushButton#accentButton:hover {{
    background-color: #163954;
    border-color: {ACCENT};
}}

QPushButton#tierPill {{
    padding: 5px 8px;
    font-weight: 600;
    color: {TEXT_MUTED};
    background-color: {BG_SURFACE};
}}

QPushButton#tierPill:checked {{
    background-color: {ACCENT_BG};
    color: {ACCENT};
    border-color: {ACCENT};
}}

QPushButton#copyButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#copyButton:hover {{
    background-color: {ACCENT_BG};
    color: {ACCENT};
    border-color: {ACCENT};
}}

QPushButton#remediationCopyButton {{
    background-color: #3B2313;
    color: {REMEDIATION_TEXT};
    border: 1px solid {REMEDIATION_BORDER};
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#remediationCopyButton:hover {{
    background-color: #4E2D18;
}}

QPushButton#relatedPill {{
    background-color: {ACCENT_BG};
    color: {ACCENT};
    border: 1px solid #1E5D82;
    border-radius: 12px;
    padding: 3px 10px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#relatedPill:hover {{
    background-color: #173B57;
    border-color: {ACCENT};
}}

QPushButton#codeChip {{
    background-color: {BG_ELEVATED};
    color: #FDE68A;
    border: 1px solid #3A475D;
    border-radius: 4px;
    padding: 2px 8px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
}}

QPushButton#codeChip:hover {{
    border-color: {ACCENT};
    color: {TEXT_PRIMARY};
}}

QPushButton#healthPill[status="ok"] {{
    background-color: {SUCCESS_BG};
    color: {SUCCESS_TEXT};
    border: 1px solid {SUCCESS_BORDER};
    border-radius: 13px;
    padding: 4px 11px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#healthPill[status="warn"] {{
    background-color: {REMEDIATION_BG};
    color: {REMEDIATION_TEXT};
    border: 1px solid {REMEDIATION_BORDER};
    border-radius: 13px;
    padding: 4px 11px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#healthPill[status="err"] {{
    background-color: {ERROR_BG};
    color: {ERROR_TEXT};
    border: 1px solid {ERROR_BORDER};
    border-radius: 13px;
    padding: 4px 11px;
    font-size: 12px;
    font-weight: 600;
}}

QPushButton#healthPill[status="unknown"] {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
    border: 1px solid {BORDER};
    border-radius: 13px;
    padding: 4px 11px;
    font-size: 12px;
}}

QPlainTextEdit#codeEditor {{
    background-color: {BG_CODE};
    color: {TEXT_PRIMARY};
    border: none;
    padding: 8px 10px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12.5px;
    selection-background-color: #1F4E78;
}}

QPlainTextEdit#reportLog {{
    background-color: {BG_CODE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 8px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
}}

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QSplitter::handle {{
    background-color: {BORDER};
    width: 2px;
}}

QSplitter::handle:hover {{
    background-color: {ACCENT};
}}

QScrollBar:vertical {{
    background-color: {BG_WINDOW};
    width: 10px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background-color: #303D52;
    border-radius: 5px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: #445673;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {BG_CODE};
    height: 10px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background-color: #303D52;
    border-radius: 5px;
    min-width: 24px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: #445673;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
    width: 0px;
}}

QStatusBar {{
    background-color: {BG_SURFACE};
    color: {TEXT_MUTED};
    border-top: 1px solid {BORDER};
    font-size: 12px;
}}

QToolTip {{
    background-color: {BG_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_ACTIVE};
    padding: 4px 8px;
}}
"""


def apply_dark_theme(app: QApplication) -> None:
    """Apply Fusion dark QPalette and GuideIT Dark QSS stylesheet."""
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG_WINDOW))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(BG_SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(BG_ELEVATED))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT_BG))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(ACCENT))
    app.setPalette(palette)
    app.setStyleSheet(DARK_QSS)
