---
id: id-008
domain: 01_Identity_AD_Entra
subject: Identity / AD & Entra ID
subcategory: ad_gpo_hybrid_sync
title: Microsoft Entra Connect Sync Errors, Duplicate Attributes & PHS Stalls
tier: L3
keywords_en:
  - entra connect sync error
  - azure ad connect not syncing
  - duplicate proxyaddress
  - invalid soft match
  - password hash sync broken
  - ad sync error
  - export error attribute value must be unique
keywords_fr:
  - synchronisation entra connect echouee
  - erreur synchronisation ad connect
  - doublon proxyaddresses ad entra
  - hachage mot de passe non synchronise
  - erreur export synchronisation hybride
error_codes:
  - "6900"
  - "6126"
  - AttributeValueMustBeUnique
  - InvalidSoftMatch
tags:
  - entra_connect_sync
  - ad_sync_duplicate
os:
  - windows
environment:
  - hybrid_ad
  - on_prem_ad
  - entra_id
tools:
  - Microsoft Entra Connect (ADSync)
  - Synchronization Service Manager (miisclient.exe)
  - PowerShell (ADSync / ActiveDirectory)
  - Microsoft Entra Health
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - id-004
  - m365-006
  - id-001
  - m365-001
---

## Fast Triage (Under 2 Minutes)
- **Identify sync scope:** Determine if ALL users/groups stopped syncing (Entra Connect service crash, expired connector credentials, SQL Express 10 GB database limit, or server offline) versus 1–2 users (`AttributeValueMustBeUnique`, `InvalidSoftMatch`, or object moved out of a synced OU).
- **Check Entra Admin Center -> Entra Connect:** Note **Last sync** timestamp and any **Sync Errors** banner before logging into the on-prem Entra Connect server.
- **Confirm Staging Mode:** Ask whether a second standby Entra Connect server exists and verify which server is active vs `StagingModeEnabled`.
- **Check recent AD edits:** Ask if someone recently created a shared mailbox/guest/cloud-only user with the same SMTP proxyAddress or UPN as a newly hired on-prem AD user.

## Read-Only Diagnostics (L1-L2)
On the **Microsoft Entra Connect server**, check scheduler status, staging mode, and connector run state without triggering any sync cycle yet:

```powershell
Import-Module ADSync
Get-ADSyncScheduler | Select-Object SyncCycleEnabled, SyncCycleInProgress, StagingModeEnabled, NextSyncCycleStartTimeInUTC, PasswordSyncEnabled
Get-ADSyncConnectorRunStatus
```

Inspect **Event Viewer -> Application** on the Entra Connect server for `ADSync` / `Directory Synchronization` errors (`6900`, `6126`, `659`, `611`), and check on-prem AD for duplicate `proxyAddresses` or `userPrincipalName` values:

```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='ADSync','Directory Synchronization'; Level=2,3} -MaxEvents 20 |
  Select-Object TimeCreated, Id, ProviderName, Message | Format-List

# Search on-prem AD for conflicting SMTP addresses (replace jsmith@contoso.com)
Get-ADObject -LDAPFilter "(|(proxyAddresses=*jsmith@contoso.com*)(mail=jsmith@contoso.com)(userPrincipalName=jsmith@contoso.com))" -Properties ObjectClass, DisplayName, userPrincipalName, proxyAddresses, mS-DS-ConsistencyGuid |
  Select-Object ObjectClass, DistinguishedName, userPrincipalName, proxyAddresses | Format-List
```

## Deep-Dive Investigation (L3)
Open **Synchronization Service Manager (`miisclient.exe`)** on the Entra Connect server -> **Operations** tab -> inspect the latest `Export` run on the Entra ID connector (`completed-export-errors` / `6900` / `6126`):
1. Double-click any **Export Error** (`AttributeValueMustBeUnique` or `InvalidSoftMatch`) to see the exact conflicting `SourceAnchor` / `mS-DS-ConsistencyGuid` and conflicting attribute (`UserPrincipalName` or `ProxyAddresses`).
2. Compare against **Microsoft Entra Connect Health -> Sync Errors** or query cloud objects using `Microsoft.Graph`:
   ```powershell
   Connect-MgGraph -Scopes "User.Read.All","Directory.Read.All"
   Get-MgUser -Filter "proxyAddresses/any(p:p eq 'smtp:jsmith@contoso.com') or userPrincipalName eq 'jsmith@contoso.com'" -Property DisplayName,Id,UserPrincipalName,OnPremisesImmutableId,OnPremisesSyncEnabled |
     Format-List
   ```
3. Check Password Hash Synchronization (PHS) health in `Get-ADSyncScheduler` (`PasswordSyncEnabled = True`) and Application Event ID `656`/`657`/`611`.
4. Verify the SQL database backing ADSync is not full if using SQL Server Express (`LocalDB` 10 GB limit often appears as `stopped-database-full` / `6301`).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Never modify `OnPremisesImmutableId` or purge cloud objects blindly — linking an on-prem user to the wrong cloud account overwrites mailbox/OneDrive identity mapping, and deleting an active cloud mailbox disconnects data. Always export object attributes before edits.

1. **Duplicate `proxyAddresses` or UPN (`AttributeValueMustBeUnique`):**
   - Scope: Only the conflicting duplicate alias on the unintended AD object or unused cloud contact/guest.
   - Prerequisite: Confirm which identity owns the email alias with the customer.
   - Remove the duplicate SMTP entry in **Active Directory Users and Computers -> Attribute Editor (`proxyAddresses`)** (or remove the duplicate Entra mail contact/guest), then run a delta sync:
     ```powershell
     # Run ONLY after removing the confirmed duplicate attribute
     Start-ADSyncSyncCycle -PolicyType Delta
     ```
2. **`InvalidSoftMatch` (Cloud User Exists Before On-Prem User Synced):**
   - Confirm the cloud-only user (`OnPremisesSyncEnabled = $null` or empty `OnPremisesImmutableId`) is genuinely the same person as the AD user.
   - Ensure on-prem AD `userPrincipalName` and primary `SMTP:` address match the intended cloud user, or hard-match cleanly using `mS-DS-ConsistencyGuid` Base64 encoding to `OnPremisesImmutableId` ONLY under L3 change control.
3. **Stalled Scheduler or PHS Out of Sync (`PasswordSyncEnabled`):**
   - Restart `Microsoft Azure AD Sync` (`ADSync`) service ONLY after checking no `SyncCycleInProgress` export is mid-write, then verify `Start-ADSyncSyncCycle -PolicyType Delta` completes cleanly.

## Verification & Post-Fix Checks
- Verify **Synchronization Service Manager (`miisclient.exe`)** shows `success` across On-Premises AD `Delta Import` / `Delta Sync` and Entra ID `Export` with zero remaining export errors.
- Confirm in Entra Admin Center that **Entra Connect -> Last sync** updates within 30 minutes and `OnPremisesLastSyncDateTime` on the affected user matches.
- Have the user verify sign-in (if PHS was impacted) and confirm expected SMTP proxy addresses appear on their Exchange mailbox.

## Cross-Subject Escalation & Pivot Links
- **On-prem AD DFSR replication or OU ACLs prevent Entra Connect from reading directory objects:** [id-004 — Active Directory GPO Not Applying, SYSVOL Permissions, and DFSR Replication Errors](./id-004-ad-gpo-not-applying-replication-and-dfsr.md)
- **Duplicate proxyAddresses or sync failure causes Exchange Online 550 5.4.1 user unknown NDRs:** [m365-006 — Exchange Online NDR Bounces (550 5.7.1 / 5.4.1) and Missing Shared Mailbox Automapping](../02_M365_Email_Collab/m365-006-exchange-ndr-550-and-shared-mailbox-missing.md)
- **Password Hash Sync (PHS) stall keeps old password in cloud and triggers AADSTS50126/4740:** [id-001 — Account Lockout Investigation](./id-001-account-lockout.md)
- **On-prem UPN vs cloud UPN mismatch traps Outlook in an endless modern auth prompt:** [m365-001 — Outlook Password Prompt Loop and Modern Auth Failure](../02_M365_Email_Collab/m365-001-outlook-auth-loop.md)

## Useful Links & External Tools
- [Microsoft Entra Admin Center](https://entra.microsoft.com/) — Inspect Entra Connect Health Sync Errors and cloud `OnPremisesSyncEnabled` state.
- [Microsoft Entra AADSTS Error Code Lookup](https://login.microsoftonline.com/error) — Decode authentication errors caused by broken UPN/PHS sync.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we identified an Entra Connect directory synchronization conflict (`AttributeValueMustBeUnique` / `InvalidSoftMatch`) preventing `<account>` from syncing from on-premises AD to Microsoft 365. After resolving the duplicate attribute and running a delta sync, cloud directory sync is now healthy. Please verify access on your side.
- **FR:** Bonjour `<user>`, nous avons identifié un conflit de synchronisation Entra Connect (`AttributeValueMustBeUnique` / `InvalidSoftMatch`) empêchant `<account>` de se synchroniser entre l'AD local et Microsoft 365. Après correction de l'attribut en doublon et relance du cycle delta, la synchronisation est rétablie. Merci de valider l'accès de votre côté.
