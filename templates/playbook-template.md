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
### Questions to Ask the User (Classify the Issue)
1. Is this happening only to you (`PC-LAB-01` / `jsmith@example.com`), or are other coworkers experiencing the exact same problem?
2. What changed right before this started (password change, OS/app update, new device, network/Wi-Fi switch)?
3. What is the exact word-for-word error message or error code on screen (ask for a screenshot)?
4. Does the issue happen both in the desktop app and in a web browser (or both on office LAN and home Wi-Fi)?

### Initial Scope & Classification
- Confirm blast radius (single user vs. department vs. tenant-wide outage) and isolate obvious triggers before running diagnostics.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
> Start with simple, non-destructive visual/GUI checks before escalating or running advanced commands.

1. Verify basic prerequisites (account lock/password status, cable/Wi-Fi connectivity, service running in `services.msc`, free disk space).
2. Capture screenshots, exact timestamps, and Event Viewer / Web Portal error messages for ticket notes.

### L2 Technical Diagnostics
> Run verified read-only PowerShell, CLI, or Admin Portal inspection commands on `PC-LAB-01` / `jsmith@example.com`.

```powershell
# Replace with verified read-only PowerShell / CLI diagnostics
```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Exact error message/code screenshot + timestamp, user UPN (`jsmith@example.com`), hostname (`PC-LAB-01`), and answers to the 4 triage questions above.

## Deep-Dive Investigation (L3)
> Deeper root-cause analysis when L1-L2 triage does not isolate a single obvious cause.

1. Inspect underlying auth tokens, policy precedence, network traces, or component logs.
2. Rule out systemic or security causes (e.g., policy conflicts, token hijack, upstream outage).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Review blast radius, user impact, and backup/rollback plan before executing any state-changing command.

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Quick Fix)** Safe, low-impact reset (sign out/in, restart stuck client app, reconnect Wi-Fi/VPN cleanly).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Fix)** Describe the targeted state-changing command, affected scope, and verified rollback:
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
