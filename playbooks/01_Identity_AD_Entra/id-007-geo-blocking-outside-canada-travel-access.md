---
id: id-007
domain: 01_Identity_AD_Entra
subject: Identity / AD & Entra ID
subcategory: entra_apps_conditional_access
title: Geo-Blocking Outside Canada, Conditional Access Named Locations & Travel Access
tier: L2
keywords_en:
  - blocked outside canada
  - gpo blocking outside canada
  - conditional access named location
  - traveling abroad sign in blocked
  - geo blocking policy
  - country block firewall vpn
  - logon denied travel
keywords_fr:
  - bloque hors canada
  - gpo bloque hors canada
  - acces conditionnel pays
  - voyage etranger connexion bloquee
  - blocage geographique entra
  - acces refuse hors canada
error_codes:
  - AADSTS53003
  - GEO_BLOCK
  - CA_NAMED_LOCATION
tags:
  - geo_block_travel
  - conditional_access_location
os:
  - cross_platform
environment:
  - entra_id
  - m365
  - on_prem_ad
  - network
tools:
  - Microsoft Entra Admin Center
  - PowerShell (Microsoft.Graph)
  - Entra Sign-in Logs
  - Group Policy (gpresult)
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - net-001
  - app-001
  - sec-001
  - net-005
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you **physically traveling outside Canada right now**, OR are you **inside Canada** (possibly connected to a personal VPN like NordVPN, iCloud Private Relay, or hotel guest network)?
2. Which **exact application** is blocked (**M365 / Outlook / Teams** -> `AADSTS53003` vs **Corporate SSL VPN** vs **RDP/Website**)?
3. What is your **destination country**, **departure date**, and **expected return date**, AND has your **manager/HR sent written approval** for travel access? *(Security Rule: **NEVER** lift a Geo-Block based on user email/chat alone without manager voice/ticket verification!)*
4. Capture the exact **IP address** and **Correlation ID** shown on the Microsoft block screen (or have the user check their IP on `https://whatismyipaddress.com`).

### Initial Scope & Classification
- **Clarify what is blocking (Cloud CA vs Firewall Geo-IP vs AD/GPO):** Explain clearly that standard Windows Active Directory Group Policy (GPO) does **not** natively evaluate Geo-IP countries. Users blocked outside Canada are almost always blocked by **Microsoft Entra Conditional Access Named Locations (`AADSTS53003`)** or **corporate VPN/Firewall Geo-IP rules**.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Confirm Physical Location vs Consumer VPN Leak (Solves False-Positive Blocks Fast!):** If `jsmith@example.com` IS inside Canada, check for active consumer VPNs (Nord/Proton/ExpressVPN), **Apple iCloud Private Relay** (Safari/Mac/iPhone), or Edge/Opera built-in **Secure Network VPN**! Turning those off restores Canadian Geo-IP instantly!
2. **Check Entra Sign-in Logs Visually (`entra.microsoft.com` -> Users -> `jsmith@example.com` -> Sign-in logs):** Look at failed sign-in rows (`AADSTS53003`), verify the logged **Location (`Country`)** matches the user's confirmed travel destination, and note which **Conditional Access** policy blocked it!
3. **Verify Manager Travel Approval Ticket:** Ensure written manager approval with exact start & end dates is attached BEFORE escalating/adding to the travel exception group!

### L2 Technical Diagnostics
On the affected Windows endpoint (if reachable via RMM/remote session), gather local network, proxy, and AD GPO state without changing configuration:

```powershell
# Check IPv4/IPv6 adapters, DNS suffixes, and active VPN adapters
ipconfig /all
Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | Select-Object Name, InterfaceDescription, LinkSpeed

# Confirm Entra hybrid/join status and applied Computer/User GPOs
dsregcmd /status
gpresult /r
```

In **Microsoft Entra Sign-in Logs** (or using Microsoft Graph PowerShell), inspect the blocked authentication attempt to confirm which location and Conditional Access policy blocked it:

```powershell
Connect-MgGraph -Scopes "AuditLog.Read.All","Policy.Read.All","Directory.Read.All"

# Inspect recent failed sign-ins for the user (check CountryOrRegion & AppliedConditionalAccessPolicies)
Get-MgAuditLogSignIn -Filter "userPrincipalName eq 'jsmith@example.com'" -Top 10 |
  Select-Object CreatedDateTime, AppDisplayName, IpAddress,
    @{N='Country';E={$_.Location.CountryOrRegion}},
    @{N='City';E={$_.Location.City}},
    @{N='ErrorCode';E={$_.Status.ErrorCode}},
    ConditionalAccessStatus | Format-Table -AutoSize
```

## Deep-Dive Investigation (L3)
Inspect Conditional Access Named Locations and policies that target countries/regions, plus on-prem AD restrictions if internal apps or VPN fail:

```powershell
# List Conditional Access Named Locations (Country vs IP ranges)
Get-MgIdentityConditionalAccessNamedLocation |
  Select-Object Id, DisplayName, AdditionalProperties | Format-List

# List enabled Conditional Access policies and inspect Location conditions
Get-MgIdentityConditionalAccessPolicy |
  Where-Object { $_.State -eq "enabled" } |
  Select-Object DisplayName, State, @{N='IncludeLocations';E={$_.Conditions.Locations.IncludeLocations}}, @{N='ExcludeLocations';E={$_.Conditions.Locations.ExcludeLocations}}, @{N='ExcludeGroups';E={$_.Conditions.Users.ExcludeGroups}} |
  Format-List
```

If M365 succeeds (or the user is authenticating to an on-prem RDS/VPN/DC where a tech suspected a "GPO block"):
1. Check Active Directory account constraints on a Domain Controller (read-only):
   ```powershell
   Get-ADUser -Identity "jsmith" -Properties LogonWorkstations, LogonHours, AccountExpirationDate, Enabled |
     Select-Object SamAccountName, Enabled, LogonWorkstations, AccountExpirationDate
   ```
2. Check Windows Firewall GPO policies (`Windows Firewall with Advanced Security` -> Inbound Rules -> `Scope` tab -> Remote IP addresses) and IPSec policies via `Get-NetFirewallRule` / `gpresult /h C:\Temp\gp.html`.
3. Check the perimeter firewall / VPN gateway (FortiGate, SonicWall, Sophos, Meraki) Geo-IP country allow-list on SSL VPN, IPsec IKEv2, and NAT virtual IPs, which frequently drop packets before Windows or AD sees a logon.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER disable a tenant-wide Geo-Blocking Conditional Access policy or remove a firewall country filter globally. All travel exceptions must require **manager approval**, use **time-bounded group membership**, and enforce **MFA** (ideally phishing-resistant FIDO2/Authenticator Number Matching).

1. **Entra ID Time-Bounded Travel Exception Group (Recommended Pattern):**
   - Scope: Single user `jsmith@example.com` added to a dedicated exclusion group (e.g., `SG-CA-Travel-Exception-Temp`) excluded only from the Country Block policy while still governed by an **MFA + Compliant/Trusted Device** Conditional Access policy.
   - Prerequisite: Manager written approval with explicit return date; Conditional Access Administrator role.
   - Remove the user from `SG-CA-Travel-Exception-Temp` automatically or via scheduled ticket immediately on the return date.
   ```powershell
   # Run ONLY after verifying manager approval and policy exclusions
   Connect-MgGraph -Scopes "GroupMember.ReadWrite.All"
   New-MgGroupMember -GroupId "<travel-exception-group-id>" -DirectoryObjectId "<user-object-id>"
   ```
2. **False-Positive Consumer VPN / Private Relay inside Canada:**
   - Instruct the user to disconnect personal consumer VPNs or disable iCloud Private Relay / browser Secure DNS-proxy features and retry without weakening tenant policy.
3. **VPN Gateway / Firewall Geo-IP Exception (When Corporate VPN Is Blocked Abroad):**
   - Coordinate with Network Admin (L3) to allow only the destination country temporarily on the VPN/ZTNA policy with MFA enforced, or route M365 through an approved Canadian corporate VPN/ZTNA gateway if split-tunneling leaks foreign IPs.

## Verification & Post-Fix Checks
- Verify in **Entra Sign-in Logs** that the user's new sign-in from the destination country transitions from `ConditionalAccessStatus: failure` (`AADSTS53003`) to `success` with **MFA satisfied**.
- Confirm the user's non-work consumer VPN is off if testing from inside Canada and that expected M365 apps (Outlook, Teams, SharePoint) sync cleanly.
- Create/schedule a follow-up ticket for `<return-date + 1 day>` to remove `<user-object-id>` from the temporary travel exception group and verify removal.

## Cross-Subject Escalation & Pivot Links
- **Consumer VPN, IPv6 exit node, or split-tunnel leak makes user appear outside Canada:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Conditional Access location enforcement causes browser SSO redirect loops (ERR_TOO_MANY_REDIRECTS):** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](../09_Apps_LOB/app-001-browser-sso-and-lob-crash.md)
- **Foreign login alert has no confirmed travel approval — escalate immediately as BEC/token theft:** [sec-001 — Suspected Business Email Compromise and Session Token Theft](../06_Security_Access/sec-001-bec-token-compromise.md)
- **Branch or Azure site-to-site firewall Geo-IP rule drops remote subnet traffic:** [net-005 — Site-to-Site IPsec VPN Tunnel Down (IKE Phase 1/2 Mismatch & DPD Timeouts)](../04_Network_VPN_VoIP/net-005-site-to-site-ipsec-vpn-tunnel-down.md)

## Useful Links & External Tools
- [Microsoft Entra AADSTS Error Code Lookup](https://login.microsoftonline.com/error) — Look up `AADSTS53003` and Conditional Access block diagnostics.
- [Microsoft Entra Admin Center](https://entra.microsoft.com/) — Inspect Named Locations, Conditional Access policies, and Sign-in Logs.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, following manager approval for your confirmed travel dates, we added a temporary, MFA-protected Conditional Access travel exception for your account (`<start-date>` to `<end-date>`). Please sign out and back in to test access, and note that this exception automatically expires upon your return.
- **FR:** Bonjour `<user>`, après validation de votre gestionnaire pour vos dates de voyage, nous avons activé une exception temporaire protégée par MFA dans l'accès conditionnel (`<start-date>` au `<end-date>`). Veuillez vous déconnecter puis vous reconnecter pour tester l'accès; l'exception sera retirée automatiquement à votre retour.
