---
id: id-005
domain: 01_Identity_AD_Entra
subject: "Identity / AD & Entra ID"
subcategory: ad_gpo_hybrid_sync
title: Windows Domain Trust Relationship Failed (Event ID 5722 / 3210 / 0xC000018B)
tier: L2
keywords_en:
  - trust relationship failed
  - primary domain trust broken
  - secure channel failed windows
  - event 5722 netlogon
  - domain workstation login failed
keywords_fr:
  - relation d'approbation domaine echouee
  - echec relation approbation poste
  - canal securise domaine casse
  - impossible ouvrir session domaine windows
  - erreur relation approbation station travail
error_codes:
  - "5722"
  - "3210"
  - "0xC000018B"
tags:
  - domain_trust_failed
  - secure_channel_broken
os:
  - windows
environment:
  - on_prem_ad
  - hybrid_ad
tools:
  - PowerShell
  - nltest
  - Event Viewer
  - Active Directory Users and Computers
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-012
  - id-004
  - id-001
  - win-004
---

## Fast Triage (Under 2 Minutes)
- User sees **`"The trust relationship between this workstation and the primary domain failed"`** at Windows login on `PC-LAB-01`.
- **Quick Remote Sign-In Trick (When User Is Remote Without Direct DC Line-of-Sight):** Have `jsmith@example.com` unplug Ethernet / turn off Wi-Fi temporarily and sign in with their **last cached domain password** — once at the desktop, connect VPN so the workstation reaches `DC01.domain.local` for live secure-channel repair!
- Common root causes: PC offline >30 days (machine password rotated out of sync), **VM snapshot rollback** without resetting machine password, or **duplicate computer name** joined to AD overwriting the machine account SID/password!

## Read-Only Diagnostics (L1-L2)
1. **Verify Line-of-Sight to Domain Controller (`DC01.domain.local`) and Machine Secure Channel (read-only, run as Local Admin):**
   ```powershell
   Test-ComputerSecureChannel -Verbose
   ```
   ```cmd
   nltest /sc_query:domain.local
   ```
2. **Check `System` Event Log on `PC-LAB-01` and `DC01.domain.local` for `NETLOGON` Errors (`5722` / `3210`, read-only):**
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'NETLOGON'; Id = 3210, 5719, 5722, 5723; StartTime = (Get-Date).AddDays(-3) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, Message
   ```
3. **Check Time Skew (`[srv-012]`) & Duplicate Hostnames in AD:**
   - Verify `PC-LAB-01` clock matches `DC01.domain.local` within 5 minutes (`w32tm /query /status`) and check **ADUC** to verify another newly imaged laptop wasn't given the exact same hostname `PC-LAB-01`!

## Deep-Dive Investigation (L3)
1. **Duplicate Computer Name Collision (`5722` on DC):** Re-imaging an endpoint with the same hostname and clicking "Yes" to reuse the AD object invalidates the old machine's `pwdLastSet` secret immediately.
2. **Hybrid Entra ID Join Impact:** If `PC-LAB-01` is **Hybrid Entra Joined**, avoid deleting and recreating the AD computer object unless strictly necessary — recreating the computer object changes its `objectGUID` and breaks its Entra Hybrid device registration until re-synced! Use `Reset-ComputerMachinePassword` / `Test-ComputerSecureChannel -Repair` instead.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Preferred Repair (Zero Reboot Required & Preserves AD Object/GUID):** Sign into `PC-LAB-01` using a **local administrator** account (or cached user + active VPN to `DC01.domain.local`), open elevated PowerShell, and repair the machine secure channel using Domain Admin or delegated join credentials:
   ```powershell
   $cred = Get-Credential  # Enter DOMAIN\admin-join-account
   Test-ComputerSecureChannel -Repair -Credential $cred -Verbose
   ```
   *(Alternative legacy CMD: `nltest /sc_reset:domain.local\DC01.domain.local`.)*
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Fallback (If `-Repair` Fails with Access Denied or Orphaned AD Object):** Disjoin `PC-LAB-01` to a temporary `WORKGROUP` (verify you have a **working local administrator username + password** FIRST so you don't lock yourself out!), reboot, reset the AD computer account if needed, and rejoin `domain.local`.

## Verification & Post-Fix Checks
1. Confirm `Test-ComputerSecureChannel -Verbose` returns **`True`** (`"The secure channel between the local computer and the domain is in good condition"`).
2. Lock/sign out and verify `jsmith@example.com` signs in cleanly with domain credentials and accesses network shares / GPOs without trust errors.

## Cross-Subject Escalation & Pivot Links
- **DC DNS resolution failure or >5 min NTP time drift (KRB_AP_ERR_SKEW) breaks Netlogon trust:** [srv-012 — Windows Server DHCP Scope Exhausted, DNS AD Load Failure, and Kerberos Time Skew](../08_Servers_Cloud_Infra/srv-012-windows-dhcp-exhausted-dns-forwarder-and-ntp-skew.md)
- **Broken domain trust channel prevents Group Policy (1058/1030) and SYSVOL access:** [id-004 — Active Directory GPO Not Applying, SYSVOL Permissions, and DFSR Replication Errors](./id-004-ad-gpo-not-applying-replication-and-dfsr.md)
- **Cached offline domain credentials diverge from AD password causing lockouts:** [id-001 — Account Lockout Investigation](./id-001-account-lockout.md)
- **Corrupt workstation profile or SID cache triggers temporary user profile at domain logon:** [win-004 — Windows Temporary User Profile Recovery (Event ID 1511 / 1515)](../03_Windows_Endpoints/win-004-windows-temporary-profile-recovery.md)

## Client Update Snippets (EN / FR)
- **EN:** We repaired the Windows Active Directory secure channel trust relationship on `PC-LAB-01` while keeping your profile and computer record intact. Please sign in with your regular domain password and confirm everything works cleanly.
- **FR:** Nous avons réparé le canal sécurisé et la relation d'approbation Active Directory sur `PC-LAB-01` tout en conservant votre profil intact. Veuillez vous connecter avec votre mot de passe de domaine habituel et confirmer que l'accès fonctionne.
