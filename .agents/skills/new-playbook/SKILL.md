---
name: new-playbook
description: >-
  Use this skill when turning solved IT support ticket notes, incident summaries,
  or troubleshooting procedures into a validated, schema-compliant GuideIT playbook
  and rebuilding the SQLite FTS5 search index.
---

# Create a New GuideIT Playbook

Follow this procedure whenever capturing a new IT troubleshooting playbook from ticket notes or technician runbooks.

## Steps

1. **Scrub Client Data (Zero PII / Multi-Tenant Hygiene)**
   - Remove all real customer names, tenant domains, user emails/UPNs, non-documentation public IPs, tenant/object GUIDs, serial numbers, passwords, and tokens.
   - Replace with approved placeholders only (`contoso.com`, `example.com`, `jsmith@example.com`, `198.51.100.10`, `10.0.10.25`, `00000000-0000-0000-0000-000000000000`, `PC-LAB-01`).

2. **Check for Existing Coverage**
   - Run `python tools/search_cli.py "<key symptoms and error codes>" --json`.
   - If an atomic playbook already covers the same root cause, propose updating the existing file rather than creating a duplicate.

3. **Choose Domain & Assign Sequential ID**
   - Read [domains.json](../../../taxonomy/domains.json) and select the matching folder (`01_Identity_AD_Entra` through `09_Apps_LOB`).
   - List existing files in that folder to find the next sequential 3-digit ID (e.g., `id-002`).
   - Name the file `<id>-<kebab-slug>.md` (atomic: one root cause per file).

4. **Author Against Schema & Template**
   - Follow [schema.json](../../../taxonomy/schema.json) and [playbook-template.md](../../../templates/playbook-template.md).
   - Set `last_verified` to today's ISO date (`YYYY-MM-DD`).
   - Populate rich bilingual `keywords_en` and `keywords_fr` lists plus `snake_case` `tags`.
   - Separate non-destructive checks (`## Read-Only Diagnostics (L1-L2)` / `## Deep-Dive Investigation (L3)`) from state-changing actions (`## Remediation (Confirm Before Running)` prefixed with `[REMEDIATION — CONFIRM BEFORE RUNNING]`).
   - Include only verified, real commands and error codes.

5. **Update Synonym Map (When Helpful)**
   - If the ticket used vague or bilingual phrasing that helps future lookups, add or update an entry in [keyword_map.json](../../../taxonomy/keyword_map.json) mapping those phrases to the playbook's canonical `tags`.

6. **Validate & Re-Index (Mandatory)**
   ```powershell
   python tools/validate_playbooks.py --strict
   python tools/build_index.py
   ```
   - Fix every error or warning before finishing. Confirm `data/guideit.db` rebuilds with the new playbook count.
