"""CLI entrypoint to validate GuideIT playbooks, schema compliance, and PII rules."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from guideit_master.guideit.validator import validate_repository  # noqa: E402
from guideit_master.paths import get_bundle_dir  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Validate GuideIT playbooks, taxonomy schema, and multi-tenant redaction."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings (stale playbooks, unknown fields, uncovered tags) as non-zero exit.",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=180,
        help="Warn if last_verified is older than this many days (default: 180).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON validation report.",
    )
    args = parser.parse_args(argv)

    report = validate_repository(get_bundle_dir(), max_age_days=args.max_age_days)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(
            f"Checked {report.checked_files} playbook(s): "
            f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)."
        )
        for issue in report.issues:
            loc = f"{issue.path}:{issue.line}" if issue.line else issue.path
            print(f"[{issue.severity.upper()}] {issue.code} ({loc}): {issue.message}")

    passed = report.strict_ok if args.strict else report.ok
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
