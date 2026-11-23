---
id: sec-002
domain: 06_Security_Access
subject: "Security & Access"
subcategory: bec_defender_threats
title: Microsoft Defender ASR Rule or Antivirus Blocking Legitimate LOB App or Macro
tier: L2
keywords_en:
  - blocked download
  - defender blocked app
  - macro blocked
  - asr rule false positive
  - smartscreen blocked executable
keywords_fr:
  - telechargement bloque
  - application bloquee par defender
  - faux positif antivirus
  - macro bloquee office
  - regle asr defender
error_codes:
  - "1121"
  - "1122"
tags:
  - defender_asr_block
  - false_positive_block
os:
  - windows
environment:
  - entra_id
  - m365
  - intune
  - local_endpoint
tools:
  - Microsoft Defender XDR
  - Intune Admin Center
  - PowerShell
  - Event Viewer
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - app-002
  - win-006
  - sec-001
linked_scripts:
  - 05_Security_Defender/Get-DefenderStatus.ps1
  - 05_Security_Defender/Invoke-DefenderUpdateAndScan.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. What **exact software, Excel macro, or file download** was blocked (`C:\Path\To\LobApp.exe`), and **where did it come from** (trusted vendor/SharePoint vs unknown email attachment)?
2. Screenshot the exact Windows popup/banner (`"Your IT administrator has limited access..."` = ASR rule vs `"Threat found / Quarantined"` = Antivirus vs `"Microsoft has blocked macros from running"` = Mark of the Web)!
3. Does this affect **only `PC-LAB-01`** or **multiple coworkers** trying to run the same business tool?
4. **Never whitelist blindly:** Confirm software legitimacy + SHA-256 hash before requesting any security exclusion!

### Initial Scope & Classification
- Separate **Microsoft Defender Antivirus Quarantine (`1116` / `1117`)**, **Attack Surface Reduction (ASR) Policy Block (`1121`)**, and **Office Mark of the Web macro block** cleanly.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Windows Security GUI & Origin Check)
1. **Check Windows Security Protection History (`windowsdefender://history`):** Open **Windows Security -> Virus & threat protection -> Protection history** on `PC-LAB-01` -> expand the top recent **`Protected folder access` / `Threat blocked` / `App & browser control`** item -> capture the exact **Affected items path** and timestamp!
2. **Verify Office Macro `"Unblock"` Checkbox (Only for Confirmed Safe Internal Files):** Right-click a blocked downloaded `.xlsm` -> **Properties** -> check if there is a **`Security: Unblock`** checkbox at the bottom (ONLY check this if the file came from a verified trusted internal source, NOT random internet/phishing mail -> `[sec-001]`!).
3. **Check File Digital Signature & Hash:** Check `Right-click EXE -> Properties -> Digital Signatures` to confirm it's legitimately signed by the business vendor, and check the SHA-256 hash against the threat-intelligence link below (without uploading client files!).

### L2 Technical Diagnostics
1. **Query Defender Operational Event Log for ASR blocks (`Event ID 1121` = Blocked, `1122` = Audited) and AV detections (read-only):**
   ```powershell
   Get-WinEvent -FilterHashtable @{ LogName = 'Microsoft-Windows-Windows Defender/Operational'; Id = 1116, 1117, 1121, 1122; StartTime = (Get-Date).AddDays(-3) } -ErrorAction SilentlyContinue |
       Select-Object TimeCreated, Id, Message | Format-List
   Get-MpThreatDetection | Select-Object InitialDetectionTime, ThreatID, ActionSuccess, Resources
   ```
2. **Inspect active Defender ASR rules & exclusions and verify binary signature/SHA-256 (read-only):**
   ```powershell
   Get-MpPreference | Select-Object AttackSurfaceReductionRules_Ids, AttackSurfaceReductionRules_Actions, AttackSurfaceReductionOnlyExclusions
   Get-FileHash -Path "C:\Path\To\LobApp.exe" -Algorithm SHA256
   Get-AuthenticodeSignature -FilePath "C:\Path\To\LobApp.exe" | Select-Object Status, SignerCertificate
   ```
3. Check **Microsoft Defender XDR (`security.microsoft.com`) -> Hunting / Incidents** for device `PC-LAB-01` (`DeviceEvents` where `ActionType startswith 'Asr'`) to identify the exact parent process and triggering rule ID.

## Deep-Dive Investigation (L3)
1. **Why Office Macros Are Blocked (`Mark of the Web`):** Microsoft Office blocks VBA macros in files downloaded from the internet or opened from network shares not listed in **Trusted Sites** / **Trusted Locations** (even when ASR is not blocking!).
2. **Scoped ASR Exclusion vs. Disabling a Whole Rule:** Never disable an Attack Surface Reduction rule globally just for one signed LOB binary; Intune/Defender supports **ASR-only per-path or certificate-scoped exclusions** (`AttackSurfaceReductionOnlyExclusions`).
3. **False Positive Quarantine (`1116` / `1117`):** Submit suspect clean binaries to Microsoft Security Intelligence (`https://www.microsoft.com/en-us/wdsi/filesubmission`) or create an **Indicator (Allow by SHA-256)** in Defender XDR rather than adding broad `C:\` folder exclusions.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **Microsoft Defender Antivirus** quarantined a verified clean, signed LOB executable, restore it safely on `PC-LAB-01` and add a **SHA-256 file indicator** in **Defender XDR -> Settings -> Endpoints -> Indicators -> File hashes** (preferred over local wildcard folder exclusions!).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If an **Intune ASR policy** blocked a legitimate LOB script/executable (`Event ID 1121`), add the exact signed file path to **Attack Surface Reduction Only Exclusions** inside the **Intune Endpoint Security -> Attack Surface Reduction** policy (or test locally only with security approval):
   ```powershell
   # Prefer managing exclusions centrally via Intune Endpoint Security policy
   Add-MpPreference -AttackSurfaceReductionOnlyExclusions "C:\Program Files\VendorApp\LobApp.exe"
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For legitimate internal Office macro workbooks blocked by **Mark of the Web**, place them in a secured, IT-approved **Trusted Location** (or sign macros with an internal code-signing certificate) rather than enabling all macros globally.

## Verification & Post-Fix Checks
1. Have `jsmith@example.com` launch the verified LOB application/macro on `PC-LAB-01` and confirm it executes without Defender prompts.
2. Confirm no new `Event ID 1121` or `1116` blocks appear in `Microsoft-Windows-Windows Defender/Operational` and all ASR rules remain `Enabled`.

## Cross-Subject Escalation & Pivot Links
- **Microsoft Defender ASR rule silently blocks Excel macro or Office COM add-in child process:** [app-002 — Excel/Word Freezing on Open, COM Add-in Conflict, and PDF Previewer Failure](../09_Apps_LOB/app-002-office-addins-crash-and-pdf-preview-failure.md)
- **Real-time antivirus/EDR scanning causes 100% disk and CPU contention on LOB apps:** [win-006 — Windows High CPU, 100% Disk Usage, and Memory Leak Triage (Event 129 / 153 / 2004)](../03_Windows_Endpoints/win-006-windows-high-cpu-100-disk-and-memory-leak.md)
- **If triggered payload wasn't an approved tool, escalate immediately to active BEC/malware triage:** [sec-001 — Suspected Business Email Compromise and Session Token Theft](./sec-001-bec-token-compromise.md)

## Useful Links & External Tools
- **[VirusTotal](https://www.virustotal.com/)** — Look up the executable's `Get-FileHash -Algorithm SHA256` **hash only** across AV engines before approving any exception (**never upload proprietary client files**).
- **[Microsoft Security Intelligence File Submission](https://www.microsoft.com/en-us/wdsi/filesubmission)** — Submit verified clean, digitally signed LOB binaries falsely quarantined by Defender Antivirus.
- **[Microsoft Intune Admin Center](https://intune.microsoft.com/)** — Manage scoped Attack Surface Reduction exclusions centrally under **Endpoint security**.

## Client Update Snippets (EN / FR)
- **EN:** We verified the digital signature and hash of the blocked business application on `PC-LAB-01` and added a tightly scoped Defender security exception. Please try launching the application again and confirm it opens normally.
- **FR:** Nous avons vérifié la signature numérique et l'empreinte du logiciel bloqué sur `PC-LAB-01` et ajouté une exception Defender ciblée et sécurisée. Pouvez-vous relancer l'application et confirmer qu'elle s'ouvre normalement ?
