"""CLI entrypoint to search GuideIT playbooks and PowerShellStore scripts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from guideit_master.guideit.search import list_facets  # noqa: E402
from guideit_master.paths import (  # noqa: E402
    get_bundle_dir,
    get_guideit_db_path,
    get_ps_scripts_dir,
    get_psstore_db_path,
)
from guideit_master.psstore.repositories.catalog_repo import CatalogRepo  # noqa: E402
from guideit_master.psstore.services.scanner import ScriptScanner  # noqa: E402
from guideit_master.services.unified_search import search_all  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Search GuideIT playbooks & PowerShellStore scripts via EN/FR expansion and SQLite FTS5."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="Symptom text, error code, playbook ID, or script keyword.",
    )
    parser.add_argument("--domain", help="Filter by domain folder (e.g., 01_Identity_AD_Entra).")
    parser.add_argument("--subcategory", help="Filter by domain subcategory id.")
    parser.add_argument("--tier", choices=["L1", "L2", "L3"], help="Filter by highest tier.")
    parser.add_argument("--os", dest="os_filter", help="Filter by OS (e.g., windows, macos, ios).")
    parser.add_argument("--env", dest="env_filter", help="Filter by environment (e.g., m365, intune).")
    parser.add_argument(
        "--risk", dest="risk_level", choices=["low", "medium", "high"], help="Filter by risk level."
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum hits per type to return (default: 5).")
    parser.add_argument(
        "--db",
        type=Path,
        default=get_guideit_db_path(),
        help="GuideIT SQLite index path (default: data/guideit.db).",
    )
    parser.add_argument(
        "--ps-db",
        type=Path,
        default=get_psstore_db_path(),
        help="PowerShellStore SQLite catalog path (default: data/powershell_store.db).",
    )
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "--playbooks-only",
        action="store_true",
        help="Search only GuideIT playbooks.",
    )
    scope_group.add_argument(
        "--scripts-only",
        action="store_true",
        help="Search only PowerShellStore scripts.",
    )
    parser.add_argument("--list-facets", action="store_true", help="List available facet filter values.")
    parser.add_argument("--json", action="store_true", help="Output unified results as JSON.")
    args = parser.parse_args(argv)

    bundle_dir = get_bundle_dir()
    try:
        if args.list_facets:
            facets = list_facets(args.db)
            if args.json:
                print(json.dumps(facets, indent=2, ensure_ascii=False))
            else:
                for key, values in facets.items():
                    print(f"{key}: {', '.join(values)}")
            return 0

        ps_repo: CatalogRepo | None = None
        if not args.playbooks_only:
            ps_repo = CatalogRepo(db_path=args.ps_db)
            if not ps_repo.get_all_scripts():
                scripts_dir = get_ps_scripts_dir(bundle_dir)
                if scripts_dir.is_dir():
                    ScriptScanner(scripts_dir=scripts_dir, repo=ps_repo).sync_catalog()

        response = search_all(
            args.query,
            guideit_db_path=args.db,
            catalog_repo=ps_repo,
            root_dir=bundle_dir,
            domain=args.domain,
            subcategory=args.subcategory,
            tier=args.tier,
            os_filter=args.os_filter,
            env_filter=args.env_filter,
            risk_level=args.risk_level,
            playbook_limit=args.limit,
            script_limit=args.limit,
            include_playbooks=not args.scripts_only,
            include_scripts=not args.playbooks_only,
            require_playbook_db=not args.scripts_only,
        )
    except FileNotFoundError as exc:
        print(f"[INDEX ERROR] {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if not args.scripts_only:
        if response.total_playbook_hits == 0:
            print(f"[NO PLAYBOOK MATCH] No playbooks matched query: {args.query!r}")
            if response.expanded_tags:
                print(f"Expanded tags: {', '.join(response.expanded_tags)}")
        else:
            print(
                f"Found {response.total_playbook_hits} playbook match(es) for {args.query!r}"
                + (
                    f" [tags: {', '.join(response.expanded_tags)}]"
                    if response.expanded_tags
                    else ""
                )
            )
            for idx, hit in enumerate(response.playbook_hits, start=1):
                codes = ", ".join(hit.error_codes) if hit.error_codes else "none"
                print(
                    f"{idx}. [{hit.id}] {hit.title} ({hit.tier} | risk={hit.risk_level} | score={hit.score})\n"
                    f"   Path: {hit.path}\n"
                    f"   Codes: {codes} | OS: {', '.join(hit.os)} | Match: {', '.join(hit.matched_reasons)}"
                )
                if hit.linked_scripts:
                    print(f"   Linked Scripts: {', '.join(hit.linked_scripts)}")
                if hit.triage_summary:
                    print(f"   Triage: {hit.triage_summary}")

    if not args.playbooks_only:
        if response.total_script_hits == 0:
            if args.scripts_only:
                print(f"[NO SCRIPT MATCH] No PowerShell scripts matched query: {args.query!r}")
        else:
            print(
                f"\nMatching PowerShell Scripts ({response.total_script_hits}):"
                if not args.scripts_only
                else f"Found {response.total_script_hits} PowerShell script(s) for {args.query!r}:"
            )
            for idx, shit in enumerate(response.script_hits, start=1):
                admin_tag = "admin" if shit.requires_admin else "user"
                pb_tag = (
                    f" | Playbooks: {', '.join(shit.linked_playbook_ids)}"
                    if shit.linked_playbook_ids
                    else ""
                )
                print(
                    f"{idx}. {shit.title} ({shit.risk_level} | {admin_tag} | score={shit.score})\n"
                    f"   Script: {shit.relative_path}{pb_tag}\n"
                    f"   Match: {', '.join(shit.matched_reasons)}"
                )
                if shit.synopsis:
                    print(f"   Synopsis: {shit.synopsis}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
