---
name: triage-ticket
description: >-
  Use this skill when a technician pastes a helpdesk ticket, user symptom, log
  excerpt, or error code (in English or French) for live L1-L3 troubleshooting
  using the GuideIT playbook library.
---

# Live L1–L3 Ticket Triage Workflow

Use this workflow to route a live IT incident through GuideIT safely and deterministically.

## Steps

1. **Detect Language & Extract Signals**
   - Identify whether the pasted ticket is in English (`EN`) or French (`FR`) and match that language in your response.
   - Extract verbatim error codes (`4740`, `0x80070005`, `AADSTS50076`, `550 5.7.1`, etc.), affected OS/app, and symptom phrases.

2. **Query the FTS5 Playbook Index First**
   - Run:
     ```powershell
     python tools/search_cli.py "<extracted symptoms and error codes>" --json
     ```
   - Apply `--tier`, `--domain`, or `--os` flags if the ticket already narrows those down.
   - If `data/guideit.db` does not exist, run `python tools/build_index.py` or inspect [keyword_map.json](../../../taxonomy/keyword_map.json) as fallback.

3. **Handle Match vs. No-Match**
   - **Match found:** Read only the top 1–3 matched playbooks from `playbooks/` and cite each matched ID and path, e.g., `[id-001] (playbooks/01_Identity_AD_Entra/id-001-account-lockout.md)`.
   - **No match:** Start your reply with `[NO PLAYBOOK MATCH]`, provide general **read-only** diagnostic steps clearly marked as outside the verified library, and offer to create a new playbook via the `new-playbook` skill once resolved.

4. **Guide Progressive L1–L3 Troubleshooting**
   - **Step A — Fast Triage:** Ask 2–4 targeted scoping questions from `## Fast Triage (Under 2 Minutes)`.
   - **Step B — Read-Only Diagnostics First:** Provide non-destructive L1–L2 (and L3 deep-dive if needed) commands from the playbook before suggesting changes.
   - **Step C — Confirmation-Gated Remediation:** Label every state-changing action `[REMEDIATION — CONFIRM BEFORE RUNNING]` with scope and impact. Never invent cmdlets, flags, or error codes.
   - **Step D — Verification & Client Reply:** Provide post-fix checks and, when helpful, an EN or FR client-facing update snippet from the playbook.
