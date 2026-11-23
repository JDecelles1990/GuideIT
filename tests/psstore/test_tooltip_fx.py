"""Animated RainbowTooltip, resolve_tooltip_text & _TooltipFxManager tests."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QPushButton, QTabWidget, QWidget

from guideit_master.ui.tooltip_fx import (
    RainbowTooltip,
    _TooltipFxManager,
    install_tooltip_fx,
    resolve_tooltip_text,
)
from guideit_master.ui.unified_theme import DARK_THEME_QSS


def test_rainbow_tooltip_lifecycle_and_render(qapp) -> None:
    tip = RainbowTooltip()
    assert tip.state == "hidden"
    assert tip.transition_progress == 0.0

    tip.show_tooltip("Copy RMM-Ready Script (Ctrl+Shift+R)", QPoint(120, 120))
    assert tip.state == "showing"
    assert tip.is_active is True
    assert tip.text == "Copy RMM-Ready Script (Ctrl+Shift+R)"

    tip.hide_tooltip(immediate=True)
    assert tip.state == "hidden"
    assert tip.transition_progress == 0.0
    tip.deleteLater()


def test_resolve_tooltip_text_widgets_tabs_and_manager(qapp) -> None:
    mgr1 = install_tooltip_fx(qapp)
    mgr2 = install_tooltip_fx(qapp)
    assert mgr1 is mgr2
    assert isinstance(mgr1, _TooltipFxManager)

    parent = QWidget()
    parent.setToolTip("Parent Container Tip")
    child = QPushButton("Action", parent)
    assert resolve_tooltip_text(child) == "Parent Container Tip"
    child.setToolTip("Child Explicit Tip")
    assert resolve_tooltip_text(child) == "Child Explicit Tip"

    tabs = QTabWidget()
    tab0 = QWidget()
    tabs.addTab(tab0, "Structured Results")
    tabs.setTabToolTip(0, "Structured Results (Ctrl+1)")
    tab_bar = tabs.tabBar()
    tab_center = tab_bar.tabRect(0).center()
    assert resolve_tooltip_text(tab_bar, tab_center) == "Structured Results (Ctrl+1)"

    help_evt = QHelpEvent(QEvent.Type.ToolTip, QPoint(5, 5), QPoint(150, 150))
    qapp.sendEvent(child, help_evt)
    assert mgr1.popup.text == "Child Explicit Tip"
    mgr1.popup.hide_tooltip(immediate=True)

    parent.deleteLater()
    tabs.deleteLater()


def test_qtooltip_fallback_stylesheet_present() -> None:
    assert "QToolTip" in DARK_THEME_QSS
    assert "#c084fc" in DARK_THEME_QSS
