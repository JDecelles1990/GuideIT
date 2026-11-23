---
id: id-002
domain: 01_Identity_AD_Entra
subject: "Identity / AD & Entra ID"
subcategory: lockout_mfa_recovery
title: Google Workspace Admin Console 2SV Lockout, Role 403, and Suspended User Recovery
tier: L2
keywords_en:
  - google admin console
  - admin.google.com
  - google workspace suspended
  - google 2sv lockout
  - google admin 403
keywords_fr:
  - console admin google
  - compte google suspendu
  - validation en deux etapes google
  - acces refuse admin google
  - compte workspace bloque
error_codes:
  - "403"
  - ERROR_2SV
tags:
  - google_workspace_admin
  - google_2sv_lockout
os:
  - cross_platform
environment:
  - google_workspace
  - saas
tools:
  - Google Admin Console
  - Browser DevTools
  - DNS Lookup
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - m365-004
  - srv-002
  - id-006
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you blocked from signing into your **normal user mailbox/Drive** (2-Step Verification / lost phone / suspended), or is an **Admin getting `403`** / `"You need a Google Workspace account to access admin.google.com"`?
2. Do you have personal `@gmail.com` accounts signed into Chrome in the same browser window?
3. Did you get a new phone, change your phone number, or travel outside your usual city/country right before the lock challenge appeared?

### Initial Scope & Classification
- Verify identity out-of-band before issuing any 2-Step Verification (2SV) backup codes or unlocking a suspended account.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Isolate Multi-Account Browser Confusion (`403` on `admin.google.com`):** Have `admin@contoso.com` open an **Incognito / InPrivate** window and sign directly into `https://admin.google.com` using ONLY the corporate Workspace account (fixes ~60% of admin `403` errors!).
2. **Check Google Account Status in Admin Console (`admin.google.com`):** Go to **Directory -> Users -> `jsmith@example.com` -> Security** -> verify whether **Account status** shows `Active`, `Suspended — Admin`, or `Suspended — Risk / Abuse` (never unsuspend `Risk / Abuse` without checking compromise logs first!).

### L2 Technical Diagnostics
1. **Inspect Account, Admin Roles, and 2SV Enforcement in Google Admin Console (`admin.google.com`):**
   - Navigate to **Directory -> Users -> `jsmith@example.com` -> Security**:
     - Check **Account status** (`Active` vs `Suspended — Admin` vs `Suspended — Risk / Abuse`).
     - Check **2-Step Verification** enrollment, **Login challenge** status, and whether the user's **Organizational Unit (OU)** enforces mandatory 2SV without a grace period.
   - Check **Account -> Admin roles**: verify `admin@contoso.com` actually holds **Super Admin** or required delegated admin privileges for the target OU.
3. **Review Audit Logs:** Check **Reporting -> Audit and investigation -> User log events** and **Admin log events** for failed logins, password changes, or automatic suspension triggers.

## Deep-Dive Investigation (L3)
1. **Abuse / Suspicious Activity Auto-Suspension:** If Google automatically suspended `jsmith@example.com` for spam/compromise, inspect **Gmail logs** and **OAuth token grants** (`Security -> API controls -> Manage Third-Party App Access`) BEFORE reactivating so compromised sessions do not keep abusing the mailbox.
2. **Third-Party SAML SSO Loop / Admin Lockout:** If the Workspace domain routes logins to an external IdP (Entra ID / Okta), Super Admins normally bypass SSO when signing in directly (`admin.google.com`), whereas standard users fail if the IdP certificate expired or SAML NameID doesn't match the Workspace primary email.
3. **Lost Last Super Admin Access:** If ALL Super Admins lost 2SV, prepare the domain's DNS registrar access for Google's **Super Admin Account Recovery** TXT/CNAME DNS verification challenge.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **2SV Lockout** (`ERROR_2SV`), in Google Admin Console open **`jsmith@example.com` -> Security -> 2-Step Verification -> Get backup verification codes** (provide one single-use 8-digit code out-of-band) or temporarily **Turn Off Login Challenge** for 10 minutes if a new location/device triggered Google's anti-hijack challenge.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **Suspended Accounts** (after ruling out compromise), open the user profile -> **More options -> Reactivate user**, reset the password if required, and enforce fresh 2SV re-enrollment.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **`403` Missing Admin Privileges**, sign in as a verified Super Admin, open **Account -> Admin roles**, and assign the scoped role (`User Management Admin`, `Help Desk Admin`, or `Groups Admin`) to `admin@contoso.com`.

## Verification & Post-Fix Checks
1. Have `jsmith@example.com` complete sign-in in a clean browser session and re-register their primary 2SV authenticator / passkey.
2. Confirm **User log events** shows a clean successful login and account status remains **Active**.

## Cross-Subject Escalation & Pivot Links
- **Workspace Admin access works yet Gmail delivery bounces (550 5.7.26) or Shared Drive fails:** [m365-004 — Google Workspace Gmail Delivery Bounce (550 5.7.26) and Shared Drive Access Triage](../02_M365_Email_Collab/m365-004-google-workspace-gmail-ndr-and-drive-access.md)
- **Workspace Super Admin access restored yet GCP Console IAM 403 or Cloud Billing blocks remain:** [srv-002 — Google Cloud Console IAM 403, Org Policy, Billing Suspension, and Quota Triage](../08_Servers_Cloud_Infra/srv-002-google-cloud-console-iam-billing-and-quota.md)
- **Third-party OAuth/SSO developer app permissions or admin consent block user sign-in:** [id-006 — Entra ID App Registration Permissions, Admin Consent & Developer Secret Failures](./id-006-entra-app-registration-permissions-and-admin-consent.md)

## Useful Links & External Tools
- **[Google Workspace Admin Console](https://admin.google.com/)** — Manage user suspensions, 2SV backup verification codes, admin roles, and audit log events (always use an isolated Incognito/work profile).
- **[Google Workspace Status Dashboard](https://www.google.com/appsstatus/dashboard/)** — Confirm whether Workspace sign-in or Admin Console is experiencing a service outage.

## Client Update Snippets (EN / FR)
- **EN:** We verified your Google Workspace account status, cleared the sign-in / 2-Step Verification block for `jsmith@example.com`, and confirmed access is restored. Please sign back in and re-verify your 2SV method.
- **FR:** Nous avons vérifié l'état de votre compte Google Workspace, levé le blocage de connexion / validation en deux étapes pour `jsmith@example.com` et rétabli l'accès. Veuillez vous reconnecter et revalider votre méthode 2FA.
