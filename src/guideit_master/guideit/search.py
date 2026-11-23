"""Hybrid EN/FR search API over the GuideIT SQLite FTS5 index."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from guideit_master.guideit.indexer import SCHEMA_VERSION, build_index
from guideit_master.guideit.models import SearchHit, SearchResponse
from guideit_master.guideit.taxonomy import TaxonomyConfig, expand_query, load_taxonomy, normalize_text
from guideit_master.paths import get_bundle_dir, get_guideit_db_path, get_taxonomy_dir

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.\-]*")


def _build_safe_fts_query(tokens: list[str]) -> str:
    """Wrap every normalized token in double quotes so FTS5 operators cannot fail."""
    seen: list[str] = []
    for tok in tokens:
        cleaned = tok.strip().strip('"')
        if not cleaned or cleaned in seen:
            continue
        seen.append(cleaned)
    return " OR ".join(f'"{t}"' for t in seen)


def _infer_root_dir(db_path: Path, root_dir: Path | None) -> Path | None:
    """Locate repository root containing taxonomy/ relative to db_path or bundle root."""
    if root_dir is not None:
        return root_dir
    for candidate in (db_path.parent.parent, db_path.parent, get_bundle_dir(), Path.cwd()):
        if (get_taxonomy_dir(candidate) / "keyword_map.json").is_file():
            return candidate
    return None


def ensure_index_current(
    root_dir: Path | None = None,
    db_path: Path | None = None,
) -> Path:
    """Verify the SQLite index exists and matches SCHEMA_VERSION, rebuilding if needed."""
    resolved_root = (root_dir if root_dir is not None else get_bundle_dir()).resolve()
    target_db = db_path.resolve() if db_path is not None else get_guideit_db_path()

    needs_build = not target_db.is_file()
    if not needs_build:
        try:
            with closing(sqlite3.connect(str(target_db))) as conn:
                ver_row = conn.execute(
                    "SELECT value FROM index_meta WHERE key = 'schema_version'"
                ).fetchone()
                cols = {row[1] for row in conn.execute("PRAGMA table_info(playbooks)").fetchall()}
                if (
                    ver_row is None
                    or str(ver_row[0]) != SCHEMA_VERSION
                    or "subcategory" not in cols
                    or "linked_scripts_json" not in cols
                ):
                    needs_build = True
        except sqlite3.DatabaseError:
            needs_build = True

    if needs_build:
        build_index(resolved_root, db_path=target_db)
    return target_db


def get_domain_and_subcategory_counts(
    db_path: Path,
) -> tuple[dict[str, int], dict[tuple[str, str], int], str]:
    """Query domain counts, subcategory counts, and index build timestamp from SQLite."""
    if not db_path.is_file():
        return {}, {}, ""
    domain_counts: dict[str, int] = {}
    subcategory_counts: dict[tuple[str, str], int] = {}
    built_at = ""
    with closing(sqlite3.connect(str(db_path))) as conn:
        for domain, cnt in conn.execute(
            "SELECT domain, COUNT(*) FROM playbooks GROUP BY domain"
        ).fetchall():
            domain_counts[str(domain)] = int(cnt)
        for domain, subcat, cnt in conn.execute(
            "SELECT domain, subcategory, COUNT(*) FROM playbooks GROUP BY domain, subcategory"
        ).fetchall():
            if subcat:
                subcategory_counts[(str(domain), str(subcat))] = int(cnt)
        row = conn.execute(
            "SELECT value FROM index_meta WHERE key = 'built_at'"
        ).fetchone()
        if row:
            built_at = str(row[0])
    return domain_counts, subcategory_counts, built_at


def _row_matches_facets(
    row: sqlite3.Row,
    *,
    domain: str | None,
    subcategory: str | None,
    tier: str | None,
    os_filter: str | None,
    env_filter: str | None,
    risk_level: str | None,
) -> bool:
    """Apply faceted metadata filters on a SQLite row."""
    if domain and str(row["domain"]).lower() != domain.lower():
        return False
    if subcategory:
        row_subcat = str(row["subcategory"]) if "subcategory" in row.keys() else ""
        if row_subcat.lower() != subcategory.lower():
            return False
    if tier and str(row["tier"]).upper() != tier.upper():
        return False
    if risk_level and str(row["risk_level"]).lower() != risk_level.lower():
        return False
    if os_filter:
        os_values = [str(v).lower() for v in json.loads(row["os_json"])]
        if os_filter.lower() not in os_values:
            return False
    if env_filter:
        env_values = [str(v).lower() for v in json.loads(row["environment_json"])]
        if env_filter.lower() not in env_values:
            return False
    return True


def _row_to_hit(
    row: sqlite3.Row,
    *,
    score: float,
    matched_reasons: list[str],
) -> SearchHit:
    return SearchHit(
        id=str(row["id"]),
        path=str(row["path"]),
        domain=str(row["domain"]),
        subject=str(row["subject"]),
        subcategory=str(row["subcategory"]) if "subcategory" in row.keys() else "",
        title=str(row["title"]),
        tier=str(row["tier"]),
        risk_level=str(row["risk_level"]),
        requires_admin=bool(row["requires_admin"]),
        os=json.loads(row["os_json"]),
        environment=json.loads(row["environment_json"]),
        tags=json.loads(row["tags_json"]),
        error_codes=json.loads(row["error_codes_json"]),
        tools=json.loads(row["tools_json"]),
        last_verified=str(row["last_verified"]),
        triage_summary=str(row["triage_summary"]),
        score=round(score, 4),
        matched_reasons=matched_reasons,
        linked_scripts=(
            json.loads(row["linked_scripts_json"])
            if "linked_scripts_json" in row.keys()
            else []
        ),
    )


def search_playbooks(
    db_path: Path,
    query: str,
    *,
    root_dir: Path | None = None,
    domain: str | None = None,
    subcategory: str | None = None,
    tier: str | None = None,
    os_filter: str | None = None,
    env_filter: str | None = None,
    risk_level: str | None = None,
    limit: int = 10,
) -> SearchResponse:
    """Search indexed playbooks using EN/FR taxonomy expansion, FTS5 BM25, and exact code boosts."""
    if not db_path.is_file():
        raise FileNotFoundError(
            f"Search index not found at '{db_path}'. Run 'python tools/build_index.py' first."
        )

    resolved_root = _infer_root_dir(db_path, root_dir)
    taxonomy: TaxonomyConfig | None = None
    expanded_tags: list[str] = []
    suggested_domains: list[str] = []
    matched_codes_from_map: list[str] = []

    if resolved_root is not None:
        taxonomy = load_taxonomy(resolved_root)
        expanded_tags, suggested_domains, matched_codes_from_map = expand_query(query, taxonomy)

    norm_query = normalize_text(query)
    raw_tokens = _TOKEN_RE.findall(norm_query)

    # Filter-only browsing mode when query has no searchable tokens
    if not raw_tokens and not expanded_tags and not matched_codes_from_map:
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM playbooks ORDER BY id ASC").fetchall()

        filtered_hits = [
            _row_to_hit(row, score=1.0, matched_reasons=["facet_filter"])
            for row in rows
            if _row_matches_facets(
                row,
                domain=domain,
                subcategory=subcategory,
                tier=tier,
                os_filter=os_filter,
                env_filter=env_filter,
                risk_level=risk_level,
            )
        ]
        return SearchResponse(
            query=query,
            expanded_tags=expanded_tags,
            suggested_domains=suggested_domains,
            total_hits=len(filtered_hits),
            hits=filtered_hits[:limit] if limit > 0 else filtered_hits,
        )

    fts_tokens = list(raw_tokens)
    for tag in expanded_tags:
        fts_tokens.append(tag)
    for code in matched_codes_from_map:
        fts_tokens.append(normalize_text(code))

    fts_expr = _build_safe_fts_query(fts_tokens)

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                p.*,
                -bm25(playbooks_fts, 10.0, 12.0, 8.0, 6.0, 6.0, 5.0, 3.0, 1.0) AS fts_score
            FROM playbooks_fts
            JOIN playbooks p ON p.id = playbooks_fts.id
            WHERE playbooks_fts MATCH ?
            """,
            (fts_expr,),
        ).fetchall()

    scored_hits: list[SearchHit] = []
    expanded_tag_set = set(expanded_tags)
    suggested_domain_set = set(suggested_domains)

    for row in rows:
        if not _row_matches_facets(
            row,
            domain=domain,
            subcategory=subcategory,
            tier=tier,
            os_filter=os_filter,
            env_filter=env_filter,
            risk_level=risk_level,
        ):
            continue

        score = max(0.0, float(row["fts_score"]))
        reasons: list[str] = []

        pb_id = str(row["id"])
        pb_id_norm = normalize_text(pb_id)
        if pb_id_norm in raw_tokens or pb_id_norm == norm_query:
            score += 100.0
            reasons.append(f"exact_id:{pb_id}")

        pb_codes = json.loads(row["error_codes_json"])
        for code in pb_codes:
            code_norm = normalize_text(str(code))
            if code_norm and (
                code_norm in raw_tokens
                or re.search(rf"(?<![a-z0-9_]){re.escape(code_norm)}(?![a-z0-9_])", norm_query)
            ):
                score += 80.0
                reasons.append(f"error_code:{code}")

        pb_tags = json.loads(row["tags_json"])
        for tag in pb_tags:
            if tag in expanded_tag_set:
                score += 25.0
                reasons.append(f"tag:{tag}")

        pb_keywords = json.loads(row["keywords_en_json"]) + json.loads(row["keywords_fr_json"])
        for kw in pb_keywords:
            kw_norm = normalize_text(str(kw))
            if kw_norm and re.search(
                rf"(?<![a-z0-9_]){re.escape(kw_norm)}(?![a-z0-9_])",
                norm_query,
            ):
                score += 20.0
                reasons.append(f"keyword:{kw}")

        if str(row["domain"]) in suggested_domain_set:
            score += 5.0
            reasons.append(f"domain:{row['domain']}")

        if not reasons:
            reasons.append("fts_bm25")

        scored_hits.append(_row_to_hit(row, score=score, matched_reasons=reasons))

    scored_hits.sort(key=lambda h: (-h.score, h.id))
    limited_hits = scored_hits[:limit] if limit > 0 else scored_hits
    return SearchResponse(
        query=query,
        expanded_tags=expanded_tags,
        suggested_domains=suggested_domains,
        total_hits=len(scored_hits),
        hits=limited_hits,
    )


def get_playbook_by_id(db_path: Path, playbook_id: str) -> dict[str, object] | None:
    """Return full playbook record including body_markdown for CLI or PySide6 viewer."""
    if not db_path.is_file():
        raise FileNotFoundError(
            f"Search index not found at '{db_path}'. Run 'python tools/build_index.py' first."
        )
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM playbooks WHERE id = ?", (playbook_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "path": str(row["path"]),
        "domain": str(row["domain"]),
        "subject": str(row["subject"]),
        "subcategory": str(row["subcategory"]) if "subcategory" in row.keys() else "",
        "title": str(row["title"]),
        "tier": str(row["tier"]),
        "risk_level": str(row["risk_level"]),
        "requires_admin": bool(row["requires_admin"]),
        "last_verified": str(row["last_verified"]),
        "os": json.loads(row["os_json"]),
        "environment": json.loads(row["environment_json"]),
        "tags": json.loads(row["tags_json"]),
        "error_codes": json.loads(row["error_codes_json"]),
        "keywords_en": json.loads(row["keywords_en_json"]),
        "keywords_fr": json.loads(row["keywords_fr_json"]),
        "tools": json.loads(row["tools_json"]),
        "related_ids": json.loads(row["related_ids_json"]),
        "linked_scripts": (
            json.loads(row["linked_scripts_json"])
            if "linked_scripts_json" in row.keys()
            else []
        ),
        "triage_summary": str(row["triage_summary"]),
        "body_markdown": str(row["body_markdown"]),
    }


def list_facets(db_path: Path) -> dict[str, list[str]]:
    """Return sorted distinct metadata values for PySide6 sidebar filters."""
    if not db_path.is_file():
        raise FileNotFoundError(
            f"Search index not found at '{db_path}'. Run 'python tools/build_index.py' first."
        )
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT domain, tier, risk_level, os_json, environment_json, tags_json FROM playbooks"
        ).fetchall()

    domains: set[str] = set()
    tiers: set[str] = set()
    risk_levels: set[str] = set()
    os_vals: set[str] = set()
    env_vals: set[str] = set()
    tags: set[str] = set()

    for row in rows:
        domains.add(str(row["domain"]))
        tiers.add(str(row["tier"]))
        risk_levels.add(str(row["risk_level"]))
        os_vals.update(str(v) for v in json.loads(row["os_json"]))
        env_vals.update(str(v) for v in json.loads(row["environment_json"]))
        tags.update(str(v) for v in json.loads(row["tags_json"]))

    return {
        "domains": sorted(domains),
        "tiers": sorted(tiers),
        "risk_levels": sorted(risk_levels),
        "os": sorted(os_vals),
        "environments": sorted(env_vals),
        "tags": sorted(tags),
    }


def get_playbook_titles(db_path: Path) -> dict[str, str]:
    """Return a {playbook_id: title} lookup dictionary for UI tooltips and cross-links."""
    if not db_path.is_file():
        return {}
    with closing(sqlite3.connect(str(db_path))) as conn:
        rows = conn.execute("SELECT id, title FROM playbooks ORDER BY id ASC").fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def get_playbook_script_links(db_path: Path) -> list[dict[str, object]]:
    """Return lightweight playbook metadata paired with linked_scripts for reverse lookups."""
    if not db_path.is_file():
        return []
    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        cols = {row[1] for row in conn.execute("PRAGMA table_info(playbooks)").fetchall()}
        if "linked_scripts_json" not in cols:
            return []
        rows = conn.execute(
            "SELECT id, title, domain, subject, tier, risk_level, path, linked_scripts_json "
            "FROM playbooks ORDER BY id ASC"
        ).fetchall()

    results: list[dict[str, object]] = []
    for row in rows:
        try:
            linked = [str(item) for item in json.loads(row["linked_scripts_json"])]
        except (TypeError, json.JSONDecodeError):
            linked = []
        results.append(
            {
                "id": str(row["id"]),
                "title": str(row["title"]),
                "domain": str(row["domain"]),
                "subject": str(row["subject"]),
                "tier": str(row["tier"]),
                "risk_level": str(row["risk_level"]),
                "path": str(row["path"]),
                "linked_scripts": linked,
            }
        )
    return results
