---
id: win-008
domain: 03_Windows_Endpoints
subject: "Windows Endpoints"
subcategory: updates_win11_licensing
title: Windows Activation, KMS/ADBA, and Entra Subscription Licensing Errors
tier: L2
keywords_en:
  - windows not activated
  - activate windows watermark
  - windows license error
  - kms activation failed
  - windows 11 pro enterprise license
keywords_fr:
  - windows non active
  - erreur licence windows
  - cle produit windows invalide
  - filigrane activer windows
  - activation kms windows echouee
error_codes:
  - "0xC004F074"
  - "0xC004C003"
  - "0xC004F050"
  - "0x8007007B"
  - "0x803FA067"
tags:
  - windows_activation
  - windows_licensing_kms
os:
  - windows
environment:
  - local_endpoint
  - hybrid_ad
  - entra_id
  - intune
tools:
  - PowerShell
  - slmgr
  - clipup
  - Microsoft 365 Admin Center
risk_level: low
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-012
  - net-001
  - mdm-001
  - win-005
linked_scripts:
  - 01_System/Get-OSInformation.ps1
  - 03_M365/Get-OfficeActivationStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you seeing the **"Activate Windows — Go to Settings to activate Windows"** watermark, OR an error in **Settings -> System -> Activation** (`0xC004F074`, `0xC004C003`, `0xC004F050`, `0x8007007B`, `0x803FA067`)?
2. Is `PC-LAB-01` currently on **Windows Home, Pro, or Enterprise** (`winver` / System -> About), and was it recently **re-imaged**, **repaired (motherboard swap)**, or running **off corporate VPN for months**?
3. What licensing model does the client use (**M365 Business Premium / E3 Enterprise Subscription**, **OEM laptop key**, or **on-prem AD KMS/ADBA**)?

### Initial Scope & Classification
- **`0xC004F074`:** Cannot reach internal KMS server (often remote laptop off VPN or imaged with Volume GVLK instead of OEM key); **`0xC004C003`:** Invalid/Home key; **`0xC004F050`/`0x803FA067`:** Edition mismatch (Home vs Pro).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Windows Activation UI & M365 Portal)
1. **Inspect Settings -> System -> Activation (`Troubleshoot`):** Expand the **Activation state** arrow to record exact error code + Edition (`Windows 11 Pro` vs `Home` vs `Enterprise`), and try clicking **Troubleshoot** (for OEM hardware changes or Microsoft Store digital licenses!).
2. **Check M365 License & Connect VPN (If KMS/Entra Subscription):**
   - If the company uses **M365 Business Premium / E3 / E5**, verify in **M365 Admin Center ([Microsoft 365 Admin Center](https://admin.microsoft.com/))** that `jsmith@example.com` actually has an active license assigned, have the user sign out/in (`Work or school account`), and wait 5 minutes!
   - If the error is `0xC004F074` (`KMS`), test connecting **corporate VPN** (`[net-006]`) or plugging into office LAN first!

### L2 Technical Diagnostics
1. **Inspect Current Windows Edition, License Status, Channel, and Partial Key (read-only):**
   ```cmd
   slmgr /dlv
   slmgr /xpr
   ```
   ```powershell
   Get-CimInstance SoftwareLicensingProduct -Filter "PartialProductKey IS NOT NULL" |
       Where-Object { $_.Name -like "Windows*" } |
       Select-Object Name, Description, LicenseStatus, PartialProductKey
   Get-CimInstance SoftwareLicensingService | Select-Object OA3xOriginalProductKey, KeyManagementServiceMachine, KeyManagementServiceLookupDomain
   ```
   *(Look at `Description`: `OEM_DM` = firmware key; `VOLUME_KMSCLIENT` = KMS client waiting for internal KMS/ADBA server; `SUBSCRIPTION` = Entra/M365 license upgrade!)*
2. **Verify KMS SRV DNS Record (`0xC004F074` / `0x8007007B`, read-only):**
   ```powershell
   Resolve-DnsName -Name "_vlmcs._tcp.domain.local" -Type SRV -ErrorAction SilentlyContinue
   ```
3. **Check Entra Subscription Activation Readiness:** Verify `jsmith@example.com` holds an active **Windows 10/11 Enterprise** or **Business** sub-SKU in **M365 Admin Center -> Licenses**, and verify `dsregcmd /status` shows `AzureAdJoined : YES` + valid PRT (`[id-001]` / `[mdm-008]`).

## Deep-Dive Investigation (L3)
1. **BIOS OEM Pro Overwritten by KMS GVLK (`0xC004F074` on Remote Laptops):** Often happens when an OEM Windows Pro laptop was imaged with a Volume ISO/GVLK instead of activating its built-in motherboard `OA3xOriginalProductKey`! Remote users lose activation every 180 days because they never reach an internal KMS host.
2. **Windows Subscription Activation Stuck on Pro Instead of Enterprise (`clipup`):** Confirm the `ClipSVC` service is running, **Windows Store / Microsoft Account Sign-in** endpoints aren't blocked by firewall/proxy, and run `dsregcmd /status` to ensure Entra device state is healthy.
3. **System Clock Skew (`0xC004F074`):** Ensure `PC-LAB-01` date/time is accurate (`[srv-012]`) — KMS/TLS activation rejects drifted clocks.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Restore OEM Firmware Product Key (When `OA3xOriginalProductKey` Exists on `VOLUME_KMSCLIENT` Laptops):**
   ```powershell
   $oemKey = (Get-CimInstance SoftwareLicensingService).OA3xOriginalProductKey
   if ($oemKey) {
       changepk.exe /ProductKey $oemKey
   }
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Re-Trigger Windows Subscription Activation (Entra Joined + M365 Business Premium / E3 / E5):**
   ```cmd
   clipup -v -o
   ```
   *(Wait 2 minutes, or have `jsmith@example.com` lock/sign out and sign back in to refresh the Entra license token.)*
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Activate Domain Host Against Approved Internal KMS / ADBA (Verify Edition Key First):**
   - Look up ONLY the official Microsoft public GVLK matching the installed edition on [Microsoft KMS Client Setup Keys](https://learn.microsoft.com/en-us/windows-server/get-started/kms-client-activation-keys) (never use third-party activator tools!).
   ```cmd
   slmgr /ipk <OFFICIAL-MICROSOFT-GVLK-FOR-EDITION>
   slmgr /ato
   ```
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Upgrade Windows Home -> Pro (Required Before Intune/Domain Join):** Enter the purchased legitimate Windows Pro Retail/Upgrade key under **Settings -> System -> Activation -> Change product key** (`changepk.exe /ProductKey <LICENSED-KEY>`).

## Verification & Post-Fix Checks
1. Run `slmgr /xpr` and confirm **`The machine is permanently activated`** (or valid KMS/Subscription activation window).
2. Confirm **Settings -> System -> Activation** reports **`Active`** with the intended Windows edition (`Windows 11 Pro` or `Windows 11 Enterprise`).

## Cross-Subject Escalation & Pivot Links
- **Internal KMS DNS SRV (_vlmcs._tcp) lookup or Kerberos clock skew fails on-prem activation:** [srv-012 — Windows Server DHCP Scope Exhausted, DNS AD Load Failure, and Kerberos Time Skew](../08_Servers_Cloud_Infra/srv-012-windows-dhcp-exhausted-dns-forwarder-and-ntp-skew.md)
- **VPN/proxy blocks port 1688 KMS host or Microsoft cloud activation endpoints:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **Entra Subscription Activation (Pro -> Enterprise) stalls due to Intune/Entra desync:** [mdm-001 — macOS and iOS Intune MDM Sync and Conditional Access Compliance Failure](../07_macOS_Mobile_MDM/mdm-001-intune-compliance-sync.md)
- **Windows 11 edition mismatch triggers 0xC004F074 activation failure after upgrade:** [win-005 — Intune Windows 10 to Windows 11 Migration, Feature Updates, and Safeguard Holds](./win-005-intune-windows-11-migration-and-safeguard-holds.md)

## Useful Links & External Tools
- **[Microsoft KMS Client Setup Keys (GVLK)](https://learn.microsoft.com/en-us/windows-server/get-started/kms-client-activation-keys)** — Official Microsoft Learn table of public KMS/ADBA GVLKs by Windows 10/11 and Server edition.
- **[M365 Maps (Microsoft Licensing Matrix)](https://m365maps.com/)** — Quickly confirm whether `jsmith@example.com`'s M365 Business Premium / E3 / E5 SKU includes Windows Enterprise Subscription Activation.
- **[Microsoft 365 Admin Center](https://admin.microsoft.com/)** — Verify active Windows / M365 license assignments on the user account.

## Client Update Snippets (EN / FR)
- **EN:** We verified the Windows product license on `PC-LAB-01`, restored the proper OEM / Entra subscription activation, and confirmed Windows now shows **Active**. Could you check **Settings -> System -> Activation** once to confirm the watermark is gone?
- **FR:** Nous avons vérifié la licence Windows sur `PC-LAB-01`, rétabli l'activation OEM / abonnement Entra appropriée et confirmé le statut **Actif**. Pouvez-vous vérifier que le filigrane d'activation a bien disparu ?
