---
id: mdm-007
domain: 07_macOS_Mobile_MDM
subject: "macOS, Mobile & MDM"
subcategory: macos_basics_apps_shares
title: Beginner macOS Finder SMB Network Share, DNS Flush, and Office Mac Licensing
tier: L1
keywords_en:
  - mac connect network drive smb
  - finder connect to server smb
  - mac office no license found
  - flush dns macos
  - mac cannot open shared folder
keywords_fr:
  - mac connecter lecteur reseau smb
  - finder se connecter au serveur mac
  - office mac aucune licence trouvee
  - vider cache dns mac
  - mac partage fichier windows impossible
error_codes:
  - SMB_MOUNT_FAIL
  - OFFICE_ACTIVATE_MAC
tags:
  - macos_smb_network
  - macos_office_license
os:
  - macos
environment:
  - local_endpoint
  - m365
  - network
tools:
  - Finder
  - Terminal
  - Microsoft Office for Mac
  - Keychain Access
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - net-004
  - net-001
  - mdm-002
  - app-003
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you trying to **connect to a shared company folder (`SMB_MOUNT_FAIL`)**, OR is **Word / Excel / Outlook on Mac saying `"No License Found" / "View Only"` (`OFFICE_ACTIVATE_MAC`)**?
2. For **Shared Folders on Mac**, did the user type Windows backslashes (`\\server\share`) instead of Mac format **`smb://SRV-FILE-01.domain.local/Share`**, and is **corporate VPN** connected if remote (`[net-001]`)?
3. For **Office Licensing on Mac**: verify the user's **Microsoft 365 license includes Desktop Apps** (*Business Standard / Premium / E3*, NOT *Business Basic* Web-only!).

### Initial Scope & Classification
- Macs use **Finder (`⌘ + K` -> `smb://server/share`)** instead of drive letters `S:\`.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Finder GUI & M365 License Check)
1. **Check Active VPN & Finder Quick Connect (`⌘ + K` GUI):**
   - If working from home, connect **VPN** (`[net-001]`) FIRST!
   - In **Finder** (blue smiley Dock icon), press **`⌘ + K`** (`Go -> Connect to Server...`), verify path starts with **`smb://`**, and test both hostname (`smb://SRV-FILE-01.domain.local/Share`) AND IP (`smb://10.0.10.25/Share`) to separate DNS vs SMB issues!
2. **Verify User License & Profile in Office Mac & M365 Admin Center:** Open **Word -> File -> Open / Word menu -> About Microsoft Word** -> check active `Belongs to:` email + check [Microsoft 365 Admin Center](https://admin.microsoft.com/) -> **Licenses**!

### L2 Technical Diagnostics
1. **Test DNS Resolution & TCP Port `445` (SMB) from Mac Terminal (`⌘ + Space` -> `Terminal`, read-only):**
   ```bash
   scutil --dns | head -n 30
   dscacheutil -q host -a name SRV-FILE-01.domain.local
   nc -vz -G 3 10.0.10.25 445
   mount | grep smbfs || true
   ```
   *(If `nc -vz ... 445` fails, VPN split-tunnel or firewall is blocking SMB — see `[net-001]` / `[net-004]`!)*
2. **Inspect Installed Office Mac License Files (read-only):**
   ```bash
   ls -la "/Library/Preferences/com.microsoft.office.licensingV2.plist" 2>/dev/null || echo "No volume/local licensingV2 plist"
   ```
   Confirm `jsmith@example.com` holds an M365 desktop app license (Business Standard / Business Premium / E3 / E5 — **M365 Business Basic** is Web/Mobile only!).

## Deep-Dive Investigation (L3)
1. **macOS SMB Signing / `DS_Store` Slowdown:** Large Windows shares feel sluggish in Finder until macOS disables creating `.DS_Store` over network shares (`com.apple.desktopservices DSDontWriteNetworkStores`) or uses SMB v3 (`smbutil statshares -a` to verify SMB dialect).
2. **Corrupted Office for Mac License Cache:** Upgrading from Office 2019/2021 perpetual to Microsoft 365 subscription (or changing UPN/tenant) leaves cached license tokens inside Keychain and `~/Library/Group Containers/UBF8T346G9.Office` that prevent activation.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Mount a Windows Network Share in Finder (Beginner GUI Steps):**
   - Click the desktop or open **Finder** (blue smiley icon in Dock).
   - Press **`⌘ + K`** (or top menu bar **`Go -> Connect to Server...`**).
   - Type **`smb://SRV-FILE-01.domain.local/Share`** (click **`+`** to save as a Favorite!) -> click **`Connect`**.
   - Select **Registered User**, enter `DOMAIN\jsmith` (or `jsmith@example.com`) and password, optionally check **"Remember this password in my keychain"**, and click **Connect**.
   - *(Tip: To make it easy to find, turn on **Finder -> Settings (`⌘ + ,`) -> General -> Connected servers** so it appears on the Desktop, or drag the mounted folder into the Dock's right-hand folder area!)*
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Flush macOS DNS Cache** (requires local admin password):
   ```bash
   sudo dscacheutil -flushcache && sudo killall -HUP mDNSResponder
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Fix Office for Mac `"No License Found"` (`OFFICE_ACTIVATE_MAC`):**
   - Quit all Office apps (`⌘ + Q` on Word, Excel, PowerPoint, Outlook).
   - Run Microsoft's official **Office License Removal Tool** (`Microsoft_Office_License_Removal.pkg`), OR sign out from **Word -> Sign Out**, remove stale `Microsoft` / `ADAL` entries in Keychain (`[mdm-002]`), relaunch Word, and sign back in with `jsmith@example.com`.

## Verification & Post-Fix Checks
1. Confirm the SMB network share mounts under Finder **Locations** and `jsmith@example.com` can read/create a test file per permissions.
2. Open **Word -> Word menu -> About Microsoft Word** and confirm **`License: Microsoft 365 Subscription`** assigned to `jsmith@example.com`.

## Cross-Subject Escalation & Pivot Links
- **Cross-platform SMB permissions, port 445 firewall, or Windows DFS namespace troubleshooting:** [net-004 — Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219](../04_Network_VPN_VoIP/net-004-smb-mapped-drives-missing-and-error-1219.md)
- **Mac fails resolving internal .domain.local names over corporate VPN split-tunnel DNS:** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](../04_Network_VPN_VoIP/net-001-dns-apipa-vpn-triage.md)
- **macOS Login Keychain stores stale SMB password blocking reconnect:** [mdm-002 — macOS Login Keychain Password Loop and Platform SSO / FileVault Desync](./mdm-002-macos-keychain-loop-and-platform-sso.md)
- **Creative Cloud sign-in/licensing repair alongside Microsoft Office Mac serializer cleanup:** [app-003 — Adobe Acrobat and Creative Cloud Licensing Errors, Sign-In Loops, and Repair](../09_Apps_LOB/app-003-adobe-acrobat-creative-cloud-licensing-and-repair.md)

## Useful Links & External Tools
- **[Microsoft My Account](https://myaccount.microsoft.com/)** — Verify the user's active Office for Mac license assignment.
- **[Microsoft 365 Admin Center](https://admin.microsoft.com/)** — Confirm M365 Apps for Mac license is assigned to the user.

## Client Update Snippets (EN / FR)
- **EN:** We mapped the shared network folder via Finder (`⌘ + K`) / refreshed your Microsoft 365 Office license on your Mac. Could you confirm you can open files on the shared drive and edit documents in Word/Excel normally?
- **FR:** Nous avons connecté le lecteur réseau partagé via le Finder (`⌘ + K`) / réinitialisé votre licence Microsoft 365 Office sur votre Mac. Pouvez-vous confirmer que vous accédez aux fichiers partagés et modifiez vos documents Word/Excel normalement ?
