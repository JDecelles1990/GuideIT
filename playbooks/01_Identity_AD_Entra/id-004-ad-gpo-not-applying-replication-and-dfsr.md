---
id: id-004
domain: 01_Identity_AD_Entra
subject: "Identity / AD & Entra ID"
subcategory: ad_gpo_hybrid_sync
title: Active Directory GPO Not Applying, SYSVOL Permissions, and DFSR Replication Errors
tier: L3
keywords_en:
  - gpo not applying
  - sysvol dfsr replication failed
  - gpresult access denied
  - group policy failing windows
  - dfsr event 4012 2213
keywords_fr:
  - strategie groupe gpo non appliquee
  - erreur replication ad sysvol
  - gpresult acces refuse
  - gpo ne s applique pas
  - erreur dfsr sysvol ad
error_codes:
  - "1058"
  - "1030"
  - "1055"
  - "1129"
  - "4012"
  - "2213"
tags:
  - gpo_not_applying
  - ad_replication_dfsr
os:
  - windows
environment:
  - on_prem_ad
  - hybrid_ad
tools:
  - gpresult
  - repadmin
  - dcdiag
  - Group Policy Management
  - Event Viewer
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-012
  - id-005
  - net-004
  - id-001
---

## Fast Triage (Under 2 Minutes)
- Distinguish **Single Endpoint Issue** (`Event ID 1055` computer not ready / `1129` DC unreachable over VPN / `1058` missing `Authenticated Users` Read permission!) vs. **Domain-Wide AD / SYSVOL Outage** (`Event ID 1030` across all workstations, `4012` DFSR stale replication, `2213` DFSR database dirty shutdown).
- If an admin recently removed **`Authenticated Users`** from a GPO's **Security Filtering** without adding **`Authenticated Users` -> `Read`** on the **Delegation** tab, Windows computers can no longer read the Computer GPO (`MS16-072` hardening)!

## Read-Only Diagnostics (L1-L2)
1. **On the affected workstation (`PC-LAB-01`), inspect applied/denied GPOs and GroupPolicy Operational events (read-only):**
   ```cmd
   gpresult /r
   gpresult /h C:\Windows\Temp\gporeport.html
   ```
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'System'; ProviderName = 'Microsoft-Windows-GroupPolicy'; StartTime = (Get-Date).AddDays(-2) } -MaxEvents 20 -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, LevelDisplayName, Message
   ```
   *(Key Event IDs: `1058` = cannot read `gpt.ini` in SYSVOL; `1055` = Computer name/network resolution failed at startup; `1129` = DC connectivity timeout before GPO processing; `1030` = Group Policy processing failed.)*
2. **Verify Secure Channel, DNS, and SYSVOL Reachability from `PC-LAB-01` (read-only):**
   ```cmd
   nltest /dsgetdc:domain.local
   ```
   ```powershell
   Test-Path "\\domain.local\SYSVOL\domain.local\Policies"
   ```
3. **On Domain Controller (`DC01.domain.local`), check AD & DFSR SYSVOL health (read-only):**
   ```cmd
   repadmin /replsummary
   repadmin /showrepl
   dcdiag /test:advertising /test:sysvolcheck /test:netlogons
   ```
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'DFS Replication'; Id = 2213, 4012, 4612, 5002; StartTime = (Get-Date).AddDays(-7) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, Message
   ```

## Deep-Dive Investigation (L3)
1. **MS16-072 Security Filtering Trap (`Event ID 1058`):** Inspect the failing GPO in **GPMC (`gpmc.msc`) -> Delegation tab**; even when scoped to a custom User Group under Security Filtering, **`Authenticated Users`** (or `Domain Computers`) **MUST retain `Read` permission** so the machine account can fetch `gpt.ini`!
2. **DFSR Dirty Shutdown (`Event ID 2213`) or MaxOfflineTime Exceeded (`Event ID 4012`):** After an ungraceful DC power loss, DFSR pauses SYSVOL replication until explicitly resumed (`ResumeReplication` WMI method), or requires authoritative/non-authoritative DFSR recovery (`D4` / `D2`) if tombstoned (`4012`) > `MaxOfflineTimeInDays`.
3. **Slow Link / Missing Always-Wait-For-Network:** Wireless/VPN laptops often log `1055`/`1129` because Windows attempts user logon before Wi-Fi/VPN connects (`Always wait for the network at computer startup and logon` or scheduled background refresh).

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If a GPO lost read access after narrowing Security Filtering (`Event ID 1058`), open **GPMC -> `<Target GPO>` -> Delegation -> Add -> `Authenticated Users` -> `Read`** (NOT `Apply group policy`).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Force clean Group Policy refresh on `PC-LAB-01` once DC/SYSVOL access is verified (warning: `/force` re-applies all policies and may log off/reboot if required by CSEs):
   ```cmd
   gpupdate /force
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **DFSR `Event ID 2213`** on a single paused DC (verify Event `2213` message text on `DC01` first — follow exact Microsoft WMI recovery command displayed inside that Event `2213` description, and confirm healthy DC replication BEFORE proceeding):
   ```powershell
   Get-CimInstance -Namespace "root\MicrosoftDFS" -ClassName DfsrVolumeConfig |
       Invoke-CimMethod -MethodName ResumeReplication
   ```

## Verification & Post-Fix Checks
1. Confirm `repadmin /replsummary` reports `0` failures and `dcdiag /test:sysvolcheck` passes cleanly on all DCs.
2. Run `gpresult /r` on `PC-LAB-01` and confirm the target GPO appears under **Applied Group Policy Objects** with zero `1058`/`1030` events.

## Cross-Subject Escalation & Pivot Links
- **DNS SRV record resolution failure or Kerberos clock skew prevents SYSVOL/GPO retrieval:** [srv-012 — Windows Server DHCP Scope Exhausted, DNS AD Load Failure, and Kerberos Time Skew](../08_Servers_Cloud_Infra/srv-012-windows-dhcp-exhausted-dns-forwarder-and-ntp-skew.md)
- **Broken workstation secure channel (Event 5722) blocks computer GPO processing (1058/1030):** [id-005 — Windows Domain Trust Relationship Failed (Event ID 5722 / 3210 / 0xC000018B)](./id-005-windows-domain-trust-relationship-failed.md)
- **GPO mapped network drives fail (Event 1129) over slow VPN or blocked SMB port 445:** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)
- **Enforced GPO password/lockout thresholds or authentication errors trigger AD lockouts:** [id-001 — Account Lockout Investigation](./id-001-account-lockout.md)

## Client Update Snippets (EN / FR)
- **EN:** We resolved the Active Directory Group Policy / SYSVOL replication issue (`Event ID 1058 / DFSR`) and verified policies apply cleanly on `PC-LAB-01`. Could you run a quick sign-out/sign-in (or reboot) and confirm the expected policy/drive settings appear?
- **FR:** Nous avons corrigé l'erreur d'application des stratégies de groupe Active Directory / réplication SYSVOL et validé la mise à jour sur `PC-LAB-01`. Pouvez-vous fermer et rouvrir votre session (ou redémarrer) et confirmer que les paramètres s'appliquent ?
