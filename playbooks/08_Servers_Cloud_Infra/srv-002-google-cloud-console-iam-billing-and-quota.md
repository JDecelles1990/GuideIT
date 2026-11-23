---
id: srv-002
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: cloud_azure_gcp_docker
title: Google Cloud Console IAM 403, Org Policy, Billing Suspension, and Quota Triage
tier: L3
keywords_en:
  - google cloud console error
  - gcp permission denied
  - google cloud billing disabled
  - cloud console 403
  - gcp quota exceeded
keywords_fr:
  - console google cloud acces refuse
  - quota gcp depasse
  - facturation google cloud desactivee
  - erreur permission gcp
  - google cloud 403
error_codes:
  - "403"
  - PERMISSION_DENIED
  - RESOURCE_EXHAUSTED
tags:
  - gcp_console_iam
  - gcp_billing_quota
os:
  - cross_platform
environment:
  - google_workspace
  - cloud_infra
  - saas
tools:
  - Google Cloud Console
  - gcloud CLI
  - Google Admin Console
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - id-002
  - m365-004
  - srv-014
---

## Fast Triage (Under 2 Minutes)
- What exact Google Cloud Console message appeared: **`PERMISSION_DENIED (403)`**, **`You do not have sufficient permissions`**, **`Billing account not linked / disabled`**, **`Service disabled by Org Policy`**, or **`RESOURCE_EXHAUSTED`**?
- Is the user (`admin@contoso.com`) signed into the exact right Google Workspace corporate identity and **Project ID** (`contoso-prod-app`) in the top selector?
- Did the client recently toggle **Google Cloud Platform** service availability off for an Organizational Unit inside **Google Admin Console (`admin.google.com`)**?

## Read-Only Diagnostics (L1-L2)
1. **Check Workspace Service Enablement (`admin.google.com`):**
   - In Google Admin Console, open **Apps -> Additional Google services -> Google Cloud Platform** and verify it is **ON** for the user's **Organizational Unit (OU)** (if OFF, `console.cloud.google.com` rejects login even if IAM roles exist!).
2. **Inspect active `gcloud` identity, project IAM bindings, and billing status (read-only):**
   ```bash
   gcloud auth list
   gcloud config get-value project
   gcloud projects get-iam-policy contoso-prod-app --format="table(bindings.role,bindings.members)"
   gcloud billing projects describe contoso-prod-app
   ```
3. **Check Enabled APIs & Quotas (read-only):**
   ```bash
   gcloud services list --enabled --project=contoso-prod-app
   ```
   Also check **IAM & Admin -> Quotas & System Limits** in Cloud Console for any `100%` utilization alerts (`RESOURCE_EXHAUSTED`).

## Deep-Dive Investigation (L3)
1. **Organization Policy & IAM Deny Policies:** Run `gcloud resource-manager org-policies list --project=contoso-prod-app` (or inspect **IAM & Admin -> Organization Policies**) for restrictive constraints such as `iam.allowedPolicyMemberDomains` (blocking external collaborator emails), `compute.vmExternalIpAccess`, or `iam.disableServiceAccountKeyCreation`.
2. **VPC Service Controls (`PERMISSION_DENIED` with VPC-SC Request ID):** Check **Cloud Logging** (`Logs Explorer`) filtering by `protoPayload.metadata.violationReason` to verify whether a VPC Service Controls perimeter blocked access from an unapproved IP/device.
3. **Suspended / Delinquent Billing Account:** In **Billing -> Account Management**, confirm the linked Billing Account is **Active** (expired credit cards or overdue invoices automatically shut down paid APIs and Compute instances).
4. **Missing Organization Administrator Role:** If a Workspace Super Admin cannot see the Cloud Organization node, grant the Super Admin **`Organization Administrator`** (`roles/resourcemanager.organizationAdmin`) in Cloud Console **IAM** at the Organization scope.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If Google Cloud access was disabled at the Workspace OU level, enable **Google Cloud Platform** for the scoped OU/Group inside `admin.google.com` (never enable broadly if restricted by security policy).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Grant the least-privilege IAM role required on the project (`roles/viewer`, `roles/editor`, or targeted service role — avoid `roles/owner` unless strictly required):
   ```bash
   gcloud projects add-iam-policy-binding contoso-prod-app \
       --member="user:jsmith@example.com" \
       --role="roles/viewer"
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Enable a required disabled API or link an active Billing Account (requires Billing Admin / Service Usage Admin):
   ```bash
   gcloud services enable compute.googleapis.com --project=contoso-prod-app
   ```
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For **`RESOURCE_EXHAUSTED`**, submit a **Quota Increase** request in **IAM & Admin -> Quotas** or scale down runaway scheduled jobs/API loops before raising limits.

## Verification & Post-Fix Checks
1. Confirm `gcloud projects get-iam-policy contoso-prod-app` reflects the expected role binding and `billingEnabled: true`.
2. Have `jsmith@example.com` refresh `https://console.cloud.google.com` in an Incognito corporate session and verify the target resource loads without `403` or billing warnings.

## Cross-Subject Escalation & Pivot Links
- **GCP IAM 403 traces to suspended Google Workspace account, 2SV lock, or org group change:** [id-002 — Google Workspace Admin Console 2SV Lockout, Role 403, and Suspended User Recovery](../01_Identity_AD_Entra/id-002-google-workspace-admin-2sv-lockout.md)
- **Workspace user/domain state mismatches affect Drive and Cloud Identity groups:** [m365-004 — Google Workspace Gmail Delivery Bounce (550 5.7.26) and Shared Drive Access Triage](../02_M365_Email_Collab/m365-004-google-workspace-gmail-ndr-and-drive-access.md)
- **Parallel Azure RBAC 403 / Key Vault / Storage permissions workflow for multi-cloud MSPs:** [srv-014 — Azure RBAC 403 Errors, Storage Permission Mismatch & Key Vault Firewall Blocks](./srv-014-azure-rbac-403-storage-and-keyvault-firewall.md)

## Useful Links & External Tools
- **[Google Cloud Console](https://console.cloud.google.com/)** — Review Project IAM bindings, Organization Policies, Billing status, and API Quotas.
- **[Google Workspace Admin Console](https://admin.google.com/)** — Verify the **Google Cloud Platform** service toggle is ON for the target user's Organizational Unit.

## Client Update Snippets (EN / FR)
- **EN:** We reviewed the Google Cloud Console IAM permissions / billing / service configuration for project `contoso-prod-app` and applied the approved fix. Please refresh the Cloud Console and confirm you can now access the required resources.
- **FR:** Nous avons vérifié les permissions IAM / la facturation / la configuration de service Google Cloud Console pour le projet `contoso-prod-app` et appliqué le correctif approuvé. Pouvez-vous actualiser la console Cloud et confirmer que l'accès fonctionne ?
