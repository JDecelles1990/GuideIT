"""Cyber-aurora frosted glass BackdropFx & QSS styling tests."""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QImage, QPainter

from guideit_master.ui.backdrop_fx import (
    BACKDROP_FX_PROPERTY,
    BACKDROP_PANEL_NAMES,
    BackdropFx,
    install_backdrop_fx,
)
from guideit_master.ui.unified_theme import DARK_THEME_QSS


def test_backdrop_fx_idempotent_install_and_panel_overlays(shell_window_factory) -> None:
    win = shell_window_factory()
    fx1 = win.property(BACKDROP_FX_PROPERTY)
    assert isinstance(fx1, BackdropFx)
    fx2 = install_backdrop_fx(win)
    assert fx2 is fx1
    assert set(fx1.panel_overlays.keys()) == set(BACKDROP_PANEL_NAMES)


def test_aurora_canvas_paint_and_hover_transition(shell_window_factory, qapp) -> None:
    win = shell_window_factory()
    win.show()
    qapp.processEvents()

    fx: BackdropFx = win.property(BACKDROP_FX_PROPERTY)
    img1 = QImage(320, 200, QImage.Format.Format_ARGB32)
    painter1 = QPainter(img1)
    fx.paint_backdrop(painter1, QRectF(0, 0, 320, 200))
    painter1.end()

    # Center pixels differ from edge pixels (non-flat gradient/orbs)
    assert img1.pixelColor(160, 100) != img1.pixelColor(2, 2)

    sidebar = win.scripts_workspace.sidebar
    inspector = win.scripts_workspace.inspector_frame
    sidebar_pos = sidebar.mapTo(win.centralWidget(), sidebar.rect().center())
    inspector_pos = inspector.mapTo(win.centralWidget(), inspector.rect().center())

    fx.set_cursor_pos(QPointF(sidebar_pos))
    assert fx.hovered_panel == "SidebarFrame"
    for _ in range(5):
        time.sleep(0.015)
        fx._tick()
    assert fx.panel_hover_level("SidebarFrame") > 0.0

    fx.set_cursor_pos(QPointF(inspector_pos))
    assert fx.hovered_panel == "InspectorFrame"
    for _ in range(5):
        time.sleep(0.015)
        fx._tick()
    assert fx.panel_hover_level("InspectorFrame") > 0.0


def test_dark_theme_qss_preserves_frosted_glass_and_gradients() -> None:
    assert "rgba(15, 23, 42, 0.58)" in DARK_THEME_QSS
    assert DARK_THEME_QSS.count("qlineargradient") >= 10
