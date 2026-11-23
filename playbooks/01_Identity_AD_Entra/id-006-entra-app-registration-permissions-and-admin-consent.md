---
id: id-006
domain: 01_Identity_AD_Entra
subject: Identity / AD & Entra ID
subcategory: entra_apps_conditional_access
title: Entra ID App Registration Permissions, Admin Consent & Developer Secret Failures
tier: L2
keywords_en:
  - entra app permissions
  - developer app registration
  - admin consent required
  - app secret expired
  - graph api permission denied
  - enterprise application assignment
  - coder oauth error
keywords_fr:
  - permission application entra
  - approbation administrateur requise
  - consentement admin entra
  - secret client expire
  - application entreprise bloquee
  - erreur graph api developpeur
error_codes:
  - AADSTS65001
  - AADSTS90094
  - AADSTS7000215
  - AADSTS50105
  - AADSTS700016
tags:
  - entra_app_permissions
  - entra_admin_consent
os:
  - cross_platform
environment:
  - entra_id
  - azure
  - saas
tools:
  - Microsoft Entra Admin Center
  - PowerShell (Microsoft.Graph)
  - Entra Sign-in Logs
  - Microsoft Entra AADSTS Error Code Lookup
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-014
  - app-004
  - sec-001
  - id-002
---

## Fast Triage (Under 2 Minutes)
- **Exact error code:** Ask the developer for the full `AADSTS` error code and HTTP response (`AADSTS65001` = missing user/admin consent, `AADSTS90094` = admin consent explicitly required by policy, `AADSTS7000215` = wrong/expired client secret, `AADSTS50105` = user/group not assigned, `AADSTS700016` = wrong Tenant ID or App ID).
- **Flow type:** Determine whether the app uses **Delegated permissions** (acts on behalf of a signed-in user) or **Application permissions** (daemon/background service with client secret or certificate — always requires Global/Cloud App Admin consent).
- **Tenant & environment:** Verify the developer is authenticating against the correct Tenant ID (`<tenant-id>`) and not mixing staging/dev App Registrations with production.
- **Least-privilege check:** Confirm why each requested Microsoft Graph or Azure API scope is needed before granting tenant-wide `*.ReadWrite.All` permissions.

## Read-Only Diagnostics (L1-L2)
Connect with read-only Microsoft Graph scopes to inspect the App Registration, Enterprise Application (Service Principal), existing grants, and tenant user-consent settings:

```powershell
Connect-MgGraph -Scopes "Application.Read.All","Directory.Read.All","Policy.Read.All","AuditLog.Read.All"

# Inspect App Registration and required Resource Access (replace <app-client-id>)
$app = Get-MgApplication -Filter "AppId eq '<app-client-id>'"
$app | Select-Object DisplayName, AppId, Id, SignInAudience, RequiredResourceAccess | Format-List

# Check Client Secret / Certificate expiration dates (never prints secret values)
$app.PasswordCredentials | Select-Object DisplayName, KeyId, StartDateTime, EndDateTime
$app.KeyCredentials | Select-Object DisplayName, KeyId, Type, StartDateTime, EndDateTime
```

Check whether tenant policy blocks users from consenting or allows the Admin Consent Request workflow:

```powershell
Get-MgPolicyAuthorizationPolicy | Select-Object -ExpandProperty DefaultUserRolePermissions | Format-List AllowedToCreateApps, PermissionGrantPoliciesAssigned
```

## Deep-Dive Investigation (L3)
Inspect the Enterprise Application (`ServicePrincipal`), existing OAuth2 delegated grants, Application Role assignments, and recent failed sign-in events:

```powershell
$sp = Get-MgServicePrincipal -Filter "AppId eq '<app-client-id>'"
$sp | Select-Object DisplayName, Id, AppId, AccountEnabled, AppRoleAssignmentRequired | Format-List

# 1. Existing Delegated OAuth2 Permission Grants
Get-MgServicePrincipalOauth2PermissionGrant -ServicePrincipalId $sp.Id |
  Select-Object ClientId, ConsentType, PrincipalId, ResourceId, Scope | Format-Table -AutoSize

# 2. Existing Application Role Assignments (daemon/app-only permissions)
Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $sp.Id |
  Select-Object PrincipalDisplayName, ResourceDisplayName, AppRoleId, CreatedDateTime | Format-Table -AutoSize

# 3. Assigned users/groups when AppRoleAssignmentRequired is True (AADSTS50105)
Get-MgServicePrincipalAppRoleAssignedTo -ServicePrincipalId $sp.Id |
  Select-Object PrincipalDisplayName, PrincipalType, AppRoleId | Format-Table -AutoSize

# 4. Inspect non-interactive/service-principal sign-in failures for the app
Get-MgAuditLogSignIn -Filter "appId eq '<app-client-id>'" -Top 15 |
  Select-Object CreatedDateTime, UserPrincipalName, AppDisplayName, @{N='ErrorCode';E={$_.Status.ErrorCode}}, @{N='Reason';E={$_.Status.FailureReason}} |
  Format-Table -AutoSize
```

Common root causes to distinguish:
1. **`AADSTS7000215` (Invalid client secret):** The developer pasted the **Secret ID** instead of the one-time **Secret Value**, or `EndDateTime` on `PasswordCredentials` has expired.
2. **`AADSTS65001` / `AADSTS90094`:** A new scope was added in `RequiredResourceAccess` or code, or the Redirect URI uses a different scope string (`/.default` for client credentials), without tenant admin consent granted on the Enterprise App.
3. **`AADSTS50105`:** Enterprise Application has **Assignment required? = Yes** (`AppRoleAssignmentRequired = True`) and the developer/test user or their security group is not assigned.
4. **`AADSTS700016`:** Code points to `common` with a single-tenant app, or passes the wrong Tenant ID / Client ID.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Review requested permissions against the principle of least privilege before approving. Tenant-wide Application permissions (e.g., `Mail.ReadWrite`, `Directory.ReadWrite.All`, `Files.Read.All`) grant access across ALL users unless scoped. Always obtain security/client approval for high-privilege Graph scopes.

1. **Grant Admin Consent (GUI — Preferred for Audit Clarity):**
   - Open **Microsoft Entra Admin Center** -> **Identity** -> **Applications** -> **App registrations** (or **Enterprise applications**).
   - Select the target app -> **API permissions** -> verify only minimal required scopes are listed -> select **Grant admin consent for `<tenant>`**.
2. **Assign Developer/Tester to Enterprise Application (`AADSTS50105`):**
   - Scope: single user or pilot security group on Enterprise App `<app-client-id>`.
   - Prerequisite: Cloud Application Administrator or Application Administrator role.
   - Open **Enterprise applications** -> `<app-name>` -> **Users and groups** -> **Add user/group**.
3. **Rotate Expired Client Secret (`AADSTS7000215`) or Switch to Certificate/Managed Identity:**
   - **[REMEDIATION — CONFIRM BEFORE RUNNING]** Creating a new secret allows new auth immediately; wait to delete the old secret until the developer confirms rollout, otherwise active production jobs will break (`AADSTS7000215`).
   - Prefer **Certificate credentials** or **Azure Managed Identity** over long-lived client secrets where workloads run on Azure.
   - When creating a secret in **Certificates & secrets**, instruct the developer to store the **Value** immediately in **Azure Key Vault** or approved secret manager (never commit to Git).
4. **Scope Exchange Mail/Calendar App Permissions (Optional RBAC Best Practice):**
   - If a coder requests `Mail.Read` or `Mail.Send` application permissions only for one shared mailbox (e.g., `invoices@contoso.com`), use **Exchange Online RBAC for Applications** instead of granting tenant-wide mailbox access.

## Verification & Post-Fix Checks
- Verify the Enterprise Application shows green **Granted for `<tenant>`** status on every approved API permission in Entra Admin Center.
- Re-run `Get-MgServicePrincipalOauth2PermissionGrant` and `Get-MgServicePrincipalAppRoleAssignment` to confirm no over-privileged scopes remain.
- Have the developer request a fresh OAuth2 token (clear cached MSAL/token cache) and confirm **Entra Sign-in Logs** record `ErrorCode: 0` (Success).
- Record any new Client Secret expiration date in the MSP password/documentation system with an automated renewal reminder 30 days before expiry.

## Cross-Subject Escalation & Pivot Links
- **Developer app gets an Entra token cleanly yet hits Azure Storage/Key Vault data-plane RBAC 403:** [srv-014 — Azure RBAC 403 Errors, Storage Permission Mismatch & Key Vault Firewall Blocks](../08_Servers_Cloud_Infra/srv-014-azure-rbac-403-storage-and-keyvault-firewall.md)
- **Developer CLI (git, npm, pip, az) fails corporate TLS proxy certs or PowerShell ExecutionPolicy:** [app-004 — Developer Git/NPM/PIP SSL Proxy Certificate Errors & PowerShell ExecutionPolicy](../09_Apps_LOB/app-004-dev-git-ssl-proxy-cert-and-powershell-policy.md)
- **Suspicious high-privilege Enterprise App consent grant triggers BEC incident review:** [sec-001 — Suspected Business Email Compromise and Session Token Theft](../06_Security_Access/sec-001-bec-token-compromise.md)
- **Cross-IdP OAuth/SSO or admin role block affects Google Workspace console access:** [id-002 — Google Workspace Admin Console 2SV Lockout, Role 403, and Suspended User Recovery](./id-002-google-workspace-admin-2sv-lockout.md)

## Useful Links & External Tools
- [Microsoft Entra AADSTS Error Code Lookup](https://login.microsoftonline.com/error) — Decode any AADSTS code returned during OAuth2 consent or token acquisition.
- [Microsoft Entra Admin Center](https://entra.microsoft.com/) — Review App Registrations, Enterprise Apps, Admin Consent Requests, and Sign-in Logs.
- [Microsoft Azure Portal](https://portal.azure.com/) — Configure Managed Identities and Azure Key Vault secret storage.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we reviewed your Entra ID application (`<app-name>`) after confirming least-privilege scope requirements. We have updated the permissions / assignment and cleared the `AADSTS` consent or secret error. Please acquire a fresh token and let us know if your test call succeeds.
- **FR:** Bonjour `<user>`, nous avons vérifié les permissions demandées pour votre application Entra ID (`<app-name>`) selon le principe du moindre privilège. L'approbation administrateur / l'assignation ou le secret a été mis à jour. Merci de renouveler votre jeton OAuth et de confirmer que l'authentification fonctionne.
