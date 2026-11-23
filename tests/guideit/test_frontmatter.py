"""Unit tests for GuideIT strict YAML frontmatter parser and section extractor."""

from __future__ import annotations

import pytest

from guideit_master.guideit.frontmatter import FrontmatterError, extract_sections, parse_frontmatter


def test_parse_valid_frontmatter_with_bom_crlf_and_mixed_lists() -> None:
    text = (
        "\ufeff---\r\n"
        "id: id-001\r\n"
        'title: "Account Lockout Investigation" # inline comment\r\n'
        "keywords_en: [locked out, \"bad, password\", 'can''t login']\r\n"
        "keywords_fr:\r\n"
        "  - compte verrouillé\r\n"
        "  - mot de passe refusé\r\n"
        "error_codes: [4740, \"0xC0000234\"]\r\n"
        "requires_admin: true\r\n"
        "related_ids: []\r\n"
        "last_verified: 2026-11-22\r\n"
        "---\r\n\r\n"
        "## Fast Triage (Under 2 Minutes)\r\n"
        "- Scope check\r\n"
    )
    meta, body, body_line = parse_frontmatter(text)
    assert meta["id"] == "id-001"
    assert meta["title"] == "Account Lockout Investigation"
    assert meta["keywords_en"] == ["locked out", "bad, password", "can't login"]
    assert meta["keywords_fr"] == ["compte verrouillé", "mot de passe refusé"]
    assert meta["error_codes"] == ["4740", "0xC0000234"]
    assert meta["requires_admin"] is True
    assert meta["related_ids"] == []
    assert meta["last_verified"] == "2026-11-22"
    assert body.startswith("## Fast Triage")
    assert body_line > 10


@pytest.mark.parametrize(
    ("bad_text", "expected_line"),
    [
        ("id: id-001\n---\n", 1),
        ("---\nid: id-001\n", 1),
        ("---\nid: id-001\nid: id-002\n---\n", 3),
        ("---\n\tid: id-001\n---\n", 2),
        ("---\ntitle: \"unclosed\n---\n", 2),
        ("---\ntitle: 'unclosed\n---\n", 2),
        ("---\ntags: [one, two\n---\n", 2),
        ("---\ntags:\ntitle: Test\n---\n", 2),
    ],
)
def test_parse_frontmatter_rejects_syntax_errors_with_line_numbers(
    bad_text: str,
    expected_line: int,
) -> None:
    with pytest.raises(FrontmatterError) as exc_info:
        parse_frontmatter(bad_text)
    assert exc_info.value.line == expected_line


def test_extract_sections_ignores_headings_inside_code_fences() -> None:
    body = (
        "## Fast Triage (Under 2 Minutes)\n"
        "- Step 1\n\n"
        "```bash\n"
        "## Comment inside fence should not become a section\n"
        "echo ok\n"
        "```\n\n"
        "## Read-Only Diagnostics (L1-L2)\n"
        "Run checks.\n"
    )
    order, sections = extract_sections(body)
    assert order == [
        "Fast Triage (Under 2 Minutes)",
        "Read-Only Diagnostics (L1-L2)",
    ]
    assert "## Comment inside fence" in sections["Fast Triage (Under 2 Minutes)"]
    assert sections["Read-Only Diagnostics (L1-L2)"] == "Run checks."
