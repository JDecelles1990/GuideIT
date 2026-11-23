"""Rich-text HTML & Markdown ticket report and ConsoleView history reload tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from guideit_master.psstore.repositories.catalog_repo import RunHistoryRecord
from guideit_master.psstore.services.report_service import ReportService
from guideit_master.psstore.services.runner import RunResult
from guideit_master.psstore.ui.console_view import ConsoleView


def _sample_result(with_errors: bool = True) -> RunResult:
    return RunResult(
        script_id=3,
        duration_ms=412,
        exit_code=1 if with_errors else 0,
        status="warning" if with_errors else "pass",
        summary="Checked 2 volumes; C: low free space.",
        data=[
            {"DeviceID": "C:", "FreeGB": 9.4, "PercentFree": 8},
            {"DeviceID": "D:", "FreeGB": 240.0, "PercentFree": 60},
        ],
        errors=["Volume C: below 15% threshold"] if with_errors else [],
        raw_output="DeviceID FreeGB PercentFree\nC: 9.4 8",
        raw_json=json.dumps(
            {
                "status": "warning" if with_errors else "pass",
                "summary": "Checked 2 volumes; C: low free space.",
                "data": [{"DeviceID": "C:", "FreeGB": 9.4, "PercentFree": 8}],
                "errors": ["Volume C: below 15% threshold"] if with_errors else [],
            }
        ),
        script_title="Disk Free Space Report",
        script_category="System",
    )


def test_report_service_html_markdown_mime_and_save(qapp, tmp_path: Path, monkeypatch) -> None:
    svc = ReportService()
    info = svc.get_system_audit_info()
    assert {"hostname", "operator", "os_name", "timestamp"} <= set(info.keys())

    res = _sample_result(with_errors=True)
    host_info = {
        "hostname": "PC-LAB-01",
        "operator": "tech.demo",
        "os_name": "Windows 11",
        "timestamp": "2026-11-22 10:00:00",
    }

    full_html = svc.generate_html_report(
        "Disk Free Space Report", res, host_info=host_info, script_category="System", standalone=True
    )
    assert "<!DOCTYPE html>" in full_html
    assert "PC-LAB-01" in full_html
    assert "Volume C: below 15% threshold" in full_html
    assert "PowerShellStore Workstation" in full_html

    frag_html = svc.generate_html_report(
        "Disk Free Space Report", res, host_info=host_info, script_category="System", standalone=False
    )
    assert "<!DOCTYPE html>" not in frag_html
    assert "DeviceID" in frag_html

    md = svc.generate_markdown_report(
        "Disk Free Space Report", res, host_info=host_info, script_category="System"
    )
    assert "### [PowerShellStore Audit] Disk Free Space Report" in md
    assert "| DeviceID | FreeGB | PercentFree |" in md
    assert "`Volume C: below 15% threshold`" in md

    mime = svc.create_mime_data("Disk Free Space Report", res, host_info=host_info)
    assert mime.hasHtml()
    assert mime.hasText()

    mock_clipboard = MagicMock()
    monkeypatch.setattr(
        "guideit_master.psstore.services.report_service.QGuiApplication.clipboard",
        lambda: mock_clipboard,
    )
    assert svc.copy_ticket_report_to_clipboard("Disk Free Space Report", res) is True
    mock_clipboard.setMimeData.assert_called_once()

    out_path = tmp_path / "reports" / "audit.html"
    saved = svc.save_html_report(out_path, "Disk Free Space Report", res, host_info=host_info)
    assert saved.exists()
    assert "Disk Free Space Report" in saved.read_text(encoding="utf-8")


def test_console_view_display_and_history_reload(qapp) -> None:
    console = ConsoleView()
    assert not console.copy_report_btn.isEnabled()
    assert not console.save_report_btn.isEnabled()

    res = _sample_result(with_errors=True)
    console.display_run_result(res)
    assert console.copy_report_btn.isEnabled()
    assert console.save_report_btn.isEnabled()
    assert console.status_badge.text() == "WARNING"
    assert console.data_table.rowCount() == 2
    assert console.errors_box.isVisible() or "below 15%" in console.errors_box.toPlainText()

    hist = RunHistoryRecord(
        id=1,
        script_id=3,
        duration_ms=200,
        exit_code=0,
        status="pass",
        summary="Clean volume check",
        raw_output="Clean raw log",
        json_payload=json.dumps({"data": [{"Drive": "C:"}], "errors": []}),
        executed_at="2026-11-22 09:30:00",
    )
    console.display_history([hist])
    assert console.history_table.rowCount() == 1
    console._on_history_double_clicked(0, 0)
    assert "[History: 2026-11-22 09:30:00]" in console.summary_box.text()
    assert "Clean raw log" in console.raw_console.toPlainText()
    console.deleteLater()
