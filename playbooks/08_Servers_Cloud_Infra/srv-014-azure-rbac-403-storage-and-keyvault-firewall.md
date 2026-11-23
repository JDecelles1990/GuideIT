---
id: srv-014
domain: 08_Servers_Cloud_Infra
subject: Servers, Cloud & Infrastructure
subcategory: cloud_azure_gcp_docker
title: Azure RBAC 403 Errors, Storage Permission Mismatch & Key Vault Firewall Blocks
tier: L2
keywords_en:
  - azure rbac 403
  - authorization failed azure
  - authorization permission mismatch
  - key vault firewall forbidden
  - storage account 403 error
  - managed identity unauthorized
keywords_fr:
  - erreur 403 azure rbac
  - permission azure refusee
  - coffre cles key vault bloque
  - compte stockage azure 403
  - identite geree non autorisee
error_codes:
  - AuthorizationFailed
  - AuthorizationPermissionMismatch
  - KeyVaultFirewall
tags:
  - azure_rbac_403
  - azure_keyvault_storage
os:
  - cross_platform
environment:
  - azure
  - cloud_infra
tools:
  - Microsoft Azure Portal
  - Azure CLI (az)
  - PowerShell (Az.Resources / Az.KeyVault)
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-013
  - id-006
  - srv-002
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Screenshot the exact **`403`** message: does it say **"does not have authorization to perform action"** (Identity/RBAC missing -> `AuthorizationFailed` / `AuthorizationPermissionMismatch`), OR **"Client address is not authorized / Public network access is disabled"** (Firewall IP allow-list -> `KeyVaultFirewall`)?
2. Which **exact Azure Resource (`Subscription` / `Resource Group` / `Storage Account or Key Vault name`)** and which **user/app identity** needs access?
3. Did you **just activate a PIM role** or get assigned a role within the last 10 minutes (needs **Sign out + Sign in / `az login` refresh**!), and has the resource owner/client approved the permission request?

### Initial Scope & Classification
- Remember `Owner` / `Contributor` do **NOT** grant Storage/Key Vault **Data Plane** access (`Storage Blob Data Reader` / `Key Vault Secrets User`)!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Azure Portal IAM & Networking UI)
1. **Verify Correct Subscription & Sign-Out/In Refresh:** Have `jsmith@example.com` confirm the top-right Portal Directory + Subscription matches `<subscription-id>`, wait 5–10 minutes if role was just added, and sign out/back into Azure Portal!
2. **Check Resource `Access control (IAM) -> Check access` & `Networking` Tab in Azure Portal:**
   - Look under **Check access** for `jsmith@example.com` -> confirm Data Plane role (`Storage Blob Data Reader/Contributor`, `Key Vault Secrets User`) exists!
   - Open **Storage Account / Key Vault -> Networking -> Firewalls and virtual networks**: see if `Public network access` is set to **Selected networks** blocking the caller's office/VPN IP (`KeyVaultFirewall`)!

### L2 Technical Diagnostics
Verify caller context and enumerate effective Azure RBAC assignments across Subscriptions, Resource Groups, and Resources:

```bash
# Confirm active CLI account/tenant/subscription
az account show --output table

# Check effective inherited RBAC roles for a user or Managed Identity object ID
az role assignment list --assignee <user-upn-or-object-id> --scope /subscriptions/<subscription-id>/resourceGroups/<rg-name> --include-inherited --output table

# Check Storage Account firewall, Shared Key toggle, and network defaults
az storage account show --resource-group <rg-name> --name <storage-account> --query "{defaultAction:networkRuleSet.defaultAction,bypass:networkRuleSet.bypass,publicNetworkAccess:publicNetworkAccess,allowSharedKeyAccess:allowSharedKeyAccess}"

# Check Key Vault permission model (RBAC vs Access Policy) and Firewall ACLs
az keyvault show --resource-group <rg-name> --name <keyvault-name> --query "{enableRbacAuthorization:properties.enableRbacAuthorization,publicNetworkAccess:properties.publicNetworkAccess,networkAcls:properties.networkAcls}"
```

On an Azure VM or App Service experiencing Managed Identity `403`, test token acquisition locally (read-only metadata check on APIPA IMDS):

```bash
# Run INSIDE the Azure VM to inspect the Managed Identity JWT audience/oid (requires no credentials)
curl -s -H "Metadata:true" "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net/" | head -c 300
```

## Deep-Dive Investigation (L3)
Analyze why authorized identities still hit `403` across complex enterprise landing zones:

1. **Azure Storage `AllowSharedKeyAccess = false` + Legacy Connection Strings:** Security baselines disable storage account keys (`KeyBasedAuthenticationPermitted = False`). Code/tools using SAS or account keys fail even when the user has `Contributor` — the client must switch to Microsoft Entra auth (`az login` / `DefaultAzureCredential` + `Storage Blob Data Contributor`).
2. **Key Vault Permission Model Split (`enableRbacAuthorization = true` vs Access Policies):** When `enableRbacAuthorization: true` is active, legacy Key Vault Access Policies are **ignored**; the principal requires `Key Vault Secrets User` / `Key Vault Crypto User` in IAM (Access Control).
3. **Key Vault / Storage Network Firewall & Private Endpoint DNS:**
   - If `defaultAction: Deny`, requests originating from an external laptop or unpeered VNet are rejected (`KeyVaultFirewall`).
   - If using **Private Endpoints**, verify private DNS zones (`privatelink.vaultcore.azure.net` / `privatelink.blob.core.windows.net`) resolve to an RFC 1918 private IP rather than the public Azure IP.
4. **Deny Assignments & Azure Policy:** Check Portal **Resource -> Access control (IAM) -> Deny assignments** (often created automatically by Azure Blueprints, Managed Applications, or Databricks/AKS managed resource groups).

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER resolve `KeyVaultFirewall` or Storage `403` by setting `publicNetworkAccess = Enabled` and `defaultAction = Allow` on production security vaults or data lakes. Always prefer **Private Endpoints**, **Trusted Azure Services** bypass, or scoped admin/CI runner CIDR allow-lists, and scope RBAC strictly to the **Resource** or **Resource Group** (not Subscription-wide `Owner`).

1. **Assign Least-Privilege Data-Plane RBAC Role:**
   - Scope: Specific Key Vault or Storage Account resource scope (never broad Subscription `Contributor`/`Owner` for app data access).
   - Prerequisite: `User Access Administrator` or `Role Based Access Control Administrator` role + ticket approval.
   ```bash
   # Example: Grant Key Vault Secrets User only at the target Key Vault scope
   az role assignment create --assignee "<principal-object-id>" --role "Key Vault Secrets User" --scope "/subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.KeyVault/vaults/<keyvault-name>"

   # Example: Grant Storage Blob Data Reader/Contributor only at Storage Account scope
   az role assignment create --assignee "<principal-object-id>" --role "Storage Blob Data Reader" --scope "/subscriptions/<subscription-id>/resourceGroups/<rg-name>/providers/Microsoft.Storage/storageAccounts/<storage-account>"
   ```
2. **Allow Authorized Jumpbox IP / VNet / Trusted Services on Firewall:**
   - **[REMEDIATION — CONFIRM BEFORE RUNNING]** Add only explicit corporate egress / MSP jumpbox CIDR (`198.51.100.10/32`) or target VNet subnet, or enable **Allow trusted Microsoft services to bypass this firewall** when supported by the workload.
   - If accessing via Private Endpoint, verify VNet DNS links to `privatelink.vaultcore.azure.net` / `privatelink.blob.core.windows.net`.
3. **Refresh Cached Entra Tokens / Activate PIM:**
   - After RBAC assignment, wait up to 5–10 minutes and instruct the developer/admin to run `az account clear && az login` (or restart the App Service/container holding stale Managed Identity tokens).

## Verification & Post-Fix Checks
- Verify `az role assignment list --scope <resource-id>` lists only the exact least-privilege Data Plane role needed (`Key Vault Secrets User`, `Storage Blob Data Reader`, etc.).
- Verify Key Vault / Storage `networkRuleSet.defaultAction` remains `Deny` (if firewall-protected) and confirm `nslookup <vault>.vault.azure.net` resolves via Private Endpoint when inside VNet/VPN.
- Have the user/service test secret read or blob operation and confirm HTTP `200 OK` without `AuthorizationFailed` or `AuthorizationPermissionMismatch`.

## Cross-Subject Escalation & Pivot Links
- **Inspect VM/NIC Boot Diagnostics or Serial Console if RBAC blocks compute triage:** [srv-013 — Azure VM Boot Failures, RDP/SSH Unreachable, NSG & Serial Console Triage](./srv-013-azure-vm-boot-rdp-ssh-and-serial-console.md)
- **App Registration or Managed Identity also fails Microsoft Graph API permissions/consent:** [id-006 — Entra ID App Registration Permissions, Admin Consent & Developer Secret Failures](../01_Identity_AD_Entra/id-006-entra-app-registration-permissions-and-admin-consent.md)
- **Equivalent IAM 403 and Org Policy debugging on Google Cloud Platform (GCP):** [srv-002 — Google Cloud Console IAM 403, Org Policy, Billing Suspension, and Quota Triage](./srv-002-google-cloud-console-iam-billing-and-quota.md)

## Useful Links & External Tools
- [Microsoft Azure Portal](https://portal.azure.com/) — Inspect IAM role assignments, Deny assignments, Networking firewall rules, and Key Vault Access configuration.
- [Microsoft Entra AADSTS Error Code Lookup](https://login.microsoftonline.com/error) — Decode identity token errors impacting Azure CLI or Managed Identity calls.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we resolved the Azure `403` error (`<AuthorizationFailed / AuthorizationPermissionMismatch / KeyVaultFirewall>`) on `<resource-name>` by verifying Data Plane RBAC vs. network firewall rules and applying the minimum scoped permission (`<role-or-private-access-fix>`). Please refresh your `az login` / app token and test again.
- **FR:** Bonjour `<user>`, nous avons résolu l'erreur Azure `403` (`<AuthorizationFailed / AuthorizationPermissionMismatch / KeyVaultFirewall>`) sur `<resource-name>` en ajustant les droits RBAC du plan de données ou la règle réseau autorisée (`<détail>`). Merci de renouveler votre session/jeton et de revalider l'accès.
