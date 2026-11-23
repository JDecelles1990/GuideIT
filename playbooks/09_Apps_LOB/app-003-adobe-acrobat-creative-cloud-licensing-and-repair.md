---
id: app-003
domain: 09_Apps_LOB
subject: "Applications & LOB"
subcategory: office_pdf_adobe
title: Adobe Acrobat and Creative Cloud Licensing Errors, Sign-In Loops, and Repair
tier: L1
keywords_en:
  - adobe acrobat license error
  - creative cloud sign in loop
  - adobe expired subscription
  - adobe error 205 195
  - personal vs company account adobe
keywords_fr:
  - licence adobe acrobat introuvable
  - adobe creative cloud bloque
  - reparer adobe acrobat
  - erreur abonnement adobe expire
  - compte personnel ou professionnel adobe
error_codes:
  - ADOBE_LICENSE_ERR
  - "205"
  - "195"
tags:
  - adobe_licensing
  - adobe_acrobat_repair
os:
  - windows
  - macos
environment:
  - saas
  - local_endpoint
tools:
  - Adobe Admin Console
  - Adobe Acrobat Cleaner Tool
  - PowerShell
  - Browser DevTools
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - app-002
  - sec-003
  - mdm-007
  - app-001
---

## Fast Triage (Under 2 Minutes)
- **Most Common MSP Trap (`Personal` vs. `Company or School Account`):** When signing in with `jsmith@example.com`, Adobe often prompts to choose between **`Personal Account`** and **`Company or School Account`**! Choosing `Personal Account` logs into a free unlicensed profile and shows `"Buy Now / Trial Expired"` (`ADOBE_LICENSE_ERR`).
- Confirm inside [Adobe Admin Console](https://adminconsole.adobe.com/) that `jsmith@example.com` holds an active **Acrobat Pro** or **Creative Cloud** product assignment.
- Capture exact Creative Cloud installer/updater codes: **`205`** = proxy/firewall/VPN blocking Adobe licensing endpoints; **`195`** = OS version below Adobe minimum requirement.

## Read-Only Diagnostics (L1-L2)
1. **Verify License Assignment in Adobe Admin Console:**
   - Sign into `https://adminconsole.adobe.com/` -> **Users -> search `jsmith@example.com`** -> verify **Products** tab shows an active assigned license (not just `Adobe Acrobat Reader` free).
   - If the client uses **Entra ID / Google Workspace Federated SSO** (`Directory`), confirm the user exists in the synced Adobe User Group!
2. **Check Installed Adobe Version & Network Connectivity on `PC-LAB-01` (read-only):**
   ```powershell
   Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
       Where-Object { $_.DisplayName -like "*Adobe*" } |
       Select-Object DisplayName, DisplayVersion | Sort-Object DisplayName
   Test-NetConnection -ComputerName "ims-na1.adobelogin.com" -Port 443 | Select-Object ComputerName, TcpTestSucceeded
   ```
3. **Check Acrobat Reader vs. Pro Installed:** Users often accidentally open **Adobe Acrobat Reader** (or have both Reader and Pro installed) instead of full **Adobe Acrobat Pro**, OR switched into `"New Acrobat"` UI hiding familiar menus.

## Deep-Dive Investigation (L3)
1. **Corrupted `OOBE` / `SLCache` / `NGLEmp` Local Licensing Cache (`ADOBE_LICENSE_ERR` Loop):** Upgrading from serialized volume Acrobat (`2017`/`2020`) to Named User Licensing leaves stale `SLStore` / `OOBE` tokens that ignore new cloud entitlements.
2. **Proxy / SSL Inspection Breaking Certificate Pinning (`Error 205`):** Adobe Creative Cloud Desktop and Acrobat licensing endpoints require TLS bypass (no SSL decryption/inspection) for `*.adobelogin.com` and `*.adobe.io` (`[sec-003]`).
3. **macOS Keychain / Credential Conflict:** On macOS, stale `Adobe User OS Info` / `Adobe App Info` items inside **Keychain Access.app -> login** cause endless sign-in loops (`[mdm-002]`).

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Sign Out and Re-Select `Company or School Account`:**
   - Open Adobe Acrobat / Creative Cloud Desktop -> click top-right profile icon -> **Sign out**.
   - Sign back in with `jsmith@example.com` -> when prompted, explicitly click **`Company or School Account`** (never `Personal Account`) and complete Entra/Google SSO!
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Reset Local Adobe Licensing `OOBE` Cache (Safe — Forces Clean Re-Auth; Requires Closing All Adobe Apps):**
   - **Windows:** Close Acrobat and `Creative Cloud.exe`, then rename `%LOCALAPPDATA%\Adobe\OOBE` to `OOBE.bak` and relaunch Acrobat/Creative Cloud.
   - **macOS:** Quit Adobe apps (`⌘ + Q`), rename `~/Library/Application Support/Adobe/OOBE` to `OOBE.bak`, and delete stale `Adobe` login tokens in Keychain Access if looping.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Broken Installation or Mixed Reader/Pro Repair:** Close all Office/Adobe apps, run the official **[Adobe Acrobat Cleaner Tool](https://www.adobe.com/devnet-docs/acrobatetk/tools/Labs/cleaner.html)** (requires local admin), reboot, and deploy a clean package from Adobe Admin Console or Intune.

## Verification & Post-Fix Checks
1. Launch Adobe Acrobat -> **Help -> About Adobe Acrobat Pro** (or **Account** profile) and confirm active subscription license under `jsmith@example.com`.
2. Test opening, editing/commenting, and saving a PDF document (plus Outlook/File Explorer PDF preview per `[app-002]`) with zero trial/sign-in popups.

## Cross-Subject Escalation & Pivot Links
- **Corrupt Acrobat handler crashes Outlook attachment preview or Explorer preview pane:** [app-002 — Excel/Word Freezing on Open, COM Add-in Conflict, and PDF Previewer Failure](./app-002-office-addins-crash-and-pdf-preview-failure.md)
- **Adobe licensing/activation SSL fails behind proxy or outdated Root CA:** [sec-003 — TLS/SSL Certificate Expired, Missing Intermediate Chain, and Untrusted Root CA](../06_Security_Access/sec-003-tls-ssl-certificate-expired-and-untrusted-ca.md)
- **Licensing cleanup or Creative Cloud issue occurs on macOS endpoint:** [mdm-007 — Beginner macOS Finder SMB Network Share, DNS Flush, and Office Mac Licensing](../07_macOS_Mobile_MDM/mdm-007-macos-finder-smb-share-and-office-licensing.md)
- **Adobe Federated ID SSO login loops endlessly in embedded/system browser:** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](./app-001-browser-sso-and-lob-crash.md)

## Useful Links & External Tools
- **[Adobe Admin Console](https://adminconsole.adobe.com/)** — Assign Acrobat Pro / Creative Cloud licenses, check SSO directory sync, and generate managed enterprise installers.
- **[Adobe Acrobat Cleaner Tool & Enterprise Docs](https://www.adobe.com/devnet-docs/acrobatetk/tools/Labs/cleaner.html)** — Official Adobe cleanup utility to wipe corrupted Acrobat/Reader installs and licensing stores cleanly before reinstalling.

## Client Update Snippets (EN / FR)
- **EN:** We verified your Adobe license assignment, refreshed the local sign-in cache on `PC-LAB-01`, and confirmed sign-in via your **Company or School Account**. Please reopen Adobe Acrobat and confirm editing/PDF features work normally.
- **FR:** Nous avons vérifié votre licence Adobe, réinitialisé le cache de connexion sur `PC-LAB-01` et validé la connexion avec votre **compte professionnel ou scolaire**. Pouvez-vous rouvrir Adobe Acrobat et confirmer que tout fonctionne ?
