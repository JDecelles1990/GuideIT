"""CLI entrypoint to search GuideIT playbooks by EN/FR symptom, error code, or facets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from guideit_master.guideit.search import list_facets, search_playbooks  # noqa: E402
from guideit_master.paths import get_bundle_dir, get_guideit_db_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Search GuideIT playbooks via EN/FR taxonomy expansion and SQLite FTS5."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="Symptom text, error code, or playbook ID (optional when filtering or listing facets).",
    )
    parser.add_argument("--domain", help="Filter by domain folder (e.g., 01_Identity_AD_Entra).")
    parser.add_argument("--subcategory", help="Filter by domain subcategory id.")
    parser.add_argument("--tier", choices=["L1", "L2", "L3"], help="Filter by highest tier.")
    parser.add_argument("--os", dest="os_filter", help="Filter by OS (e.g., windows, macos, ios).")
    parser.add_argument("--env", dest="env_filter", help="Filter by environment (e.g., m365, intune).")
    parser.add_argument(
        "--risk", dest="risk_level", choices=["low", "medium", "high"], help="Filter by risk level."
    )
    parser.add_argument("--limit", type=int, default=5, help="Maximum hits to return (default: 5).")
    parser.add_argument(
        "--db",
        type=Path,
        default=get_guideit_db_path(),
        help="SQLite index path (default: data/guideit.db).",
    )
    parser.add_argument("--list-facets", action="store_true", help="List available facet filter values.")
    parser.add_argument("--json", action="store_true", help="Output results as JSON.")
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

        response = search_playbooks(
            args.db,
            args.query,
            root_dir=bundle_dir,
            domain=args.domain,
            subcategory=args.subcategory,
            tier=args.tier,
            os_filter=args.os_filter,
            env_filter=args.env_filter,
            risk_level=args.risk_level,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"[INDEX ERROR] {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(response.to_dict(), indent=2, ensure_ascii=False))
        return 0

    if response.total_hits == 0:
        print(f"[NO PLAYBOOK MATCH] No playbooks matched query: {args.query!r}")
        if response.expanded_tags:
            print(f"Expanded tags: {', '.join(response.expanded_tags)}")
        return 0

    print(
        f"Found {response.total_hits} match(es) for {args.query!r}"
        + (f" [tags: {', '.join(response.expanded_tags)}]" if response.expanded_tags else "")
    )
    for idx, hit in enumerate(response.hits, start=1):
        codes = ", ".join(hit.error_codes) if hit.error_codes else "none"
        print(
            f"{idx}. [{hit.id}] {hit.title} ({hit.tier} | risk={hit.risk_level} | score={hit.score})\n"
            f"   Path: {hit.path}\n"
            f"   Codes: {codes} | OS: {', '.join(hit.os)} | Match: {', '.join(hit.matched_reasons)}"
        )
        if hit.triage_summary:
            print(f"   Triage: {hit.triage_summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
