"""Unified bilingual EN/FR FTS5 search across GuideIT playbooks and PowerShellStore scripts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from guideit_master.guideit.models import SearchHit
from guideit_master.guideit.search import _build_safe_fts_query, _fts_term, search_playbooks
from guideit_master.guideit.taxonomy import (
    expand_query,
    extract_search_tokens,
    load_taxonomy,
    normalize_text,
)
from guideit_master.paths import (
    get_bundle_dir,
    get_guideit_db_path,
    get_psstore_db_path,
    get_taxonomy_dir,
)
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo, ScriptRecord
from guideit_master.services.cross_link_service import CrossLinkService

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.\-]*")


@dataclass(slots=True)
class ScriptSearchHit:
    """Ranked PowerShell script match returned by unified FTS5 search."""

    relative_path: str
    title: str
    category: str
    filename: str
    synopsis: str
    risk_level: str
    ps_edition: str
    requires_admin: bool
    timeout_seconds: int
    score: float
    matched_reasons: list[str] = field(default_factory=list)
    linked_playbook_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class UnifiedSearchResponse:
    """Combined search results across GuideIT playbooks and PowerShellStore scripts."""

    query: str
    expanded_tags: list[str]
    suggested_domains: list[str]
    total_playbook_hits: int
    total_script_hits: int
    playbook_hits: list[SearchHit]
    script_hits: list[ScriptSearchHit]

    def to_dict(self) -> dict[str, object]:
        return {
            "query": self.query,
            "expanded_tags": self.expanded_tags,
            "suggested_domains": self.suggested_domains,
            "total_hits": self.total_playbook_hits,
            "total_playbook_hits": self.total_playbook_hits,
            "total_script_hits": self.total_script_hits,
            "hits": [hit.to_dict() for hit in self.playbook_hits],
            "script_hits": [hit.to_dict() for hit in self.script_hits],
        }


def _resolve_taxonomy_root(db_path: Path, root_dir: Path | None) -> Path | None:
    if root_dir is not None and (get_taxonomy_dir(root_dir) / "keyword_map.json").is_file():
        return root_dir
    for candidate in (db_path.parent.parent, db_path.parent, get_bundle_dir(), Path.cwd()):
        if (get_taxonomy_dir(candidate) / "keyword_map.json").is_file():
            return candidate
    return None


def search_all(
    query: str,
    *,
    guideit_db_path: Path | None = None,
    catalog_repo: CatalogRepo | None = None,
    psstore_db_path: Path | None = None,
    root_dir: Path | None = None,
    domain: str | None = None,
    subcategory: str | None = None,
    tier: str | None = None,
    os_filter: str | None = None,
    env_filter: str | None = None,
    risk_level: str | None = None,
    playbook_limit: int = 10,
    script_limit: int = 10,
    include_playbooks: bool = True,
    include_scripts: bool = True,
    require_playbook_db: bool = False,
    include_all_scripts_on_empty: bool = False,
) -> UnifiedSearchResponse:
    """Search both playbooks_fts and scripts_fts with bilingual EN/FR expansion."""
    pb_db = (
        guideit_db_path.resolve() if guideit_db_path is not None else get_guideit_db_path()
    )
    resolved_root = _resolve_taxonomy_root(pb_db, root_dir)

    expanded_tags: list[str] = []
    suggested_domains: list[str] = []
    matched_codes: list[str] = []
    if resolved_root is not None:
        taxonomy = load_taxonomy(resolved_root)
        expanded_tags, suggested_domains, matched_codes = expand_query(query, taxonomy)

    playbook_hits: list[SearchHit] = []
    total_playbook_hits = 0
    boost_playbooks: list[SearchHit] = []

    if pb_db.is_file():
        pb_resp = search_playbooks(
            pb_db,
            query,
            root_dir=resolved_root,
            domain=domain,
            subcategory=subcategory,
            tier=tier,
            os_filter=os_filter,
            env_filter=env_filter,
            risk_level=risk_level,
            limit=max(playbook_limit, 5) if playbook_limit > 0 else 0,
        )
        expanded_tags = pb_resp.expanded_tags
        suggested_domains = pb_resp.suggested_domains
        boost_playbooks = pb_resp.hits[:5]
        if include_playbooks:
            total_playbook_hits = pb_resp.total_hits
            playbook_hits = (
                pb_resp.hits[:playbook_limit] if playbook_limit > 0 else pb_resp.hits
            )
    elif require_playbook_db and include_playbooks:
        # Delegate to search_playbooks so callers receive the canonical missing-index message.
        search_playbooks(pb_db, query, root_dir=resolved_root)

    if not include_scripts:
        return UnifiedSearchResponse(
            query=query,
            expanded_tags=expanded_tags,
            suggested_domains=suggested_domains,
            total_playbook_hits=total_playbook_hits,
            total_script_hits=0,
            playbook_hits=playbook_hits,
            script_hits=[],
        )

    repo = catalog_repo
    if repo is None:
        target_ps_db = (
            psstore_db_path.resolve()
            if psstore_db_path is not None
            else get_psstore_db_path()
        )
        if target_ps_db.is_file():
            repo = CatalogRepo(db_path=target_ps_db)

    if repo is None:
        return UnifiedSearchResponse(
            query=query,
            expanded_tags=expanded_tags,
            suggested_domains=suggested_domains,
            total_playbook_hits=total_playbook_hits,
            total_script_hits=0,
            playbook_hits=playbook_hits,
            script_hits=[],
        )

    cross_link = CrossLinkService(guideit_db_path=pb_db, catalog_repo=repo)
    norm_query = normalize_text(query)
    raw_tokens = _TOKEN_RE.findall(norm_query)
    content_tokens = extract_search_tokens(query)

    if not raw_tokens and not expanded_tags and not matched_codes:
        if not include_all_scripts_on_empty:
            return UnifiedSearchResponse(
                query=query,
                expanded_tags=expanded_tags,
                suggested_domains=suggested_domains,
                total_playbook_hits=total_playbook_hits,
                total_script_hits=0,
                playbook_hits=playbook_hits,
                script_hits=[],
            )
        all_scripts = repo.get_all_scripts()
        hits_all = [
            ScriptSearchHit(
                relative_path=rec.relative_path,
                title=rec.title,
                category=rec.category,
                filename=rec.filename,
                synopsis=rec.synopsis or "",
                risk_level=rec.risk_level,
                ps_edition=rec.ps_edition,
                requires_admin=rec.requires_admin,
                timeout_seconds=rec.timeout_seconds,
                score=1.0,
                matched_reasons=["catalog_browse"],
                linked_playbook_ids=[
                    pb.id for pb in cross_link.get_playbooks_for_script(rec.relative_path)
                ],
            )
            for rec in all_scripts
        ]
        sliced = hits_all[:script_limit] if script_limit > 0 else hits_all
        return UnifiedSearchResponse(
            query=query,
            expanded_tags=expanded_tags,
            suggested_domains=suggested_domains,
            total_playbook_hits=total_playbook_hits,
            total_script_hits=len(hits_all),
            playbook_hits=playbook_hits,
            script_hits=sliced,
        )

    if not content_tokens and not expanded_tags and not matched_codes and not boost_playbooks:
        return UnifiedSearchResponse(
            query=query,
            expanded_tags=expanded_tags,
            suggested_domains=suggested_domains,
            total_playbook_hits=total_playbook_hits,
            total_script_hits=0,
            playbook_hits=playbook_hits,
            script_hits=[],
        )

    candidates: dict[str, tuple[ScriptRecord, float, list[str]]] = {}

    if content_tokens:
        and_terms = [t for t in (_fts_term(tok) for tok in content_tokens) if t]
        if and_terms:
            strict_expr = and_terms[0] if len(and_terms) == 1 else f"({' AND '.join(and_terms)})"
            for rec, fts_score in repo.search_scripts_fts(strict_expr, limit=50):
                candidates[rec.relative_path] = (rec, fts_score + 10.0, ["fts_bm25_and"])

    has_linked_boost = any(pb.linked_scripts for pb in boost_playbooks)
    if not candidates and not has_linked_boost:
        fallback_tokens: list[str] = list(content_tokens)
        for tag in expanded_tags:
            fallback_tokens.append(tag)
            for part in tag.split("_"):
                if len(part) >= 2:
                    fallback_tokens.append(part)
        for code in matched_codes:
            fallback_tokens.append(normalize_text(code))
        fts_expr = _build_safe_fts_query(fallback_tokens)
        if fts_expr:
            for rec, fts_score in repo.search_scripts_fts(fts_expr, limit=50):
                candidates[rec.relative_path] = (rec, fts_score, ["fts_bm25"])

    # Exact path match (e.g., user searches "04_Devices/Reset-PrintSpooler.ps1")
    norm_rel_guess = query.strip().replace("\\", "/")
    if "/" in norm_rel_guess:
        exact_rec = repo.get_script_by_path(norm_rel_guess)
        if exact_rec is not None:
            rec_cur, score_cur, reasons_cur = candidates.get(
                exact_rec.relative_path, (exact_rec, 0.0, [])
            )
            reasons_cur.append(f"exact_script:{exact_rec.relative_path}")
            candidates[exact_rec.relative_path] = (rec_cur, score_cur + 60.0, reasons_cur)

    # Boost scripts linked to top-matching playbooks (bridges FR/error-code queries to .ps1 scripts)
    if norm_query:
        for rank, pb_hit in enumerate(boost_playbooks):
            if not pb_hit.linked_scripts:
                continue
            boost = max(15.0, 45.0 - rank * 7.0)
            linked_map = repo.get_scripts_by_paths(pb_hit.linked_scripts)
            for rel_path, rec in linked_map.items():
                if rel_path in candidates:
                    existing_rec, cur_score, reasons = candidates[rel_path]
                    reasons_new = list(reasons)
                    reasons_new.append(f"linked_playbook:{pb_hit.id}")
                    candidates[rel_path] = (existing_rec, cur_score + boost, reasons_new)
                else:
                    candidates[rel_path] = (
                        rec,
                        boost,
                        [f"linked_playbook:{pb_hit.id}"],
                    )

    # Exact filename / title token boost
    scored_scripts: list[ScriptSearchHit] = []
    for rel_path, (rec, base_score, reasons) in candidates.items():
        score = base_score
        final_reasons = list(reasons)
        stem_norm = normalize_text(Path(rec.filename).stem)
        fname_norm = normalize_text(rec.filename)
        if norm_query and (
            norm_query == fname_norm
            or norm_query == stem_norm
            or fname_norm in norm_query
        ):
            score += 60.0
            final_reasons.append(f"exact_filename:{rec.filename}")

        linked_pb_ids = [
            pb.id for pb in cross_link.get_playbooks_for_script(rel_path)
        ]
        scored_scripts.append(
            ScriptSearchHit(
                relative_path=rec.relative_path,
                title=rec.title,
                category=rec.category,
                filename=rec.filename,
                synopsis=rec.synopsis or "",
                risk_level=rec.risk_level,
                ps_edition=rec.ps_edition,
                requires_admin=rec.requires_admin,
                timeout_seconds=rec.timeout_seconds,
                score=round(score, 4),
                matched_reasons=final_reasons,
                linked_playbook_ids=linked_pb_ids,
            )
        )

    scored_scripts.sort(key=lambda h: (-h.score, h.title.lower(), h.relative_path))
    limited_scripts = scored_scripts[:script_limit] if script_limit > 0 else scored_scripts
    return UnifiedSearchResponse(
        query=query,
        expanded_tags=expanded_tags,
        suggested_domains=suggested_domains,
        total_playbook_hits=total_playbook_hits,
        total_script_hits=len(scored_scripts),
        playbook_hits=playbook_hits,
        script_hits=limited_scripts,
    )
