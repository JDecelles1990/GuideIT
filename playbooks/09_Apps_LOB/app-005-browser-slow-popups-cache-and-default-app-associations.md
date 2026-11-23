---
id: app-005
domain: 09_Apps_LOB
subject: "Applications & LOB"
subcategory: browsers_sso_dev_tools
title: Web Browser Slow, Popups/Adware Extensions, Clear Cache, and Default PDF/Mail Handler Reset
tier: L1
keywords_en:
  - browser slow chrome edge
  - unwanted popups fake notifications browser
  - how to clear browser cache cookies
  - pdf opens in edge instead of adobe
  - change default browser mailto outlook
keywords_fr:
  - navigateur chrome edge tres lent
  - fenetres popups publicites navigateur
  - vider cache cookies navigateur
  - pdf s'ouvre dans edge au lieu d'adobe
  - changer application par defaut courriel pdf
error_codes:
  - BROWSER_ADWARE_POPUP
  - DEFAULT_PDF_RESET
tags:
  - browser_slow_popups
  - default_app_handler
os:
  - windows
  - macos
environment:
  - local_endpoint
tools:
  - Google Chrome / Microsoft Edge
  - Windows Default Apps Settings
  - PowerShell
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - app-001
  - app-003
  - sec-002
linked_scripts:
  - 05_Security_Defender/Get-PersistenceAndConnectionsAudit.ps1
  - 03_M365/Clear-BrowserCache.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you seeing **fake "McAfee / Virus / System Update" corner popups** in the bottom-right (`BROWSER_ADWARE_POPUP`), **broken website loading/formatting** (needs cache clear), or **50 open tabs / slow Edge & Chrome**?
2. Or is Windows opening **PDF files in Microsoft Edge instead of Adobe Acrobat (`DEFAULT_PDF_RESET`)**, or clicking `mailto:` email links opening New Mail instead of Outlook?
3. Did you recently **install a free Chrome/Edge extension** (PDF converter, coupon finder, weather toolbar) or click **"Allow notifications"** on an unfamiliar website?

### Initial Scope & Classification
- Distinguish **Malicious Browser Push Notifications (`Allow` notifications spam — NOT a real virus!)**, **Bloat/Adware Extensions**, **Stale Site Cookies/Cache** (`Clear-BrowserCache`), and **Windows Default App File Associations** (`.pdf` / `mailto:`). If real Defender threat detections exist, escalate to `[sec-002]`.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Fake Virus Popups in Bottom-Right Corner? Check Website Notification Permissions FIRST! (Solves ~80% of "I have a virus" tickets cleanly!):**
   - **Edge:** Paste `edge://settings/content/notifications` -> check **Allow** list at bottom -> any suspicious random domain is just sending fake browser toast notifications!
   - **Chrome:** Paste `chrome://settings/content/notifications` -> check **Allowed to send notifications** list!
2. **Audit Browser Extensions & Task Manager (`Shift + Esc` inside Chrome/Edge!):**
   - Open `edge://extensions` or `chrome://extensions` and ask `jsmith@example.com` about any unfamiliar toolbar/search hijacker.
   - Press **`Shift + Esc`** inside Edge/Chrome to see which exact tab or extension is hogging RAM/CPU!
3. **Verify Windows Default PDF / Browser / Mail Associations:** Open **Windows Settings -> Apps -> Default apps** -> search **`.pdf`** (`Adobe Acrobat` vs `Edge`), **`MAILTO`** (`Outlook`), and **`.htm/.html`**.

### L2 Technical Diagnostics
1. **Verify Installed Browser Versions, Policies, and Defender Health (`PC-LAB-01`, read-only):**
   ```powershell
   # Check Edge / Chrome installed versions & Windows Defender clean state
   Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
       Where-Object { $_.DisplayName -match "Chrome|Edge|Firefox" } |
       Select-Object DisplayName, DisplayVersion
   Get-MpThreatDetection -ErrorAction SilentlyContinue | Select-Object -First 5 InitialDetectionTime, ThreatID, ActionSuccess
   ```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Screenshot of popup URL or extension name, whether notifications list was cleaned, and whether Microsoft Defender reported real detections (`[sec-002]`).

## Deep-Dive Investigation (L3)
1. **Default `.pdf` / Browser Managed by GPO / Intune (`DEFAULT_PDF_RESET`):** If Edge keeps stealing `.pdf` back on every login despite changing Windows Settings, inspect GPO/Intune `DefaultAssociationsConfiguration` XML or browser enterprise policies (`edge://policy` / `chrome://policy`) for forced hijack/sync settings.
2. **Hijacked Browser Shortcut / Scheduled Task Persistence:** If adware extensions return after removal, inspect desktop shortcut target arguments, Chrome/Edge `ExtensionInstallForcelist` registry keys, and scheduled tasks.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** Warn the user before clearing **Cookies/Passwords** vs **Cached images and files** — clearing **Cached images** fixes layout/login glitches with zero annoyance, whereas clearing **All Cookies** signs them out of websites! Always preserve bookmarks!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Remove Fake Notification Spam & Suspect Extensions)**
   - In `edge://settings/content/notifications` or `chrome://settings/content/notifications`, **Remove/Block** all unknown notification sites.
   - In `edge://extensions` / `chrome://extensions`, **Remove** unauthorized adware extensions, check **Search engine** (`Google`/`Bing`), and run a quick **Defender Scan** (`[sec-002]`) for peace of mind.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Safe Cache Clear — or run `psstore://03_M365/Clear-BrowserCache.ps1`)** Close the browser completely, clear **Cached images and files** (keep Passwords & Bookmarks intact — only clear Cookies for the specific broken site via the URL lock icon unless full SSO reset is needed `[app-001]`).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Set Default PDF / Mailto App)** Open **Settings -> Apps -> Default apps**:
   - Search **`.pdf`** -> choose **Adobe Acrobat** (or preferred viewer) -> click **Set default** (or Right-click any `.pdf` -> **Open with -> Choose another app -> Always**).
   - Search **`MAILTO`** -> select **Outlook** (`Classic` or `New` per client standard).

## Verification & Post-Fix Checks
1. Restart Edge/Chrome, verify zero fake notification popups appear, and load a test portal cleanly.
2. Double-click a sample `.pdf` file and click a `mailto:` link to confirm the expected applications open directly.

## Cross-Subject Escalation & Pivot Links
- **Browser SSO portal loops continuously (ERR_TOO_MANY_REDIRECTS) after clearing site cookies:** [app-001 — Browser SSO Redirect Loop, Profile Conflict, and LOB App Crash Triage](./app-001-browser-sso-and-lob-crash.md)
- **Adobe Acrobat opens PDFs cleanly as default yet asks for sign-in / fails activation:** [app-003 — Adobe Acrobat and Creative Cloud Licensing Errors, Sign-In Loops, and Repair](./app-003-adobe-acrobat-creative-cloud-licensing-and-repair.md)
- **Suspicious download / adware triggered Microsoft Defender alert or ASR block:** [sec-002 — Microsoft Defender ASR Rule or Antivirus Blocking Legitimate LOB App or Macro](../06_Security_Access/sec-002-defender-asr-block-and-false-positive.md)


## Useful Links & External Tools
- **[VirusTotal](https://www.virustotal.com/)** — Check suspicious extension IDs or downloaded installer SHA-256 hashes.
- **[URLScan.io](https://urlscan.io/)** — Safely inspect suspicious popup/redirect URLs in an unlisted sandbox.
## Client Update Snippets (EN / FR)
- **EN:** We removed the unwanted browser notification permissions / extensions, refreshed the browser cache safely without erasing your bookmarks, and restored your default PDF / email handler settings on `PC-LAB-01`. Could you test opening your browser and a PDF file to confirm everything looks clean?
- **FR:** Nous avons supprimé les notifications et extensions indésirables du navigateur, vidé le cache en toute sécurité (tout en conservant vos favoris) et rétabli les applications par défaut PDF / courriel sur `PC-LAB-01`. Pouvez-vous tester votre navigateur et l'ouverture d'un PDF pour confirmer que tout est revenu à la normale ?
