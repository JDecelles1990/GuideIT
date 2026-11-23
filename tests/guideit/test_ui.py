"""Unit and PySide6 integration tests for the GuideIT Playbooks workspace UI."""

from __future__ import annotations

import ast
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit

from guideit_master.guideit.frontmatter import extract_sections
from guideit_master.guideit.indexer import build_index
from guideit_master.guideit.ui.main_window import PlaybooksWorkspaceWidget
from guideit_master.guideit.ui.markdown_blocks import CodeBlock, ProseBlock, parse_section_blocks
from guideit_master.guideit.ui.widgets.resources_dialog import ResourcesDialog
from guideit_master.guideit.validator import load_playbook_file

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_COUNT = len(list((REPO_ROOT / "playbooks").glob("*/*.md")))


@pytest.fixture()
def window(qapp: QApplication, tmp_path: Path) -> PlaybooksWorkspaceWidget:
    db_path = tmp_path / "guideit.db"
    build_index(REPO_ROOT, db_path=db_path)
    win = PlaybooksWorkspaceWidget(REPO_ROOT, db_path=db_path)
    qapp.processEvents()
    yield win
    win.shutdown_workers()
    win.close()
    win.deleteLater()
    qapp.processEvents()


def test_parse_section_blocks_splits_code_remediation_and_links() -> None:
    diag_content = (
        "1. Run check and escalate to `[sec-001]` if needed:\n"
        "   ```powershell\n"
        "   Get-Date\n"
        "   ```\n"
        "2. Check cmd output:\n"
        "   ```cmd\n"
        "   cmdkey /list\n"
        "   ```\n"
    )
    diag = parse_section_blocks("Read-Only Diagnostics (L1-L2)", diag_content)
    assert diag.category == "diagnostics"
    code_blocks = [b for b in diag.blocks if isinstance(b, CodeBlock)]
    prose_blocks = [b for b in diag.blocks if isinstance(b, ProseBlock)]
    assert len(code_blocks) == 2
    assert code_blocks[0].language == "powershell"
    assert code_blocks[0].is_remediation is False
    assert code_blocks[1].language == "cmd"
    assert any("guideit://sec-001" in p.html for p in prose_blocks)

    rem = parse_section_blocks(
        "Remediation (Confirm Before Running)",
        "1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Unlock:\n```powershell\nUnlock-ADAccount jsmith\n```\n",
    )
    assert rem.category == "remediation"
    rem_codes = [b for b in rem.blocks if isinstance(b, CodeBlock)]
    assert len(rem_codes) == 1
    assert rem_codes[0].is_remediation is True

    pivots = parse_section_blocks(
        "Cross-Subject Escalation & Pivot Links",
        "- **DNS / WSD Offline:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)\n",
    )
    assert pivots.category == "pivots"
    pivot_prose = [b for b in pivots.blocks if isinstance(b, ProseBlock)]
    assert len(pivot_prose) == 1
    assert 'href="guideit://net-001"' in pivot_prose[0].html
    assert "net-001 — No Internet" in pivot_prose[0].html
    assert "→" in pivot_prose[0].html


def test_all_seed_playbooks_produce_en_and_fr_client_snippets() -> None:
    playbooks = sorted((REPO_ROOT / "playbooks").glob("*/*.md"))
    assert len(playbooks) == EXPECTED_COUNT
    assert EXPECTED_COUNT >= 65
    for pb_file in playbooks:
        pb = load_playbook_file(REPO_ROOT, pb_file)
        order, sections = extract_sections(pb.body_markdown)
        snippet_headings = [h for h in order if "client update snippets" in h.lower()]
        assert len(snippet_headings) == 1, f"Missing snippet section in {pb.id}"
        parsed = parse_section_blocks(snippet_headings[0], sections[snippet_headings[0]])
        assert parsed.snippets is not None
        assert parsed.snippets.en, f"Missing EN snippet in {pb.id}"
        assert parsed.snippets.fr, f"Missing FR snippet in {pb.id}"


def test_mainwindow_startup_search_and_facets(
    qapp: QApplication, window: PlaybooksWorkspaceWidget
) -> None:
    assert window.results_list.results_widget.count() == EXPECTED_COUNT
    tree = window.filter_sidebar.domain_tree
    assert tree.topLevelItemCount() == 10  # All Subjects + 9 domains
    total_subcats = sum(
        tree.topLevelItem(i).childCount() for i in range(1, tree.topLevelItemCount())
    )
    assert total_subcats == 23
    assert window.health_button.text() == f"✓ {EXPECTED_COUNT} Valid"
    assert window.viewer.current_playbook_id is not None

    # Collapse & re-expand Subjects tree toggle
    assert window.filter_sidebar.toggle_expand_button.text() == "Collapse"
    window.filter_sidebar.toggle_expand_button.click()
    qapp.processEvents()
    assert window.filter_sidebar.toggle_expand_button.text() == "Expand"
    assert not tree.topLevelItem(1).isExpanded()
    window.filter_sidebar.toggle_expand_button.click()
    qapp.processEvents()
    assert window.filter_sidebar.toggle_expand_button.text() == "Collapse"
    assert tree.topLevelItem(1).isExpanded()

    # Selecting a subdivided child sub-subject filters to its exact playbooks
    printers_domain_item = tree.topLevelItem(5)
    assert printers_domain_item is not None
    spooler_sub_item = printers_domain_item.child(0)
    tree.setCurrentItem(spooler_sub_item)
    window.run_search_now()
    qapp.processEvents()
    sub_ids = {
        window.results_list.results_widget.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(window.results_list.results_widget.count())
    }
    assert sub_ids == {"prt-001", "prt-004"}

    window.filter_sidebar.reset_button.click()
    qapp.processEvents()
    assert window.results_list.results_widget.count() == EXPECTED_COUNT

    # Bilingual French accent-insensitive search
    window.search_input.setText("compte verrouille")
    window.run_search_now()
    qapp.processEvents()

    assert window.results_list.selected_playbook_id() == "id-001"
    assert window.viewer.current_playbook_id == "id-001"
    assert window.expansion_bar.isVisibleTo(window)
    assert "account_lockout" in window.expansion_label.text()

    # Exact error code + facet filtering
    window.search_input.setText("intune non conforme")
    window.filter_sidebar.tier_buttons["L2"].click()
    os_idx = window.filter_sidebar.os_combo.findData("macos")
    assert os_idx >= 0
    window.filter_sidebar.os_combo.setCurrentIndex(os_idx)
    window.run_search_now()
    qapp.processEvents()

    assert window.results_list.results_widget.count() >= 1
    assert window.results_list.selected_playbook_id() == "mdm-001"

    ios_idx = window.filter_sidebar.os_combo.findData("ios")
    assert ios_idx >= 0
    window.filter_sidebar.os_combo.setCurrentIndex(ios_idx)
    window.run_search_now()
    qapp.processEvents()
    assert window.results_list.results_widget.count() == 1
    assert window.results_list.selected_playbook_id() == "mdm-001"

    # Reset filters restores all playbooks
    window.filter_sidebar.reset_button.click()
    qapp.processEvents()
    assert window.results_list.results_widget.count() == EXPECTED_COUNT
    assert window.search_input.text() == ""


def test_code_and_snippet_copy_and_related_navigation(
    qapp: QApplication,
    window: PlaybooksWorkspaceWidget,
) -> None:
    window.search_input.setText("0x0000011b")
    window.run_search_now()
    qapp.processEvents()

    assert window.viewer.current_playbook_id == "prt-001"
    assert len(window.viewer.code_widgets) >= 3
    assert any(cw.is_remediation for cw in window.viewer.code_widgets)
    assert window.viewer.copy_en_button is not None
    assert window.viewer.copy_fr_button is not None

    # Click Copy on first code block and verify clipboard text
    first_cw = window.viewer.code_widgets[0]
    first_cw.copy_button.click()
    qapp.processEvents()
    assert QApplication.clipboard().text() == first_cw.code_text

    # Click Copy FR Update and verify French snippet on clipboard
    window.viewer.copy_fr_button.click()
    qapp.processEvents()
    assert "spouleur" in QApplication.clipboard().text().lower()

    # Navigate to related playbook via id-001 -> sec-001, then test Back
    window.search_input.setText("4740")
    window.run_search_now()
    qapp.processEvents()
    assert window.viewer.current_playbook_id == "id-001"
    assert "sec-001" in window.viewer.related_buttons

    window.viewer.related_buttons["sec-001"].click()
    qapp.processEvents()
    assert window.viewer.current_playbook_id == "sec-001"
    assert window.viewer.back_button is not None and window.viewer.back_button.isEnabled()

    window.viewer.back_button.click()
    qapp.processEvents()
    assert window.viewer.current_playbook_id == "id-001"
    assert window.viewer.back_button is not None and not window.viewer.back_button.isEnabled()

    # Cross-subject relative .md link navigation (prt-001 -> net-001 -> Back)
    window.navigate_to_playbook("prt-001")
    qapp.processEvents()
    assert window.viewer.current_playbook_id == "prt-001"
    window.viewer._handle_link("guideit://net-001")
    qapp.processEvents()
    assert window.viewer.current_playbook_id == "net-001"
    assert window.viewer.back_button is not None and window.viewer.back_button.isEnabled()
    window.viewer.back_button.click()
    qapp.processEvents()
    assert window.viewer.current_playbook_id == "prt-001"


def test_no_match_empty_state_and_background_reindex(
    qapp: QApplication,
    window: PlaybooksWorkspaceWidget,
) -> None:
    window.search_input.setText("zzzz_nonexistent_issue_999")
    window.run_search_now()
    qapp.processEvents()

    assert window.results_list.stack.currentIndex() == 1
    assert window.viewer.current_playbook_id is None

    window.reset_all()
    qapp.processEvents()
    assert window.results_list.stack.currentIndex() == 0
    assert window.results_list.results_widget.count() == EXPECTED_COUNT

    # Background Validate & Re-Index worker
    window.start_reindex()
    deadline = time.monotonic() + 10.0
    while window._worker is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.02)
    qapp.processEvents()

    assert window._worker is None
    assert window.reindex_button.isEnabled()
    assert window.health_button.text() == f"✓ {EXPECTED_COUNT} Valid"
    assert window.results_list.results_widget.count() == EXPECTED_COUNT


def test_results_cards_do_not_overflow_horizontally_or_clip_vertically(
    qapp: QApplication,
    window: PlaybooksWorkspaceWidget,
) -> None:
    window.resize(1360, 840)
    window.show()
    qapp.processEvents()

    def _assert_cards_fit() -> None:
        rw = window.results_list.results_widget
        vp_w = rw.viewport().width()
        spacing = rw.spacing()
        assert rw.count() == EXPECTED_COUNT
        for idx in range(rw.count()):
            item = rw.item(idx)
            card = rw.itemWidget(item)
            assert card is not None
            assert card.width() <= vp_w - 2 * spacing
            required_h = card.heightForWidth(card.width())
            if required_h > 0:
                assert item.sizeHint().height() >= required_h
            for lbl in card.findChildren(QLabel):
                assert lbl.geometry().right() <= card.rect().right()
                assert lbl.geometry().bottom() <= card.rect().bottom()

    _assert_cards_fit()

    # Narrow the middle pane via splitter and re-verify wrapped layout adapts cleanly
    window.splitter.setSizes([240, 290, 830])
    qapp.processEvents()
    _assert_cards_fit()


def test_markdown_external_links_and_resources_dialog(
    qapp: QApplication,
    window: PlaybooksWorkspaceWidget,
) -> None:
    links_sec = parse_section_blocks(
        "Useful Links & External Tools",
        "- **[MXToolbox](https://mxtoolbox.com/SuperTool.aspx)** — Check SPF/DKIM.",
    )
    assert links_sec.category == "links"
    prose = [b for b in links_sec.blocks if isinstance(b, ProseBlock)]
    assert len(prose) == 1
    assert 'href="https://mxtoolbox.com/SuperTool.aspx"' in prose[0].html
    assert "MXToolbox ↗" in prose[0].html

    dlg = ResourcesDialog(REPO_ROOT, parent=window)
    qapp.processEvents()
    assert len(dlg.visible_resource_names()) >= 25

    dlg.search_input.setText("virustotal")
    qapp.processEvents()
    assert dlg.visible_resource_names() == ["VirusTotal"]
    dlg.copy_buttons["VirusTotal"].click()
    qapp.processEvents()
    assert QApplication.clipboard().text() == "https://www.virustotal.com/"

    dlg.search_input.setText("subnet")
    qapp.processEvents()
    assert any("Subnet Calculator" in name for name in dlg.visible_resource_names())

    dlg.search_input.setText("adobe")
    qapp.processEvents()
    assert any("Adobe" in name for name in dlg.visible_resource_names())
    dlg.close()


def test_code_blocks_wrap_cleanly_without_horizontal_or_vertical_clipping(
    qapp: QApplication,
    window: PlaybooksWorkspaceWidget,
) -> None:
    window.resize(1360, 840)
    window.show()
    window.navigate_to_playbook("mdm-007")
    qapp.processEvents()

    def _assert_code_blocks_fit() -> None:
        assert window.viewer.current_playbook_id == "mdm-007"
        assert len(window.viewer.code_widgets) >= 3
        for cw in window.viewer.code_widgets:
            assert cw.editor.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
            assert not cw.editor.horizontalScrollBar().isVisible()
            assert cw.editor.verticalScrollBar().maximum() == 0

    _assert_code_blocks_fit()

    # Narrow the right viewer pane and re-verify long commands wrap cleanly without clipping
    window.splitter.setSizes([240, 350, 460])
    qapp.processEvents()
    _assert_code_blocks_fit()

    # Verify Copy button still copies unwrapped verbatim command
    first_cw = window.viewer.code_widgets[0]
    first_cw.copy_button.click()
    qapp.processEvents()
    assert QApplication.clipboard().text() == first_cw.code_text


def test_guideit_ui_has_zero_forbidden_imports_or_cross_imports() -> None:
    ui_root = REPO_ROOT / "src" / "guideit_master" / "guideit" / "ui"
    forbidden_modules = {"sqlite3", "subprocess", "hashlib"}

    for py_file in sorted(ui_root.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in forbidden_modules, (
                        f"Forbidden import '{alias.name}' in {py_file}"
                    )
                    assert not alias.name.startswith("guideit_master.psstore"), (
                        f"Forbidden cross-module import '{alias.name}' in {py_file}"
                    )
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                top = mod.split(".")[0]
                assert top not in forbidden_modules, f"Forbidden import '{mod}' in {py_file}"
                assert not mod.startswith("guideit_master.psstore"), (
                    f"Forbidden cross-module import '{mod}' in {py_file}"
                )
