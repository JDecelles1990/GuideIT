"""Unit tests for GuideIT schema validator and multi-tenant PII/redaction linter."""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

from guideit_master.guideit.validator import validate_repository

REPO_ROOT = Path(__file__).resolve().parents[2]


def _copy_taxonomy(dst_root: Path) -> None:
    shutil.copytree(REPO_ROOT / "taxonomy", dst_root / "taxonomy")
    (dst_root / "playbooks" / "01_Identity_AD_Entra").mkdir(parents=True)


def _valid_playbook_content(
    *,
    pb_id: str = "id-001",
    tier: str = "L2",
    last_verified: str = "2026-11-22",
    related_ids: str = "[]",
    extra_body: str = "",
    sections_override: str | None = None,
) -> str:
    body = sections_override or (
        "## Fast Triage (Under 2 Minutes)\n"
        "- Check single user vs tenant-wide.\n\n"
        "## Read-Only Diagnostics (L1-L2)\n"
        "- Inspect `jsmith@example.com` and `198.51.100.10` or `10.10.1.5` / `1.1.1.1`.\n"
        "- Placeholder GUID: `00000000-0000-0000-0000-000000000000`.\n\n"
        "## Deep-Dive Investigation (L3)\n"
        "- Review audit logs.\n\n"
        "## Remediation (Confirm Before Running)\n"
        "- **[REMEDIATION — CONFIRM BEFORE RUNNING]** Unlock account.\n\n"
        "## Verification & Post-Fix Checks\n"
        "- Confirm sign-in works.\n"
        f"{extra_body}"
    )
    return (
        f"---\n"
        f"id: {pb_id}\n"
        f"domain: 01_Identity_AD_Entra\n"
        f'subject: "Identity / AD & Entra ID"\n'
        f"title: Account Lockout Investigation\n"
        f"tier: {tier}\n"
        f"keywords_en: [locked out, account locked]\n"
        f"keywords_fr: [compte verrouillé]\n"
        f'error_codes: ["4740"]\n'
        f"tags: [account_lockout, bad_password]\n"
        f"os: [windows]\n"
        f"environment: [hybrid_ad]\n"
        f"tools: [PowerShell]\n"
        f"risk_level: low\n"
        f"requires_admin: true\n"
        f"last_verified: {last_verified}\n"
        f"related_ids: {related_ids}\n"
        f"---\n\n"
        f"{body}"
    )


def test_real_repository_passes_strict_validation() -> None:
    expected_count = len(list((REPO_ROOT / "playbooks").glob("*/*.md")))
    assert expected_count >= 65
    report = validate_repository(REPO_ROOT, max_age_days=180, today=date(2026, 11, 22))
    assert report.checked_files == expected_count
    assert report.errors == []
    assert report.warnings == []
    assert report.strict_ok is True


def test_validator_catches_pii_leaks_while_allowing_placeholders(tmp_path: Path) -> None:
    _copy_taxonomy(tmp_path)
    pb_path = tmp_path / "playbooks" / "01_Identity_AD_Entra" / "id-001-lockout.md"
    pb_path.write_text(
        _valid_playbook_content(
            extra_body=(
                "\nReal leak email: alice@acmecorp.ca\n"
                "Real public IP: 45.33.32.156\n"
                "Real GUID: 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d\n"
                "-----BEGIN PRIVATE KEY-----\n"
            )
        ),
        encoding="utf-8",
    )

    report = validate_repository(tmp_path, today=date(2026, 11, 22))
    codes = {issue.code for issue in report.errors}
    assert {"PII_EMAIL", "PII_PUBLIC_IP", "PII_GUID", "PII_SECRET"}.issubset(codes)


def test_validator_catches_structural_schema_and_staleness_issues(tmp_path: Path) -> None:
    _copy_taxonomy(tmp_path)
    p1 = tmp_path / "playbooks" / "01_Identity_AD_Entra" / "id-001-first.md"
    p2 = tmp_path / "playbooks" / "01_Identity_AD_Entra" / "badname-second.md"

    p1.write_text(
        _valid_playbook_content(
            pb_id="id-001",
            tier="L9",
            last_verified="2025-01-01",
            related_ids="[missing-999]",
            sections_override="## Fast Triage (Under 2 Minutes)\n- Missing rest.\n",
        ),
        encoding="utf-8",
    )
    p2.write_text(
        _valid_playbook_content(pb_id="win-001"),
        encoding="utf-8",
    )

    report = validate_repository(tmp_path, max_age_days=180, today=date(2026, 11, 22))
    error_codes = {issue.code for issue in report.errors}
    warning_codes = {issue.code for issue in report.warnings}

    assert "INVALID_ENUM" in error_codes
    assert "MISSING_SECTION" in error_codes
    assert "BROKEN_RELATED_ID" in error_codes
    assert "ID_DOMAIN_MISMATCH" in error_codes
    assert "FILENAME_MISMATCH" in error_codes
    assert "STALE_PLAYBOOK" in warning_codes


def test_validator_catches_subcategory_and_relative_md_link_issues(tmp_path: Path) -> None:
    _copy_taxonomy(tmp_path)
    p1 = tmp_path / "playbooks" / "01_Identity_AD_Entra" / "id-001-lockout.md"
    p2 = tmp_path / "playbooks" / "01_Identity_AD_Entra" / "id-002-second.md"

    raw_p1 = _valid_playbook_content(
        pb_id="id-001",
        extra_body="\n## Cross-Subject Escalation & Pivot Links\n- **Broken:** [Missing](../04_Network_VPN_VoIP/missing.md)\n",
    ).replace(
        'subject: "Identity / AD & Entra ID"\n',
        'subject: "Identity / AD & Entra ID"\nsubcategory: nonexistent_subcat\n',
    )
    p1.write_text(raw_p1, encoding="utf-8")

    raw_p2 = _valid_playbook_content(
        pb_id="id-002",
        related_ids="[]",
        extra_body=(
            "\n## Cross-Subject Escalation & Pivot Links\n"
            "- **Unsynced:** [Lockout](./id-001-lockout.md)\n"
            "- **Self:** [Self](./id-002-second.md)\n"
        ),
    ).replace(
        'subject: "Identity / AD & Entra ID"\n',
        'subject: "Identity / AD & Entra ID"\nsubcategory: lockout_mfa_recovery\n',
    )
    p2.write_text(raw_p2, encoding="utf-8")

    report = validate_repository(tmp_path, max_age_days=180, today=date(2026, 11, 22))
    error_codes = {issue.code for issue in report.errors}
    warning_codes = {issue.code for issue in report.warnings}

    assert "INVALID_SUBCATEGORY" in error_codes
    assert "BROKEN_MD_LINK" in error_codes
    assert "UNSYNCED_MD_LINK" in warning_codes
    assert "SELF_MD_LINK" in warning_codes
