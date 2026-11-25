"""Hybrid EN/FR search API over the GuideIT SQLite FTS5 index."""

from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from guideit_master.guideit.indexer import SCHEMA_VERSION, build_index, compute_corpus_hash
from guideit_master.guideit.models import SearchHit, SearchResponse
from guideit_master.guideit.taxonomy import (
    TaxonomyConfig,
    expand_query,
    extract_search_tokens,
    load_taxonomy,
    normalize_text,
)
from guideit_master.paths import get_bundle_dir, get_guideit_db_path, get_taxonomy_dir

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.\-]*")


def _fts_term(tok: str) -> str:
    """Format a single token for FTS5 MATCH with safe prefix matching for long words."""
    cleaned = tok.strip().strip('"')
    if not cleaned:
        return ""
    if cleaned.isalpha() and len(cleaned) >= 5:
        return f'"{cleaned}"*'
    return f'"{cleaned}"'


def _build_safe_fts_query(tokens: list[str]) -> str:
    """Wrap every normalized token in double quotes so FTS5 operators cannot fail."""
    seen: list[str] = []
    for tok in tokens:
        cleaned = tok.strip().strip('"')
        if not cleaned or cleaned in seen:
            continue
        seen.append(cleaned)
    return " OR ".join(f'"{t}"' for t in seen)


def _build_strict_fts_query(
    content_tokens: list[str],
    expanded_tags: list[str],
    matched_codes: list[str],
) -> str:
    """Require all content tokens together OR match column-scoped taxonomy tags/codes."""
    clauses: list[str] = []
    if content_tokens:
        terms = [t for t in (_fts_term(tok) for tok in content_tokens) if t]
        if terms:
            clauses.append(terms[0] if len(terms) == 1 else f"({' AND '.join(terms)})")

    seen_clauses = set(clauses)
    for tag in expanded_tags:
        cleaned = tag.strip().strip('"')
        if cleaned:
            clause = f'tags : "{cleaned}"'
            if clause not in seen_clauses:
                seen_clauses.add(clause)
                clauses.append(clause)

    for code in matched_codes:
        cleaned = normalize_text(code).strip().strip('"')
        if cleaned:
            clause = f'error_codes : "{cleaned}"'
            if clause not in seen_clauses:
                seen_clauses.add(clause)
                clauses.append(clause)

    return " OR ".join(clauses)


def _build_relaxed_fts_query(
    content_tokens: list[str],
    expanded_tags: list[str],
    matched_codes: list[str],
) -> str:
    """Fallback OR query over content tokens plus column-scoped tags/codes."""
    clauses: list[str] = []
    seen: set[str] = set()
    for tok in content_tokens:
        term = _fts_term(tok)
        if term and term not in seen:
            seen.add(term)
            clauses.append(term)
    for tag in expanded_tags:
        cleaned = tag.strip().strip('"')
        if cleaned:
            clause = f'tags : "{cleaned}"'
            if clause not in seen:
                seen.add(clause)
                clauses.append(clause)
    for code in matched_codes:
        cleaned = normalize_text(code).strip().strip('"')
        if cleaned:
            clause = f'error_codes : "{cleaned}"'
            if clause not in seen:
                seen.add(clause)
                clauses.append(clause)
    return " OR ".join(clauses)


def _token_matches_text(tok: str, norm_text: str) -> bool:
    """Match token on word boundary (allowing prefix stems for alpha words len >= 5)."""
    if not tok or not norm_text:
        return False
    escaped = re.escape(tok)
    if tok.isalpha() and len(tok) >= 5:
        pattern = rf"(?<![a-z0-9_]){escaped}[a-z0-9_]*"
    else:
        pattern = rf"(?<![a-z0-9_]){escaped}(?![a-z0-9_])"
    return re.search(pattern, norm_text) is not None


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
                hash_row = conn.execute(
                    "SELECT value FROM index_meta WHERE key = 'source_hash'"
                ).fetchone()
                cols = {row[1] for row in conn.execute("PRAGMA table_info(playbooks)").fetchall()}
                expected_hash = compute_corpus_hash(resolved_root)
                if (
                    ver_row is None
                    or str(ver_row[0]) != SCHEMA_VERSION
                    or hash_row is None
                    or str(hash_row[0]) != expected_hash
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

    content_tokens = extract_search_tokens(query)
    if not content_tokens and not expanded_tags and not matched_codes_from_map:
        return SearchResponse(
            query=query,
            expanded_tags=expanded_tags,
            suggested_domains=suggested_domains,
            total_hits=0,
            hits=[],
        )

    strict_expr = _build_strict_fts_query(content_tokens, expanded_tags, matched_codes_from_map)
    relaxed_expr = _build_relaxed_fts_query(content_tokens, expanded_tags, matched_codes_from_map)

    fts_sql = """
        SELECT
            p.*,
            -bm25(playbooks_fts, 10.0, 12.0, 8.0, 6.0, 6.0, 5.0, 3.0, 1.0) AS fts_score
        FROM playbooks_fts
        JOIN playbooks p ON p.id = playbooks_fts.id
        WHERE playbooks_fts MATCH ?
    """

    def _run_and_filter(expr: str) -> list[sqlite3.Row]:
        if not expr:
            return []
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.row_factory = sqlite3.Row
            fetched = conn.execute(fts_sql, (expr,)).fetchall()
        return [
            r
            for r in fetched
            if _row_matches_facets(
                r,
                domain=domain,
                subcategory=subcategory,
                tier=tier,
                os_filter=os_filter,
                env_filter=env_filter,
                risk_level=risk_level,
            )
        ]

    matched_rows = _run_and_filter(strict_expr)
    used_relaxed_fallback = False
    if not matched_rows and relaxed_expr and relaxed_expr != strict_expr:
        matched_rows = _run_and_filter(relaxed_expr)
        used_relaxed_fallback = True

    scored_candidates: list[tuple[SearchHit, bool, bool, int, int]] = []
    expanded_tag_set = set(expanded_tags)
    suggested_domain_set = set(suggested_domains)

    for row in matched_rows:
        score = max(0.0, float(row["fts_score"]))
        reasons: list[str] = []
        has_exact_id = False
        has_error_code = False
        has_expanded_tag = False
        has_kw_phrase = False

        pb_id = str(row["id"])
        pb_id_norm = normalize_text(pb_id)
        if pb_id_norm in raw_tokens or pb_id_norm == norm_query:
            score += 100.0
            has_exact_id = True
            reasons.append(f"exact_id:{pb_id}")

        pb_codes = json.loads(row["error_codes_json"])
        for code in pb_codes:
            code_norm = normalize_text(str(code))
            if code_norm and (
                code_norm in raw_tokens
                or re.search(rf"(?<![a-z0-9_]){re.escape(code_norm)}(?![a-z0-9_])", norm_query)
            ):
                score += 80.0
                has_error_code = True
                reasons.append(f"error_code:{code}")

        pb_tags = json.loads(row["tags_json"])
        for tag in pb_tags:
            if tag in expanded_tag_set:
                score += 30.0
                has_expanded_tag = True
                reasons.append(f"tag:{tag}")

        pb_keywords = json.loads(row["keywords_en_json"]) + json.loads(row["keywords_fr_json"])
        for kw in pb_keywords:
            kw_norm = normalize_text(str(kw))
            if kw_norm and re.search(
                rf"(?<![a-z0-9_]){re.escape(kw_norm)}(?![a-z0-9_])",
                norm_query,
            ):
                score += 45.0 if kw_norm == norm_query else 25.0
                has_kw_phrase = True
                reasons.append(f"keyword:{kw}")

        # Token-level precision scoring in title, keywords, tags, and tools
        title_norm = normalize_text(str(row["title"]))
        kw_blob_norm = normalize_text(" ".join(str(k) for k in pb_keywords))
        tags_blob_norm = normalize_text(" ".join(str(t).replace("_", " ") for t in pb_tags))
        meta_kw_tags = f"{kw_blob_norm} {tags_blob_norm}".strip()
        tools_norm = normalize_text(" ".join(str(t) for t in json.loads(row["tools_json"])))
        non_pivot_body = re.split(
            r"(?im)^##\s+(?:cross-subject|escalation\s*&\s*pivot)",
            str(row["body_markdown"]),
            maxsplit=1,
        )[0]
        full_searchable_norm = normalize_text(
            f"{title_norm} {meta_kw_tags} {tools_norm} {non_pivot_body}"
        )

        meta_hits = 0
        total_token_hits = 0
        for tok in content_tokens:
            matched_meta = False
            if _token_matches_text(tok, title_norm):
                score += 12.0
                meta_hits += 1
                matched_meta = True
                reasons.append(f"title_tok:{tok}")
            elif _token_matches_text(tok, meta_kw_tags):
                score += 9.0
                meta_hits += 1
                matched_meta = True
                reasons.append(f"kw_tok:{tok}")
            elif _token_matches_text(tok, tools_norm):
                score += 6.0
                meta_hits += 1
                matched_meta = True
                reasons.append(f"tool_tok:{tok}")

            if matched_meta or _token_matches_text(tok, full_searchable_norm):
                total_token_hits += 1

        if len(content_tokens) >= 2:
            if meta_hits == len(content_tokens):
                score += 15.0
            if total_token_hits == len(content_tokens):
                score += 6.0

        is_strong = (
            has_exact_id
            or has_error_code
            or has_expanded_tag
            or has_kw_phrase
            or meta_hits >= 1
        )
        is_explicit_high = (
            has_exact_id
            or has_error_code
            or has_expanded_tag
            or has_kw_phrase
            or (bool(content_tokens) and meta_hits == len(content_tokens))
        )

        if str(row["domain"]) in suggested_domain_set and (
            has_expanded_tag or has_error_code or has_kw_phrase or meta_hits >= 1
        ):
            score += 5.0
            reasons.append(f"domain:{row['domain']}")

        if not reasons:
            reasons.append("fts_bm25")

        hit = _row_to_hit(row, score=score, matched_reasons=reasons)
        scored_candidates.append((hit, is_strong, is_explicit_high, meta_hits, total_token_hits))

    if used_relaxed_fallback and len(content_tokens) >= 2 and scored_candidates:
        max_tok_hits = max(item[4] for item in scored_candidates)
        if max_tok_hits >= 2:
            scored_candidates = [
                item
                for item in scored_candidates
                if item[4] >= 2 or item[1]
            ]

    if scored_candidates:
        any_strong = any(item[1] for item in scored_candidates)
        any_explicit_high = any(item[2] for item in scored_candidates)
        top_score = max(item[0].score for item in scored_candidates)
        if any_strong:
            scored_candidates = [
                item
                for item in scored_candidates
                if item[1] or (not any_explicit_high and item[0].score >= top_score * 0.25)
            ]

    scored_hits = [item[0] for item in scored_candidates]
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
