---
name: audit-library
description: >-
  Use this skill when auditing the GuideIT playbook library for schema validity,
  multi-tenant PII/redaction leaks, stale verification dates, broken related_ids,
  uncovered keyword_map tags, or search index drift.
---

# Audit the GuideIT Playbook Library

Run a complete quality, security, and index health audit across `playbooks/` and `taxonomy/`.

## Steps

1. **Run Strict Validation & Index Rebuild**
   ```powershell
   python tools/validate_playbooks.py --strict --max-age-days 180 --json
   python tools/build_index.py
   ```

2. **Review Findings by Category**
   - **Schema & Structure Errors:** Missing YAML fields, invalid enums (`tier`, `os`, `environment`, `risk_level`), prefix/domain mismatches, duplicate IDs, missing required Markdown headings, or broken `related_ids`.
   - **Multi-Tenant PII / Redaction Violations:** Non-placeholder emails, public IPv4 addresses, raw GUIDs, or secret key headers (`PII_EMAIL`, `PII_PUBLIC_IP`, `PII_GUID`, `PII_SECRET`).
   - **Freshness Warnings (`STALE_PLAYBOOK`):** Playbooks whose `last_verified` date exceeds `180` days.
   - **Taxonomy Coverage Warnings (`UNCOVERED_TAG`):** Canonical tags in [keyword_map.json](../../../taxonomy/keyword_map.json) that have no matching playbook yet.

3. **Report & Remediate**
   - Summarize total playbooks checked, errors, warnings, and indexed count.
   - Prioritize fixing PII violations and schema errors first, then stale dates or broken links.
   - Re-run `python tools/validate_playbooks.py --strict` and `python tools/build_index.py` after any fixes to verify clean exit `0`.
