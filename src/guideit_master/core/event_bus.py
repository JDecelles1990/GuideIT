"""Lightweight Qt Signal event bus decoupling GuideIT and PowerShellStore modules."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppEventBus(QObject):
    """Central event bus coordinated by UnifiedShellWindow.

    Ensures GuideIT UI widgets and PowerShellStore UI widgets never cross-import
    each other directly.
    """

    open_script_requested = Signal(str, dict, bool)  # (relative_path, param_overrides, split_view)
    copy_script_requested = Signal(str, dict, bool)  # (relative_path, param_overrides, rmm_ready)
    run_script_requested = Signal(str, dict)         # (relative_path, param_overrides)
    open_playbook_requested = Signal(str, bool)      # (playbook_id, split_view)
    catalog_synced = Signal()
    playbooks_reindexed = Signal()
    status_toast_requested = Signal(str, int)        # (message, timeout_ms)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
