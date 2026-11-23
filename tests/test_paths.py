"""Tests for PyInstaller-ready centralized path resolution in guideit_master.paths."""

from __future__ import annotations

import sys
from pathlib import Path

from guideit_master import paths


def test_source_mode_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(paths.ENV_BUNDLE_DIR, raising=False)
    monkeypatch.delenv(paths.ENV_DATA_DIR, raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    expected_root = Path(__file__).resolve().parent.parent.resolve()
    assert paths.is_frozen() is False
    assert paths.get_bundle_dir() == expected_root
    assert paths.get_user_data_dir() == (expected_root / "data").resolve()
    assert paths.get_playbooks_dir() == (expected_root / "playbooks").resolve()
    assert paths.get_taxonomy_dir() == (expected_root / "taxonomy").resolve()
    assert paths.get_templates_dir() == (expected_root / "templates").resolve()
    assert paths.get_ps_scripts_dir() == (expected_root / "powershell_scripts").resolve()
    assert paths.get_psstore_db_path() == (expected_root / "data" / "powershell_store.db").resolve()
    assert paths.get_guideit_db_path() == (expected_root / "data" / "guideit.db").resolve()

    custom_dir = paths.get_user_custom_scripts_dir(data_dir=tmp_path)
    assert custom_dir == (tmp_path / "user_scripts").resolve()
    assert custom_dir.is_dir()

    logs_dir = paths.get_logs_dir(data_dir=tmp_path)
    assert logs_dir == (tmp_path / "logs").resolve()
    assert logs_dir.is_dir()


def test_frozen_pyinstaller_mode_paths(monkeypatch, tmp_path: Path) -> None:
    meipass_dir = tmp_path / "bundle_meipass"
    local_app_data = tmp_path / "local_appdata"
    meipass_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.delenv(paths.ENV_BUNDLE_DIR, raising=False)
    monkeypatch.delenv(paths.ENV_DATA_DIR, raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))

    expected_user_data = (local_app_data / paths.APP_NAME).resolve()

    assert paths.is_frozen() is True
    assert paths.get_bundle_dir() == meipass_dir.resolve()
    assert paths.get_playbooks_dir() == (meipass_dir / "playbooks").resolve()
    assert paths.get_taxonomy_dir() == (meipass_dir / "taxonomy").resolve()
    assert paths.get_templates_dir() == (meipass_dir / "templates").resolve()
    assert paths.get_ps_scripts_dir() == (meipass_dir / "powershell_scripts").resolve()

    assert paths.get_user_data_dir() == expected_user_data
    assert expected_user_data.is_dir()
    assert paths.get_psstore_db_path() == (expected_user_data / "powershell_store.db").resolve()
    assert paths.get_guideit_db_path() == (expected_user_data / "guideit.db").resolve()
    assert paths.get_user_custom_scripts_dir() == (expected_user_data / "user_scripts").resolve()
    assert paths.get_logs_dir() == (expected_user_data / "logs").resolve()


def test_environment_variable_overrides(monkeypatch, tmp_path: Path) -> None:
    override_bundle = tmp_path / "override_bundle"
    override_data = tmp_path / "override_data"
    override_bundle.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "ignored_meipass"), raising=False)
    monkeypatch.setenv(paths.ENV_BUNDLE_DIR, str(override_bundle))
    monkeypatch.setenv(paths.ENV_DATA_DIR, str(override_data))

    assert paths.get_bundle_dir() == override_bundle.resolve()
    assert paths.get_ps_scripts_dir() == (override_bundle / "powershell_scripts").resolve()
    assert paths.get_user_data_dir() == override_data.resolve()
    assert override_data.is_dir()
    assert paths.get_psstore_db_path() == (override_data / "powershell_store.db").resolve()
    assert paths.get_guideit_db_path() == (override_data / "guideit.db").resolve()
