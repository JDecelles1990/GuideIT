"""ButtonFx & GlowItemDelegate animated hover/ripple effects tests."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtWidgets import QPushButton

from guideit_master.ui.effects import (
    FX_PROPERTY,
    ButtonFx,
    GlowItemDelegate,
    install_button_fx,
    install_item_view_glow_recursive,
)


def test_button_fx_hover_click_and_manager_idempotent(qapp) -> None:
    mgr1 = install_button_fx(qapp)
    mgr2 = install_button_fx(qapp)
    assert mgr1 is mgr2

    btn = QPushButton("Run Script")
    fx = ButtonFx(btn)
    assert btn.property(FX_PROPERTY) is True
    assert fx.hover_level == 0.0

    fx.set_hovered(True)
    assert fx.is_active is True
    fx.trigger_click(QPointF(10.0, 10.0))
    assert len(fx._ripples) == 1

    qapp.sendEvent(btn, QEvent(QEvent.Type.Enter))
    fx._timer.stop()
    btn.deleteLater()


def test_glow_item_delegate_installed_on_shell_views(shell_window_factory) -> None:
    win = shell_window_factory()
    delegates = install_item_view_glow_recursive(win)
    assert len(delegates) >= 4  # category_list, catalog table, data_table, history_table
    assert isinstance(win.scripts_workspace.sidebar.category_list.itemDelegate(), GlowItemDelegate)
    assert isinstance(win.scripts_workspace.catalog_view.table.itemDelegate(), GlowItemDelegate)
    assert isinstance(win.scripts_workspace.console_view.data_table.itemDelegate(), GlowItemDelegate)
    assert isinstance(win.scripts_workspace.console_view.history_table.itemDelegate(), GlowItemDelegate)

    cat_delegate: GlowItemDelegate = win.scripts_workspace.sidebar.category_list.itemDelegate()
    cat_delegate.set_hover_row(0)
    assert cat_delegate.hover_row == 0
    cat_delegate.trigger_click(0, QPointF(12.0, 12.0))
    assert len(cat_delegate._ripples) == 1
    cat_delegate._timer.stop()
