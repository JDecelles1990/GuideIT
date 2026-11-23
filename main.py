"""Root launcher wrapper for GuideIT Master (works both from source and PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_on_path() -> None:
    if getattr(sys, "frozen", False):
        return
    src_dir = Path(__file__).resolve().parent / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))


if __name__ == "__main__":
    _ensure_src_on_path()
    from guideit_master.main import main

    raise SystemExit(main())
