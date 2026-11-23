"""Integration tests for SQLite FTS5 indexing and bilingual EN/FR search."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from guideit_master.guideit.indexer import SCHEMA_VERSION, build_index
from guideit_master.guideit.search import (
    ensure_index_current,
    get_domain_and_subcategory_counts,
    get_playbook_by_id,
    get_playbook_titles,
    list_facets,
    search_playbooks,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def built_db(tmp_path: Path) -> Path:
    expected_count = len(list((REPO_ROOT / "playbooks").glob("*/*.md")))
    assert expected_count >= 65
    db_path = tmp_path / "guideit.db"
    stats = build_index(REPO_ROOT, db_path=db_path)
    assert stats.indexed_count == expected_count
    assert db_path.is_file()
    return db_path


@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        ("0x0000011b", "prt-001"),
        ("4740", "id-001"),
        ("AADSTS53000", "mdm-001"),
        ("0x80042306", "srv-001"),
        ("ERR_TOO_MANY_REDIRECTS", "app-001"),
        ("550 5.7.26", "m365-004"),
        ("0x8004de40", "m365-005"),
        ("CREDSSP", "srv-003"),
        ("0xC1900101", "win-005"),
        ("80180014", "mdm-008"),
        ("1058", "id-004"),
        ("5722", "id-005"),
        ("0x80070035", "net-004"),
        ("NET::ERR_CERT_DATE_INVALID", "sec-003"),
        ("0xA00F4244", "win-007"),
        ("1020", "srv-012"),
        ("0xC004F074", "win-008"),
        ("ADOBE_LICENSE_ERR", "app-003"),
        ("AADSTS65001", "id-006"),
        ("AllocationFailed", "srv-013"),
        ("AuthorizationPermissionMismatch", "srv-014"),
        ("AttributeValueMustBeUnique", "id-008"),
        ("554 5.2.2", "m365-008"),
        ("NO_PROPOSAL_CHOSEN", "net-005"),
        ("18456", "srv-016"),
        ("SELF_SIGNED_CERT_IN_CHAIN", "app-004"),
    ],
)
def test_exact_error_code_ranking(built_db: Path, query: str, expected_id: str) -> None:
    res = search_playbooks(built_db, query, root_dir=REPO_ROOT)
    assert res.total_hits >= 1
    assert res.hits[0].id == expected_id


@pytest.mark.parametrize(
    ("query", "expected_id"),
    [
        ("compte verrouille", "id-001"),
        ("bloque en file", "prt-001"),
        ("hameconnage", "sec-001"),
        ("intune non conforme", "mdm-001"),
        ("sauvegarde echouee", "srv-001"),
        ("Outlook keeps asking for password", "m365-001"),
        ("server disk full", "srv-001"),
        ("mapped drive gone", "net-001"),
        ("bluetooth headphones won't connect", "prt-002"),
        ("ecouteurs bluetooth", "prt-002"),
        ("can't modify shared excel", "m365-002"),
        ("excel lecture seule", "m365-002"),
        ("lost modifications word", "m365-003"),
        ("modifications perdues excel", "m365-003"),
        ("google admin console", "id-002"),
        ("google cloud console error", "srv-002"),
        ("bitlocker recovery screen", "win-002"),
        ("ecran bleu", "win-003"),
        ("onedrive bloque", "m365-005"),
        ("second monitor not detected", "prt-003"),
        ("intune windows 11 upgrade", "win-005"),
        ("enroll new device intune", "mdm-008"),
        ("mac spinning beachball force quit", "mdm-003"),
        ("macos app blocked developer", "mdm-004"),
        ("mac startup disk full", "mdm-005"),
        ("mac recovery mode won't boot", "mdm-006"),
        ("mac connect network drive smb", "mdm-007"),
        ("systemd failed journalctl", "srv-004"),
        ("linux oom killer", "srv-005"),
        ("linux disk full inodes", "srv-006"),
        ("linux ssh permission denied", "srv-008"),
        ("ipmi raid degraded", "srv-009"),
        ("sfp optical rx power", "srv-010"),
        ("grub rescue emergency mode", "srv-011"),
        ("windows not activated", "win-008"),
        ("adobe acrobat license error", "app-003"),
        ("licence adobe acrobat introuvable", "app-003"),
        ("mxtoolbox", "m365-004"),
        ("virustotal", "sec-001"),
        ("developer app permissions entra", "id-006"),
        ("blocked outside canada", "id-007"),
        ("voyage hors canada bloque", "id-007"),
        ("azure vm won't boot rdp", "srv-013"),
    ],
)
def test_bilingual_accent_insensitive_and_synonym_expansion(
    built_db: Path,
    query: str,
    expected_id: str,
) -> None:
    res = search_playbooks(built_db, query, root_dir=REPO_ROOT)
    assert res.total_hits >= 1
    assert res.hits[0].id == expected_id


def test_faceted_filters_and_empty_query_browsing(built_db: Path) -> None:
    res = search_playbooks(
        built_db,
        "intune non conforme",
        root_dir=REPO_ROOT,
        os_filter="macos",
        tier="L2",
        env_filter="intune",
    )
    assert res.hits[0].id == "mdm-001"
    assert all(
        hit.tier == "L2" and "macos" in hit.os and "intune" in hit.environment
        for hit in res.hits
    )

    ios_res = search_playbooks(
        built_db,
        "intune non conforme",
        root_dir=REPO_ROOT,
        os_filter="ios",
        tier="L2",
        env_filter="intune",
    )
    assert [hit.id for hit in ios_res.hits] == ["mdm-001"]

    l3_only = search_playbooks(built_db, "", root_dir=REPO_ROOT, tier="L3", limit=50)
    assert {
        "sec-001",
        "srv-001",
        "srv-002",
        "win-003",
        "srv-005",
        "srv-009",
        "srv-011",
        "srv-012",
        "id-004",
    }.issubset({hit.id for hit in l3_only.hits})
    assert all(hit.tier == "L3" for hit in l3_only.hits)

    gw_only = search_playbooks(built_db, "", root_dir=REPO_ROOT, env_filter="google_workspace")
    assert {hit.id for hit in gw_only.hits} == {"id-002", "m365-004", "srv-002"}

    dc_only = search_playbooks(built_db, "", root_dir=REPO_ROOT, env_filter="datacenter", limit=50)
    assert {
        "srv-004",
        "srv-005",
        "srv-006",
        "srv-007",
        "srv-008",
        "srv-009",
        "srv-010",
        "srv-011",
    }.issubset({hit.id for hit in dc_only.hits})

    linux_only = search_playbooks(built_db, "", root_dir=REPO_ROOT, os_filter="linux", limit=50)
    assert len(linux_only.hits) >= 8

    azure_only = search_playbooks(built_db, "", root_dir=REPO_ROOT, env_filter="azure", limit=50)
    assert len(azure_only.hits) >= 4

    printers_sub = search_playbooks(
        built_db,
        "",
        root_dir=REPO_ROOT,
        domain="05_Printers_Devices",
        subcategory="printers_spooler_scan",
        limit=50,
    )
    assert {hit.id for hit in printers_sub.hits} == {"prt-001", "prt-004"}

    cloud_sub = search_playbooks(
        built_db,
        "",
        root_dir=REPO_ROOT,
        domain="08_Servers_Cloud_Infra",
        subcategory="cloud_azure_gcp_docker",
        limit=50,
    )
    assert {hit.id for hit in cloud_sub.hits} == {"srv-002", "srv-013", "srv-014", "srv-015"}


@pytest.mark.parametrize(
    "special_query",
    [
        "169.254",
        "id-001",
        "550 5.7.1",
        'Event: 4740 / (AD) - "lockout"',
        "OR AND NOT *",
    ],
)
def test_fts5_special_characters_do_not_crash(built_db: Path, special_query: str) -> None:
    res = search_playbooks(built_db, special_query, root_dir=REPO_ROOT)
    assert isinstance(res.hits, list)


def test_get_playbook_by_id_and_list_facets(built_db: Path) -> None:
    record = get_playbook_by_id(built_db, "id-001")
    assert record is not None
    assert record["id"] == "id-001"
    assert record["subcategory"] == "lockout_mfa_recovery"
    assert "## Fast Triage (Under 2 Minutes)" in str(record["body_markdown"])

    assert get_playbook_by_id(built_db, "does-not-exist") is None

    facets = list_facets(built_db)
    assert len(facets["domains"]) == 9
    assert facets["tiers"] == ["L1", "L2", "L3"]
    assert "macos" in facets["os"]
    assert "intune" in facets["environments"]
    assert "google_workspace" in facets["environments"]
    assert "datacenter" in facets["environments"]
    assert "azure" in facets["environments"]

    titles = get_playbook_titles(built_db)
    assert len(titles) >= 65
    assert "id-001" in titles and "prt-001" in titles


def test_ensure_index_current_and_domain_subcategory_counts(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    resolved = ensure_index_current(REPO_ROOT, db_path=db_path)
    assert resolved == db_path.resolve()
    assert db_path.is_file()

    domain_counts, subcat_counts, built_at = get_domain_and_subcategory_counts(db_path)
    assert sum(domain_counts.values()) >= 65
    assert len(domain_counts) == 9
    assert subcat_counts[("05_Printers_Devices", "printers_spooler_scan")] == 2
    assert built_at

    # Corrupt schema_version triggers automatic rebuild
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.execute("UPDATE index_meta SET value = '0' WHERE key = 'schema_version'")
        conn.commit()
    ensure_index_current(REPO_ROOT, db_path=db_path)
    with closing(sqlite3.connect(str(db_path))) as conn:
        row = conn.execute("SELECT value FROM index_meta WHERE key = 'schema_version'").fetchone()
    assert row is not None and row[0] == SCHEMA_VERSION
