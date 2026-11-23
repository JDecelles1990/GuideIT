"""Phase 3 PySide6 UI widget, layer boundary & UnifiedShellWindow tests."""

from __future__ import annotations

import ast
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QHeaderView, QLineEdit, QSpinBox

from guideit_master.psstore.repositories.catalog_repo import ScriptRecord
from guideit_master.psstore.services.runner import RunResult
from guideit_master.psstore.ui.catalog_table_view import CatalogTableView
from guideit_master.psstore.ui.console_view import ConsoleView
from guideit_master.psstore.ui.parameter_form import ParameterFormWidget

FORBIDDEN_UI_MODULES = {"sqlite3", "subprocess", "hashlib"}


def test_zero_forbidden_imports_in_ui_layer() -> None:
    src_root = Path(__file__).resolve().parents[2] / "src" / "guideit_master"
    ui_dirs = [src_root / "ui", src_root / "psstore" / "ui"]
    py_files = [p for d in ui_dirs if d.exists() for p in d.rglob("*.py")]
    assert len(py_files) >= 6

    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in FORBIDDEN_UI_MODULES, f"{py_file} imports {top}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                top = node.module.split(".")[0]
                assert top not in FORBIDDEN_UI_MODULES, f"{py_file} imports from {top}"


def test_parameter_form_typed_controls_and_reset(qapp) -> None:
    form = ParameterFormWidget()
    script = ScriptRecord(
        relative_path="01_System/Test.ps1",
        category="System",
        filename="Test.ps1",
        title="Typed Form Test",
        params=[
            {"name": "Host", "type": "string", "default": "PC01"},
            {"name": "Count", "type": "int", "default": 15, "min": 1, "max": 100},
            {"name": "Detailed", "type": "bool", "default": True},
        ],
    )
    form.load_script(script)

    assert isinstance(form._input_widgets["Host"], QLineEdit)
    assert isinstance(form._input_widgets["Count"], QSpinBox)
    assert isinstance(form._input_widgets["Detailed"], QCheckBox)

    assert form.get_parameter_values() == {"Host": "PC01", "Count": 15, "Detailed": True}

    form.set_parameter_values({"Host": "SRV02", "Count": 50, "Detailed": False})
    assert form.get_parameter_values() == {"Host": "SRV02", "Count": 50, "Detailed": False}

    form.reset_to_defaults()
    assert form.get_parameter_values() == {"Host": "PC01", "Count": 15, "Detailed": True}
    form.deleteLater()


def test_catalog_table_and_console_table_resize_modes(qapp) -> None:
    catalog = CatalogTableView()
    headers = [catalog.table.horizontalHeaderItem(i).text() for i in range(3)]
    assert headers == ["Title", "Risk Level", "Admin"]
    hdr = catalog.table.horizontalHeader()
    assert hdr.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert hdr.sectionResizeMode(1) == QHeaderView.ResizeMode.Interactive
    assert hdr.sectionResizeMode(2) == QHeaderView.ResizeMode.Interactive

    console = ConsoleView()
    console.display_run_result(
        RunResult(
            script_id=1,
            duration_ms=10,
            exit_code=0,
            status="pass",
            summary="OK",
            data=[{"Host": "PC-LAB-01", "Status": "Healthy"}],
        )
    )
    assert console.data_table.columnCount() == 2
    assert (
        console.data_table.horizontalHeader().sectionResizeMode(0)
        == QHeaderView.ResizeMode.Interactive
    )
    assert (
        console.data_table.horizontalHeader().sectionResizeMode(1)
        == QHeaderView.ResizeMode.Interactive
    )
    assert console.data_table.horizontalHeader().stretchLastSection() is False
    catalog.deleteLater()
    console.deleteLater()


def test_shell_window_sidebar_collapse_and_opacity_slider(shell_window_factory) -> None:
    win = shell_window_factory()
    win.show()

    ws = win.scripts_workspace
    assert ws.sidebar.isVisible()
    ws.toggle_sidebar()
    assert not ws.sidebar.isVisible()
    ws.toggle_sidebar()
    assert ws.sidebar.isVisible()

    assert win.opacity_slider.minimum() == 60
    assert win.opacity_slider.maximum() == 100
    assert win.opacity_slider.value() == 100

    win.opacity_slider.setValue(75)
    assert win.opacity_label.text() == "75%"
    assert abs(win.windowOpacity() - 0.75) < 0.02
