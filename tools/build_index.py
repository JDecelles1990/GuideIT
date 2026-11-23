"""CLI entrypoint to build or rebuild the GuideIT SQLite FTS5 search index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from guideit_master.guideit.indexer import build_index  # noqa: E402
from guideit_master.paths import get_bundle_dir, get_guideit_db_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Build the GuideIT SQLite FTS5 search index from playbooks/."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=get_guideit_db_path(),
        help="Target SQLite database path (default: data/guideit.db).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output build statistics as JSON.",
    )
    args = parser.parse_args(argv)

    stats = build_index(get_bundle_dir(), db_path=args.db)
    if args.json:
        print(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(
            f"Indexed {stats.indexed_count} playbook(s) into {stats.db_path} "
            f"(built_at={stats.built_at}, hash={stats.source_hash[:12]})."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
