---
id: m365-007
domain: 02_M365_Email_Collab
subject: Microsoft 365 / Email & Collaboration
subcategory: docs_onedrive_teams
title: Microsoft Teams External Federation & B2B Guest Access Blocked
tier: L2
keywords_en:
  - teams external user blocked
  - teams guest access failed
  - cannot message external partner teams
  - federation disabled teams
  - cross tenant access block
  - cannot invite guest to team
keywords_fr:
  - utilisateur externe teams bloque
  - acces invite teams refuse
  - impossible contacter partenaire externe teams
  - federation externe teams bloquee
  - erreur invitation invite m365
error_codes:
  - EXTERNAL_FEDERATION_BLOCKED
  - GUEST_INVITE_FAILED
tags:
  - teams_external_guest
  - teams_federation_blocked
os:
  - cross_platform
environment:
  - m365
  - entra_id
tools:
  - Microsoft Teams Admin Center
  - Microsoft Entra Admin Center
  - PowerShell (MicrosoftTeams / Microsoft.Graph)
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - id-007
  - sec-004
  - m365-005
  - net-003
---

## Fast Triage (Under 2 Minutes)
- **Distinguish External Access vs. Guest Access:**
  - **External Access (Federation):** 1:1 chat/call with someone at `partner@fabrikam.com` using Teams without adding them as a tenant member.
  - **Guest Access (B2B):** Adding `partner@fabrikam.com` into a specific Team/Channel (creates an Entra B2B `#EXT#` Guest object and relies on M365 Groups, SharePoint, and Cross-Tenant Access policies).
- **One partner domain or everyone?** Ask if external communication fails with ALL external domains or only one specific partner (`fabrikam.com`) — one partner failing often means the block is on the **partner tenant's** Teams federation or Entra Cross-Tenant Access policy!
- **Verify domain spelling & consumer vs. business Teams:** Confirm the partner is on Microsoft Teams Work/School vs. Teams Personal (`@outlook.com` / consumer) and check for typos in the email address.

## Read-Only Diagnostics (L1-L2)
Connect to Microsoft Teams and Microsoft Graph with read-only permissions to inspect federation mode, domain allow/block lists, guest policy, and Entra B2B invite rules:

```powershell
Connect-MicrosoftTeams
# Check Teams External Access (Federation) settings
Get-CsTenantFederationConfiguration |
  Select-Object AllowFederatedUsers, AllowTeamsConsumer, AllowTeamsConsumerInbound, AllowPublicUsers, AllowedDomains, BlockedDomains | Format-List

# Check Guest Access enabled state at tenant level
Get-CsTeamsClientConfiguration | Select-Object AllowGuestUser, AllowEmailIntoChannel, AllowBox, AllowDropBox
```

Inspect Entra ID guest invite settings and existing guest object state:

```powershell
Connect-MgGraph -Scopes "Policy.Read.All","User.Read.All"
Get-MgPolicyAuthorizationPolicy | Select-Object AllowInvitesFrom, GuestUserRoleId | Format-List

# Check if the external partner already has a PendingAcceptance or blocked Guest account
Get-MgUser -Filter "mail eq 'partner@fabrikam.com'" -Property DisplayName, UserPrincipalName, UserType, ExternalUserState, AccountEnabled |
  Format-List
```

## Deep-Dive Investigation (L3)
When both tenants claim federation or guest access is enabled globally, inspect the four common L3 layers that silently block collaboration:
1. **Teams Allowed/Blocked Domain Lists (Symmetry Required):** If `AllowedDomains` contains even one domain, **Teams switches from "Allow all except blocked" to strict "Allow ONLY listed domains"**. Also verify whether the **partner tenant** uses an allow-list and forgot to add `<our-tenant-domain>`.
2. **Entra External Identities -> Cross-tenant access settings:** Check **Default settings** and **Organizational settings** for `fabrikam.com` in Entra Admin Center (`B2B collaboration` inbound/outbound rules, `B2B direct connect` for Shared Channels, and **Trust settings** for partner MFA). If your Conditional Access requires MFA for guests and Inbound Trust is off, or partner MFA fails, the guest hits a wall.
3. **Microsoft 365 Group / SharePoint Sensitivity & Domain Allow-Lists:** Even if Entra allows guests, a specific Team's M365 Group (`AllowToAddGuests = False`) or SharePoint tenant/site sharing policy (`SharingDomainRestrictionMode`) can block adding guests or viewing Files inside the Team.
4. **Pending B2B Redemption:** `ExternalUserState: PendingAcceptance` means the user never clicked the redemption email (check spam/quarantine or resend invite via Entra).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Never switch a restrictive `AllowedDomains` allow-list to "Allow all external domains" without security approval — many regulated clients intentionally restrict Teams federation to approved partners. Scope domain additions strictly to verified business domains (`fabrikam.com`).

1. **Add Partner Domain to Teams External Access Allow-List (`External Federation`):**
   - Scope: Adds `fabrikam.com` to `AllowedDomains` without opening communication to the entire internet.
   - Prerequisite: Teams Administrator role + written approval of partner domain.
   - Open **Teams Admin Center** -> **Users** -> **External access** -> under **Choose which external domains your users have access to**, add `fabrikam.com` (or verify `fabrikam.com` isn't listed under blocked domains). Note: Teams federation changes can take up to 2–24 hours to replicate globally.
2. **Enable Guest Invite / Resend B2B Redemption (`Guest Access`):**
   - Open **Microsoft Entra Admin Center** -> **External Identities** -> **External collaboration settings** -> confirm `Guest invite settings` matches client security policy (e.g., Admins & Guest Inviter role only, or Members can invite).
   - If the guest shows `PendingAcceptance`, resend the invitation from **Entra ID -> Users -> `<guest>` -> Resend invitation**, or confirm Team-level `AllowToAddGuests` on the M365 Group.
3. **Allow Partner Domain in Entra Cross-Tenant Access / Conditional Access:**
   - Configure **Inbound B2B collaboration** and **Trust multifactor authentication claims from Microsoft Entra tenants** for the verified partner tenant if guests fail MFA/access loops when opening Teams channels or SharePoint tabs.

## Verification & Post-Fix Checks
- Re-run `Get-CsTenantFederationConfiguration` and confirm `fabrikam.com` appears in `AllowedDomains` (if allow-list mode) and is absent from `BlockedDomains`.
- Have the internal user open a fresh Teams 1:1 chat (external federation) or verify the guest completes B2B redemption (`ExternalUserState: Accepted`) and can view both the **Posts** and **Files** tabs in the Team.
- Remind the user that Teams federation policy updates may require a Teams client sign-out/sign-in and up to several hours for tenant cache propagation.

## Cross-Subject Escalation & Pivot Links
- **Conditional Access location block or missing Inbound MFA Trust rejects guest outside Canada:** [id-007 — Geo-Blocking Outside Canada, Conditional Access Named Locations & Travel Access](../01_Identity_AD_Entra/id-007-geo-blocking-outside-canada-travel-access.md)
- **Purview Sensitivity Label / RMS encryption denies B2B guest permission on shared files:** [sec-004 — Microsoft Purview DLP Policy Blocks & Sensitivity Label Encryption Denied](../06_Security_Access/sec-004-purview-dlp-block-and-sensitivity-labels.md)
- **SharePoint/OneDrive sharing restriction blocks guest access to Team Files tab:** [m365-005 — OneDrive Sync Stuck Processing Changes and SharePoint Path Limit Errors](./m365-005-onedrive-sync-stuck-and-sharepoint-path-limit.md)
- **Teams federation chat works while external audio/video calls fail due to UDP 3478-3481 NAT/jitter:** [net-003 — Teams and VoIP Choppy Audio, High Jitter, and One-Way Sound Triage](../04_Network_VPN_VoIP/net-003-teams-voip-choppy-audio-and-jitter.md)

## Useful Links & External Tools
- [Microsoft 365 Admin Center](https://admin.microsoft.com/) — Verify M365 Group guest toggles and SharePoint domain restrictions.
- [Microsoft Entra Admin Center](https://entra.microsoft.com/) — Check External Identities Cross-Tenant Access settings and B2B Guest redemption state.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we verified Teams federation and Entra B2B guest policies for `<partner-domain>`. After updating `<specific change — e.g., domain allow-list / B2B guest invite>`, external access is now permitted on our tenant. Note that Microsoft Teams federation changes can take a few hours to propagate, and the partner organization must also allow your domain on their side.
- **FR:** Bonjour `<user>`, nous avons vérifié les stratégies de fédération Teams et d'accès invité Entra B2B pour `<partner-domain>`. Suite à la mise à jour (`<liste d'autorisation / invitation invité>`), l'accès externe est maintenant autorisé sur notre locataire. Veuillez noter que la propagation Teams peut prendre quelques heures et que l'organisation partenaire doit également autoriser votre domaine.
