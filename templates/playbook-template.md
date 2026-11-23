---
id: "<prefix>-000"
domain: "<domain_folder_from_domains_json>"
subject: "<canonical_subject_from_domains_json>"
subcategory: "<subcategory_id_from_domains_json>"
title: "<Concise Action-Oriented Title>"
tier: L2
keywords_en:
  - "<english user symptom>"
  - "<english alternate phrasing>"
keywords_fr:
  - "<symptome utilisateur en francais>"
  - "<autre formulation francaise>"
error_codes:
  - "<EVENT_OR_HEX_CODE>"
tags:
  - "<canonical_snake_case_tag>"
os:
  - windows
environment:
  - hybrid_ad
tools:
  - PowerShell
  - Event Viewer
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids: []
linked_scripts: []
---

## Fast Triage (Under 2 Minutes)
- Scope check 1: Single user/endpoint or multi-user/tenant-wide impact?
- Scope check 2: What changed recently (password change, OS/app update, VPN/network change, license/policy change)?
- Confirm exact verbatim error message or code before running diagnostics.

## Read-Only Diagnostics (L1-L2)
> Run non-destructive read-only checks first to isolate scope and gather evidence.

1. Run initial read-only inspection on the affected endpoint (`PC-LAB-01` / `jsmith@example.com`):
   ```powershell
   # Replace with verified read-only PowerShell / CLI diagnostics
   ```
2. Check relevant event logs or admin portal logs and note timestamps and correlation IDs.

## Deep-Dive Investigation (L3)
> Deeper root-cause analysis when L1-L2 triage does not isolate a single obvious cause.

1. Inspect underlying auth tokens, policy precedence, network traces, or component logs.
2. Rule out systemic or security causes (e.g., policy conflicts, token hijack, upstream outage).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Review blast radius, user impact, and backup/rollback plan before executing any state-changing command.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Describe the targeted fix, affected scope, and verified command:
   ```powershell
   # Verified state-changing command with synthetic placeholders only
   ```

## Verification & Post-Fix Checks
1. Re-run the key read-only diagnostic check to confirm the error condition is cleared.
2. Have the user (`jsmith@example.com`) reproduce the workflow end-to-end and verify stability.

## Cross-Subject Escalation & Pivot Links
- **If root cause shifts to DNS, DHCP, or VPN routing:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../playbooks/04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)

## Useful Links & External Tools
- **[Example Official Docs](https://learn.microsoft.com/)** — Concise note explaining what to verify without sharing real client PII.

## Client Update Snippets (EN / FR)
- **EN:** We identified the root cause of the issue and applied a verified fix. Could you please test once more on your side and confirm everything is working normally?
- **FR:** Nous avons identifié la cause du problème et appliqué un correctif vérifié. Pouvez-vous effectuer un nouvel essai de votre côté et nous confirmer que tout fonctionne normalement ?
