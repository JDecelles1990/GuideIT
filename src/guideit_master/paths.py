"""Centralized PyInstaller-aware path resolver for GuideIT Master."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "GuideIT_Master"
ENV_BUNDLE_DIR = "GUIDEIT_BUNDLE_DIR"
ENV_DATA_DIR = "GUIDEIT_DATA_DIR"


def is_frozen() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def get_bundle_dir() -> Path:
    """Return the root directory containing read-only bundled assets.

    Order of precedence:
    1. GUIDEIT_BUNDLE_DIR environment variable (for tests/CLI overrides).
    2. sys._MEIPASS when frozen by PyInstaller.
    3. Repository root directory (parent of src/) during source execution.
    """
    env_override = os.environ.get(ENV_BUNDLE_DIR)
    if env_override:
        return Path(env_override).resolve()
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return Path(__file__).resolve().parents[2]


def get_user_data_dir() -> Path:
    """Return the writable directory for SQLite databases, logs, and user custom scripts.

    Order of precedence:
    1. GUIDEIT_DATA_DIR environment variable (for isolated pytest tmp_path runs).
    2. %LOCALAPPDATA%\\GuideIT_Master when frozen as a packaged Windows executable.
    3. <repo_root>\\data during local developer execution.
    """
    env_override = os.environ.get(ENV_DATA_DIR)
    if env_override:
        path = Path(env_override).resolve()
    elif is_frozen():
        local_app_data = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = (Path(local_app_data) / APP_NAME).resolve()
    else:
        path = (get_bundle_dir() / "data").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- Read-Only Bundled Assets ---
def get_playbooks_dir(root_dir: Path | None = None) -> Path:
    return ((root_dir or get_bundle_dir()) / "playbooks").resolve()


def get_taxonomy_dir(root_dir: Path | None = None) -> Path:
    return ((root_dir or get_bundle_dir()) / "taxonomy").resolve()


def get_templates_dir(root_dir: Path | None = None) -> Path:
    return ((root_dir or get_bundle_dir()) / "templates").resolve()


def get_ps_scripts_dir(root_dir: Path | None = None) -> Path:
    return ((root_dir or get_bundle_dir()) / "powershell_scripts").resolve()


# --- Writable Local User Data ---
def get_guideit_db_path(data_dir: Path | None = None) -> Path:
    return ((data_dir or get_user_data_dir()) / "guideit.db").resolve()


def get_psstore_db_path(data_dir: Path | None = None) -> Path:
    return ((data_dir or get_user_data_dir()) / "powershell_store.db").resolve()


def get_user_custom_scripts_dir(data_dir: Path | None = None) -> Path:
    """Reserved writable directory for user custom scripts (overlay scanning wired in Phase 4)."""
    custom_dir = ((data_dir or get_user_data_dir()) / "user_scripts").resolve()
    custom_dir.mkdir(parents=True, exist_ok=True)
    return custom_dir


def get_logs_dir(data_dir: Path | None = None) -> Path:
    logs_dir = ((data_dir or get_user_data_dir()) / "logs").resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir
