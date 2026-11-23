"""Unified dark frosted-glass QSS theme for GuideIT Master."""

DARK_THEME_QSS = """
/* Global Window and Base Styles */
QWidget {
    color: #f3f4f6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QMainWindow, QDialog, QMessageBox, QMenu {
    background-color: #0b1120;
}

QWidget#CentralBackdrop {
    background-color: transparent;
}

/* Splitter */
QSplitter {
    background-color: transparent;
}
QSplitter::handle {
    background-color: transparent;
    width: 3px;
}
QSplitter::handle:hover {
    background-color: rgba(96, 165, 250, 0.55);
}

/* Frosted Glass Panel Containers (underlit by guideit_master/ui/backdrop_fx.py) */
QFrame#ShellHeaderFrame, QFrame#topBar,
QFrame#filterSidebar, QFrame#resultsPane, QFrame#viewerPane,
QFrame#SidebarFrame, QFrame#InspectorFrame, QFrame#CatalogFrame {
    background-color: rgba(15, 23, 42, 0.58);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 10px;
}

QStatusBar {
    background-color: rgba(9, 14, 28, 0.78);
    color: #cbd5e1;
    border-top: 1px solid rgba(148, 163, 184, 0.18);
}

/* ScrollBars */
QScrollBar:vertical {
    background: rgba(10, 15, 30, 0.45);
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(71, 85, 105, 0.65);
    min-height: 20px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(100, 116, 139, 0.85);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: rgba(10, 15, 30, 0.45);
    height: 10px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background: rgba(71, 85, 105, 0.65);
    min-width: 20px;
    border-radius: 5px;
}

/* Inputs & ComboBoxes */
QLineEdit, QSpinBox, QComboBox {
    background-color: rgba(10, 16, 32, 0.68);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 6px;
    padding: 6px 10px;
    color: #f9fafb;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #3b82f6;
}
QComboBox::drop-down {
    border: 0px;
    width: 24px;
}
QComboBox QAbstractItemView {
    background-color: #162036;
    border: 1px solid rgba(148, 163, 184, 0.28);
    selection-background-color: #2563eb;
    color: #f9fafb;
}

/* Push Buttons — colorful gradient on hover, inverted "pressed-in" gradient on click.
   The animated rainbow glow, shine sweep and click ripple are painted by effects.py. */
QPushButton {
    background-color: #374151;
    color: #f9fafb;
    border: 1px solid #4b5563;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6366f1, stop:0.35 #8b5cf6, stop:0.7 #ec4899, stop:1 #f59e0b);
    border: 1px solid #f0abfc;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: qlineargradient(x1:1, y1:1, x2:0, y2:0,
        stop:0 #4338ca, stop:0.5 #7e22ce, stop:1 #be185d);
    border: 1px solid #ffffff;
    padding-top: 8px;
    padding-bottom: 6px;
}
QPushButton:disabled {
    background-color: #1f2937;
    border: 1px solid #374151;
    color: #6b7280;
}

/* Shell Mode Switcher Pills */
QPushButton#ModeSwitchButton {
    background-color: rgba(30, 41, 59, 0.72);
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 6px;
    padding: 5px 12px;
    color: #cbd5e1;
    font-weight: 600;
    font-size: 12px;
}
QPushButton#ModeSwitchButton:checked {
    background-color: #1d4ed8;
    border: 1px solid #38bdf8;
    color: #ffffff;
}

/* Primary Action Button (Blue -> Cyan -> Violet) */
QPushButton#PrimaryButton {
    background-color: #2563eb;
    border: 1px solid #1d4ed8;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #06b6d4, stop:0.45 #3b82f6, stop:1 #a855f7);
    border: 1px solid #a5f3fc;
}
QPushButton#PrimaryButton:pressed {
    background-color: qlineargradient(x1:1, y1:1, x2:0, y2:0,
        stop:0 #0e7490, stop:0.5 #1d4ed8, stop:1 #7e22ce);
    border: 1px solid #ffffff;
}

/* Success Button (Emerald -> Lime -> Teal) */
QPushButton#SuccessButton {
    background-color: #059669;
    border: 1px solid #047857;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#SuccessButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #10b981, stop:0.5 #84cc16, stop:1 #14b8a6);
    border: 1px solid #bbf7d0;
}
QPushButton#SuccessButton:pressed {
    background-color: qlineargradient(x1:1, y1:1, x2:0, y2:0,
        stop:0 #047857, stop:0.5 #4d7c0f, stop:1 #0f766e);
    border: 1px solid #ffffff;
}

/* Danger / Stop Button (Red -> Orange -> Magenta) */
QPushButton#DangerButton {
    background-color: #dc2626;
    border: 1px solid #b91c1c;
    color: #ffffff;
    font-weight: 600;
}
QPushButton#DangerButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ef4444, stop:0.5 #f97316, stop:1 #db2777);
    border: 1px solid #fecaca;
}
QPushButton#DangerButton:pressed {
    background-color: qlineargradient(x1:1, y1:1, x2:0, y2:0,
        stop:0 #991b1b, stop:0.5 #c2410c, stop:1 #9d174d);
    border: 1px solid #ffffff;
}
QPushButton#PrimaryButton:disabled, QPushButton#SuccessButton:disabled, QPushButton#DangerButton:disabled {
    background-color: #1f2937;
    border: 1px solid #374151;
    color: #6b7280;
}

/* Report Action Buttons (Dark Slate -> Aurora gradient on hover) */
QPushButton#ReportButton {
    background-color: #1f2937;
    border: 1px solid #374151;
    color: #e5e7eb;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 4px;
    font-weight: 500;
}
QPushButton#ReportButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b82f6, stop:0.5 #8b5cf6, stop:1 #ec4899);
    border: 1px solid #c4b5fd;
    color: #ffffff;
}
QPushButton#ReportButton:pressed {
    background-color: qlineargradient(x1:1, y1:0, x2:0, y2:0,
        stop:0 #1d4ed8, stop:0.5 #6d28d9, stop:1 #be185d);
    border: 1px solid #ffffff;
}
QPushButton#ReportButton:disabled {
    background-color: #111827;
    border-color: #1f2937;
    color: #4b5563;
}

/* Tables and Lists */
QTableWidget, QListWidget {
    background-color: rgba(9, 14, 28, 0.56);
    border: 1px solid rgba(148, 163, 184, 0.20);
    border-radius: 6px;
    gridline-color: rgba(51, 65, 85, 0.35);
    outline: none;
}
QTableWidget::item, QListWidget::item {
    padding: 8px;
    border-bottom: 1px solid rgba(51, 65, 85, 0.32);
}
QTableWidget::item:selected, QListWidget::item:selected {
    background-color: rgba(37, 99, 235, 0.55);
    color: #ffffff;
}
QHeaderView::section {
    background-color: rgba(20, 30, 54, 0.68);
    color: #cbd5e1;
    border: 0px;
    border-bottom: 1px solid rgba(148, 163, 184, 0.22);
    padding: 8px;
    font-weight: 600;
}
QHeaderView::section:hover {
    background-color: rgba(37, 99, 235, 0.34);
    color: #ffffff;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background-color: rgba(11, 17, 34, 0.54);
    border-radius: 6px;
}
QTabBar::tab {
    background-color: rgba(22, 32, 56, 0.62);
    color: #9ca3af;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: rgba(11, 17, 34, 0.78);
    color: #7dd3fc;
    border-bottom: 2px solid #38bdf8;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    background-color: rgba(51, 65, 85, 0.68);
    color: #f3f4f6;
}

/* Code and Console Text Edit */
QPlainTextEdit#ConsoleView, QPlainTextEdit#CodePreview {
    background-color: rgba(3, 7, 18, 0.72);
    border: 1px solid rgba(148, 163, 184, 0.20);
    border-radius: 6px;
    color: #e5e7eb;
    font-family: Consolas, "Cascadia Code", "Courier New", monospace;
    font-size: 12px;
    line-height: 1.4;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #f3f4f6;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #4b5563;
    background-color: #111827;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border: 1px solid #3b82f6;
}
QTableWidget::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #4b5563;
    background-color: #111827;
}
QTableWidget::indicator:hover {
    border: 1px solid #60a5fa;
}
QTableWidget::indicator:checked {
    background-color: #2563eb;
    border: 2px solid #93c5fd;
}

/* Badges and Labels */
QLabel#HeaderTitle {
    font-size: 18px;
    font-weight: 700;
    color: #ffffff;
}
QLabel#SectionTitle {
    font-size: 13px;
    font-weight: 600;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Opacity Slider */
QSlider::groove:horizontal {
    border: 1px solid #374151;
    height: 4px;
    background: #111827;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #2563eb;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #60a5fa;
    border: 1px solid #2563eb;
    width: 12px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 6px;
}
QSlider::handle:horizontal:hover {
    background: #93c5fd;
}

/* Fallback Native ToolTip Styling */
QToolTip {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #312e81, stop:0.45 #6d28d9, stop:0.8 #a21caf, stop:1 #0e7490);
    color: #f0f9ff;
    border: 1px solid #c084fc;
    border-radius: 8px;
    padding: 6px 10px;
    font-weight: 600;
}

/* =====================================================================
   GuideIT Playbooks Workspace Scoped Selectors
   ===================================================================== */
QFrame#expansionBar {
    background-color: rgba(18, 27, 40, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 8px;
}

QFrame#headerCard, QFrame#sectionCard, QFrame#snippetCard, QFrame#emptyStateCard {
    background-color: rgba(22, 29, 39, 0.88);
    border: 1px solid #2A3547;
    border-radius: 8px;
}

QFrame#remediationSectionCard {
    background-color: rgba(27, 23, 21, 0.90);
    border: 1px solid #F59E0B;
    border-radius: 8px;
}

QFrame#codeCard {
    background-color: #0B0F14;
    border: 1px solid #2A3547;
    border-radius: 6px;
}

QFrame#remediationCodeCard {
    background-color: #0B0F14;
    border: 1px solid #F59E0B;
    border-radius: 6px;
}

QFrame#codeHeader {
    background-color: #131922;
    border-bottom: 1px solid #2A3547;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QFrame#remediationCodeHeader {
    background-color: #2A1A12;
    border-bottom: 1px solid #F59E0B;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}

QLineEdit#searchInput {
    background-color: rgba(30, 39, 54, 0.85);
    border: 1px solid #2A3547;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 14px;
    color: #E6EDF3;
    selection-background-color: #38BDF8;
    selection-color: #091017;
}

QLineEdit#searchInput:focus {
    border: 1px solid #38BDF8;
    background-color: #212C3D;
}

QTreeWidget#domainTree {
    background-color: transparent;
    border: none;
    outline: 0;
    show-decoration-selected: 1;
}

QTreeWidget#domainTree::item {
    padding: 4px 6px;
    border-radius: 5px;
    margin: 1px 0px;
    color: #93A4B8;
}

QTreeWidget#domainTree::item:hover {
    background-color: #1E2736;
    color: #E6EDF3;
}

QTreeWidget#domainTree::item:selected {
    background-color: #112A3E;
    color: #38BDF8;
    font-weight: 600;
}

QListWidget#resultsWidget {
    background-color: transparent;
    border: none;
    outline: 0;
}

QListWidget#resultsWidget::item {
    padding: 0px;
    background-color: rgba(22, 29, 39, 0.86);
    border: 1px solid #2A3547;
    border-radius: 8px;
}

QListWidget#resultsWidget::item:hover {
    border-color: #3D4E68;
    background-color: #1A222E;
}

QListWidget#resultsWidget::item:selected {
    border: 1px solid #38BDF8;
    background-color: #162231;
}

QPushButton#accentButton {
    background-color: #112A3E;
    color: #38BDF8;
    border: 1px solid #1E5D82;
    font-weight: 600;
}

QPushButton#accentButton:hover {
    background-color: #163954;
    border-color: #38BDF8;
    color: #ffffff;
}

QPushButton#accentButton:disabled {
    color: #6E8096;
    background-color: #141A23;
    border-color: #202937;
}

QPushButton#tierPill {
    padding: 5px 8px;
    font-weight: 600;
    color: #93A4B8;
    background-color: #161D27;
    border: 1px solid #2A3547;
}

QPushButton#tierPill:checked {
    background-color: #112A3E;
    color: #38BDF8;
    border-color: #38BDF8;
}

QPushButton#copyButton {
    background-color: #1E2736;
    color: #E6EDF3;
    border: 1px solid #2A3547;
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#copyButton:hover {
    background-color: #112A3E;
    color: #38BDF8;
    border-color: #38BDF8;
}

QPushButton#remediationCopyButton {
    background-color: #3B2313;
    color: #FBBF24;
    border: 1px solid #F59E0B;
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#remediationCopyButton:hover {
    background-color: #4E2D18;
    color: #ffffff;
}

QPushButton#relatedPill {
    background-color: #112A3E;
    color: #38BDF8;
    border: 1px solid #1E5D82;
    border-radius: 12px;
    padding: 3px 10px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#relatedPill:hover {
    background-color: #173B57;
    border-color: #38BDF8;
    color: #ffffff;
}

QPushButton#codeChip {
    background-color: #1E2736;
    color: #FDE68A;
    border: 1px solid #3A475D;
    border-radius: 4px;
    padding: 2px 8px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
}

QPushButton#codeChip:hover {
    border-color: #38BDF8;
    color: #E6EDF3;
}

QPushButton#healthPill[status="ok"] {
    background-color: #0F2922;
    color: #34D399;
    border: 1px solid #10B981;
    border-radius: 13px;
    padding: 4px 11px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#healthPill[status="warn"] {
    background-color: #2A1A12;
    color: #FBBF24;
    border: 1px solid #F59E0B;
    border-radius: 13px;
    padding: 4px 11px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#healthPill[status="err"] {
    background-color: #2D1518;
    color: #F87171;
    border: 1px solid #EF4444;
    border-radius: 13px;
    padding: 4px 11px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#healthPill[status="unknown"] {
    background-color: #1E2736;
    color: #93A4B8;
    border: 1px solid #2A3547;
    border-radius: 13px;
    padding: 4px 11px;
    font-size: 12px;
}

QPlainTextEdit#codeEditor {
    background-color: #0B0F14;
    color: #E6EDF3;
    border: none;
    padding: 8px 10px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12.5px;
    selection-background-color: #1F4E78;
}

QPlainTextEdit#reportLog {
    background-color: #0B0F14;
    color: #E6EDF3;
    border: 1px solid #2A3547;
    border-radius: 6px;
    padding: 8px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

/* =====================================================================
   Phase 3 Cross-Linking Action Cards & Unified Omnibox
   ===================================================================== */
QFrame#linkedScriptsSectionCard {
    background-color: rgba(20, 24, 39, 0.90);
    border: 1px solid rgba(139, 92, 246, 0.55);
    border-radius: 8px;
}

QFrame#linkedScriptCard {
    background-color: #0E1525;
    border: 1px solid #2A3547;
    border-radius: 6px;
}

QPushButton#linkedScriptPill {
    background-color: #211938;
    color: #DDD6FE;
    border: 1px solid #6D28D9;
    border-radius: 12px;
    padding: 3px 10px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#linkedScriptPill:hover {
    background-color: #2E224F;
    border-color: #A78BFA;
    color: #FFFFFF;
}

QLineEdit#omniboxInput {
    background-color: rgba(10, 16, 32, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12.5px;
    color: #F8FAFC;
}

QLineEdit#omniboxInput:focus {
    border: 1px solid #38BDF8;
    background-color: rgba(15, 23, 42, 0.95);
}

QFrame#OmniboxPopup {
    background-color: #0F172A;
    border: 1px solid #38BDF8;
    border-radius: 8px;
}

QListWidget#OmniboxResultsList {
    background-color: transparent;
    border: none;
    outline: 0;
}

QListWidget#OmniboxResultsList::item {
    padding: 6px 10px;
    border-radius: 5px;
    border-bottom: 1px solid rgba(51, 65, 85, 0.30);
}

QListWidget#OmniboxResultsList::item:selected {
    background-color: rgba(37, 99, 235, 0.55);
    color: #FFFFFF;
}
"""
