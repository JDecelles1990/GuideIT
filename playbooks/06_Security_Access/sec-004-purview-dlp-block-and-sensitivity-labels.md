---
id: sec-004
domain: 06_Security_Access
subject: Security & Access
subcategory: tls_certs_purview_dlp
title: Microsoft Purview DLP Policy Blocks & Sensitivity Label Encryption Denied
tier: L2
keywords_en:
  - purview dlp blocked
  - sensitivity label access denied
  - cannot open encrypted document
  - information protection rms error
  - policy tip blocking sharepoint email
  - file encrypted confidential cannot decrypt
keywords_fr:
  - blocage dlp purview courriel
  - etiquette sensibilite acces refuse
  - fichier chiffre impossible ouvrir
  - erreur protection information rms
  - politique dlp bloque partage
error_codes:
  - DLP_POLICY_TIP
  - RMS_ACCESS_DENIED
tags:
  - purview_dlp_block
  - sensitivity_label_denied
os:
  - cross_platform
environment:
  - m365
  - entra_id
tools:
  - Microsoft Purview Portal
  - PowerShell (ExchangeOnlineManagement / IPPSSession)
  - Microsoft 365 Apps / Office Account
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - m365-002
  - m365-007
  - m365-008
  - sec-001
linked_scripts:
  - 03_M365/Get-EntraRegistrationStatus.ps1
  - 03_M365/Get-OfficeActivationStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you blocked **BEFORE opening/sending** by a red/yellow Microsoft **"Policy Tip / This item is blocked from sharing externally" (`DLP_POLICY_TIP`)**, OR are you blocked **trying to open an already encrypted file** (`"You don't have permissions to view this document"` / `RMS_ACCESS_DENIED`)?
2. For **`RMS_ACCESS_DENIED`**: check the **top-right name/email inside Word/Excel/Edge** — are you signed into Office with the exact email address the sender invited (`jsmith@contoso.com`), or a different account?
3. For **`DLP_POLICY_TIP`**: does the email/file contain sensitive numbers (credit cards, SIN/SSN, health/bank info), and has your manager/sender confirmed this external recipient is authorized?

### Initial Scope & Classification
- Distinguish **DLP Block (`DLP_POLICY_TIP`)** vs **Sensitivity Label / IRM Encryption (`RMS_ACCESS_DENIED`)** — **NEVER** bypass DLP policies without confirming authorized business justification!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Account Sign-In & Web Fallback)
1. **For `RMS_ACCESS_DENIED` (File Won't Decrypt / Open):**
   - Look at **top-right corner of Word / Excel -> File -> Account**: confirm the primary connected email matches the exact address that received the link/email (`jsmith@contoso.com`)! Sign out of conflicting secondary/personal accounts (`@gmail.com` / `@fabrikam.com`).
   - Ask the user to try opening the file in **Word / Excel for the Web** via SharePoint/OneDrive browser link (browser auth cleanly acquires modern RMS decryption tokens!).
   - If the sender encrypted it with an **"Internal Only / Confidential — Employees Only"** label and sent it to an external partner, only the **document owner** (or authorized admin) can change the label to an approved External Partner label!
2. **For `DLP_POLICY_TIP` (Blocked External Email / Share):** Screenshot the exact yellow/red Policy Tip text (shows WHICH Sensitive Info Type triggered, e.g., *Credit Card*, often caused by false-positive invoice IDs in email signatures!) and ask Purview Admin / L2 to inspect Alerts before approving any override!

### L2 Technical Diagnostics
Connect to Microsoft Purview Compliance PowerShell (`Connect-IPPSSession` from `ExchangeOnlineManagement`) to inspect active DLP policies, rules, and Sensitivity Labels without altering protections:

```powershell
# Connects to Microsoft Purview Security & Compliance PowerShell
Connect-IPPSSession

# List enabled DLP policies and their enforcement mode (Enable vs TestWithNotifications)
Get-DlpCompliancePolicy | Select-Object Name, Enabled, Mode, ExchangeLocation, SharePointLocation, OneDriveLocation, TeamsLocation |
  Format-Table -AutoSize

# Inspect DLP rule actions and override settings
Get-DlpComplianceRule | Select-Object Name, ParentPolicyName, BlockAccess, BlockAccessScope, NotifyAllowOverride |
  Format-Table -AutoSize

# Inspect configured Sensitivity Labels (Encryption / ContentMarking)
Get-Label | Select-Object DisplayName, Name, Tooltip, EncryptionEnabled, ContentType | Format-Table -AutoSize
```

On Windows endpoints experiencing `RMS_ACCESS_DENIED`, inspect device Entra registration and Office identity context cleanly:

```powershell
# Confirm device Entra join / PRT token health for Rights Management decryption
dsregcmd /status
```

In **Microsoft Purview Portal**, inspect:
1. **Data loss prevention -> Alerts** / **Activity explorer** to confirm exact matched **Sensitive Information Type (SIT)**, confidence level, and file/email sender.
2. **Exchange Message Trace** (if blocked on outbound mail) to confirm whether an Exchange Transport Rule vs Purview DLP rule rejected/quarantined the message.

## Deep-Dive Investigation (L3)
Pinpoint why legitimate work triggers DLP or RMS failures:
1. **DLP False Positives on Structured Strings:** Invoice numbers, project IDs, or phone numbers matching weak Low-Confidence SIN/SSN/Credit Card patterns (`Luhn` false matches in signatures or PDFs) trigger `DLP_POLICY_TIP`. Check instance counts and confidence levels inside **Purview Activity Explorer**.
2. **Sensitivity Label Scope Mismatch (`RMS_ACCESS_DENIED`):**
   - The file carries a label configured **Assign permissions now** limited to an internal security group that excludes the recipient (`jsmith@contoso.com`), or excludes external B2B guests.
   - Or the recipient works on an external tenant whose Conditional Access / Cross-Tenant Access blocks authenticating to the sender's Rights Management Service (`RMS`), or the user lacks an assigned **Microsoft 365 / Purview Information Protection** license (`RightsManagement` service plan) to decrypt/re-label.
3. **Stale Windows Office / ADAL Token Cache:** Password changes or MFA updates leave Office caching an old RMS license/token (`UseLicense`) until signed out and re-authenticated.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER disable an entire DLP policy or strip Sensitivity Label encryption across a SharePoint library to fix one user's blocked email/file. Always apply the narrowest approved exception (Authorized Business Override, explicit recipient permission on the file, or SIT minimum-count tuning approved by the security owner).

1. **Legitimate External Send Blocked by DLP (`DLP_POLICY_TIP`):**
   - Scope: Single approved transfer or business workflow exception.
   - Prerequisite: Manager / Data Owner approval confirming no unauthorized PII exposure.
   - Use Purview's **NotifyAllowOverride (Allow user override with business justification)** workflow where configured, OR have the sender redact unnecessary sensitive data before resending, OR refine the specific DLP rule's exception (approved partner domain / sender group) under change control.
2. **Encrypted File Cannot Be Opened (`RMS_ACCESS_DENIED`):**
   - **Step A (User-side identity check):** Confirm Microsoft Word/Excel/Edge top-right account matches the exact invited recipient UPN (`jsmith@contoso.com`), sign out of conflicting secondary accounts, and retry opening via **SharePoint / Word for the Web** (encrypted browser fallback).
   - **Step B (Owner-side permission update):** If the recipient wasn't included in the label's encryption scope, ask the **document owner** (or authorized Purview **Content Explorer / Super User** under incident approval) to apply an approved **Confidential — External Partner** label or add `<recipient-upn>` explicitly rather than stripping protection altogether.
3. **Endpoint RMS License/Token Refresh:**
   - Have the user verify M365 license includes Rights Management, update M365 Apps to Current/Monthly Enterprise Channel, and refresh Office sign-in session.

## Verification & Post-Fix Checks
- Verify the approved email/file passes Purview DLP or opens cleanly in Microsoft 365 desktop + web apps for the intended recipient (`jsmith@contoso.com`).
- Confirm in **Purview Activity Explorer** that no global DLP policies were left disabled or switched back to `Disable` mode.
- Record business justification approval in the ticket for audit compliance.

## Cross-Subject Escalation & Pivot Links
- **Sensitivity Label / IRM encryption leaves shared Excel file locked read-only:** [m365-002 — Shared Excel Workbook Cannot Be Modified, Read-Only, or Locked for Editing](../02_M365_Email_Collab/m365-002-excel-shared-workbook-locked-readonly.md)
- **External B2B guest invited to Teams hits RMS_ACCESS_DENIED opening protected files:** [m365-007 — Microsoft Teams External Federation & B2B Guest Access Blocked](../02_M365_Email_Collab/m365-007-teams-external-guest-access-and-federation.md)
- **Purview Retention Policy / Hold fills Recoverable Items (100 GB) causing mailbox full 554 5.2.2:** [m365-008 — Exchange Online Mailbox Full (554 5.2.2) & Online Archive Not Moving Mail](../02_M365_Email_Collab/m365-008-exchange-mailbox-full-and-online-archive-stuck.md)
- **Unexpected mass sensitive file sharing DLP alert signals compromised insider session:** [sec-001 — Suspected Business Email Compromise and Session Token Theft](./sec-001-bec-token-compromise.md)

## Useful Links & External Tools
- [Microsoft Purview Portal](https://purview.microsoft.com/) — Inspect DLP Alerts, Activity Explorer, Sensitive Information Types, and Sensitivity Label definitions.
- [Microsoft 365 Admin Center](https://admin.microsoft.com/) — Verify user M365 Information Protection / Rights Management licensing.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we reviewed the Microsoft Purview `<DLP block / Sensitivity Label encryption>` alert (`<DLP_POLICY_TIP / RMS_ACCESS_DENIED>`). Because this protection safeguards sensitive data, we kept tenant policies active and applied the scoped resolution (`<account sign-in refresh / approved recipient permission / justified override>`). Please reopen the document or resend the approved item and confirm.
- **FR:** Bonjour `<user>`, nous avons analysé le blocage Microsoft Purview (`<DLP_POLICY_TIP / RMS_ACCESS_DENIED>`). Tout en maintenant la protection globale des données actives, nous avons appliqué l'ajustement ciblé (`<réauthentification compte M365 / ajout permission destinataire / dérogation justifiée>`). Merci de rouvrir le document ou de relancer l'envoi et de confirmer.
