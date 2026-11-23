"""Background QThread workers for validation and SQLite FTS5 re-indexing."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from guideit_master.guideit.indexer import build_index
from guideit_master.guideit.validator import validate_repository


class ReindexWorker(QThread):
    """Validates playbooks and rebuilds data/guideit.db off the UI thread."""

    completed = Signal(object, object)  # (ValidationReport, IndexStats)
    failed = Signal(str)

    def __init__(
        self,
        root_dir: Path,
        db_path: Path,
        *,
        max_age_days: int = 180,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.root_dir = root_dir
        self.db_path = db_path
        self.max_age_days = max_age_days

    def run(self) -> None:
        try:
            report = validate_repository(self.root_dir, max_age_days=self.max_age_days)
            stats = build_index(self.root_dir, db_path=self.db_path)
        except Exception as exc:  # pragma: no cover - surfaced to UI error handler
            self.failed.emit(str(exc))
            return
        self.completed.emit(report, stats)
