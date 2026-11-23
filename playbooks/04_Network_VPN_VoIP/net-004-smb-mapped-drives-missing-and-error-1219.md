---
id: net-004
domain: 04_Network_VPN_VoIP
subject: "Network, VPN & VoIP"
subcategory: smb_vpn_tunnels
title: Windows SMB Mapped Network Drives Red X, 0x80070035, and Error 1219
tier: L2
keywords_en:
  - mapped network drive red x
  - network path was not found
  - smb error 1219
  - mapped drive disconnected vpn
  - windows cannot access share 0x80070035
keywords_fr:
  - lecteur reseau croix rouge
  - chemin reseau introuvable smb
  - erreur 1219 connexions multiples
  - lecteur mappe inaccessible vpn
  - erreur 0x80070035 partage windows
error_codes:
  - "0x80070035"
  - "0x80070043"
  - "1219"
  - "53"
tags:
  - smb_mapped_drive
  - smb_error_1219
os:
  - windows
environment:
  - network
  - on_prem_ad
  - hybrid_ad
tools:
  - PowerShell
  - net use
  - Test-NetConnection
  - Credential Manager
risk_level: low
requires_admin: false
last_verified: 2026-11-22
related_ids:
  - net-001
  - id-001
  - id-004
  - mdm-007
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are you working **remotely over VPN (`[net-006]`)** or inside the **office**? *(Remote mapped drives often show a red `X` simply because VPN wasn't connected BEFORE opening Explorer!)*
2. When clicking the drive (`S:` / `Z:`), what exact error pops up: **`The network path was not found` (`0x80070035`)**, **`Multiple connections... Error 1219`**, **`Access is denied` (`[srv-017]`)**, or a **password prompt**?
3. Can anyone else in the office open `\\SRV-FILE-01\Share` right now, or did you recently **change your Windows password**?

### Initial Scope & Classification
- Distinguish the exact Windows SMB error on `PC-LAB-01`:
  - **`0x80070035` / `Error 53` (`The network path was not found`):** DNS cannot resolve `SRV-FILE-01`, VPN isn't connected/routing to `10.0.10.25`, or firewall/ISP blocks **TCP `445`**.
  - **`0x80070043` (`The network name cannot be found`):** Server is reachable, but the share name (`\Share`) is misspelled, moved, or offline.
  - **`Error 1219` (`Multiple connections to a server...`):** Windows already holds an open SMB session to `SRV-FILE-01` under a different credential/mapped drive!
- **L1 Shortcut Check:** Does `\\10.0.10.25\Share` open when `\\SRV-FILE-01\Share` fails? *(If IP works and hostname fails -> DNS suffix / VPN DNS issue `[net-001]`!)*

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
1. **Verify Active VPN & Test Full Path (`Win + R`):** Confirm VPN is **Connected** (`[net-006]`), press `Win + R` -> type `\\SRV-FILE-01.domain.local\Share` (using the full FQDN instead of bare server name!).
2. **Check Credential Manager (`control /name Microsoft.CredentialManager`):** Look under **Windows Credentials** for old saved passwords under `SRV-FILE-01` or `10.0.10.25` (stale saved creds often cause `Error 1219` or account lockouts `[id-001]`!).
3. **Try Lock/Unlock or Sign Out (`gpupdate`):** If the drive usually maps automatically at login over LAN, connecting VPN and signing out/in or browsing by UNC refreshes it.

### L2 Technical Diagnostics
1. **Inspect Existing Mapped Drives, SMB Connections, and Cached Credentials (read-only):**
   ```cmd
   net use
   cmdkey /list | findstr /i "SRV-FILE"
   ```
   ```powershell
   Get-SmbConnection -ErrorAction SilentlyContinue | Select-Object ServerName, ShareName, UserName, Dialect, NumOpens
   ```
2. **Test DNS Resolution and SMB TCP `445` Reachability to `SRV-FILE-01` (read-only):**
   ```powershell
   Resolve-DnsName "SRV-FILE-01.domain.local" -ErrorAction SilentlyContinue
   Test-NetConnection -ComputerName "SRV-FILE-01.domain.local" -Port 445 | Select-Object ComputerName, RemoteAddress, TcpTestSucceeded
   ```
3. **Check GPO Drive Mapping vs. Intune Script Timing:** Verify `gpresult /r` (`[id-004]`) if drives map via AD Group Policy Preferences (GPP `Update` vs `Replace` — `Replace` deletes and recreates drives on background refresh, briefly flashing red X!).

## Deep-Dive Investigation (L3)
1. **Windows 11 `24H2` SMB Signing & Insecure Guest Auth Hardening (`0x80070035` / `System error 1219` / `Logon failure`):** Windows 11 24H2 requires **SMB Signing** by default and blocks **insecure guest logons** to third-party NAS appliances (Synology/QNAP) unless NAS enables SMB3 signing + authenticated user accounts!
2. **Kerberos vs. NTLM (`IP` UNC uses NTLM; FQDN uses Kerberos):** Cloud-only Entra ID joined endpoints connecting to an on-prem AD server need **Cloud Kerberos Trust** or cached domain/Entra credentials (`cmdkey`), and must reference the FQDN `\\SRV-FILE-01.domain.local\Share`.
3. **SMB Multichannel / Firewall Asymmetric Drop:** Check `Get-SmbClientConfiguration` and `Microsoft-Windows-SmbClient/Connectivity` operational logs for `STATUS_ACCESS_DENIED` vs `STATUS_BAD_NETWORK_NAME`.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Resolve `Error 1219` (Conflicting SMB Session):** Disconnect existing stale SMB sessions to `SRV-FILE-01` (verify no unsaved files are open on mapped drives first!), then reconnect cleanly with a single credential:
   ```cmd
   net use \\SRV-FILE-01 /delete /y
   net use * /delete /y
   ```
   *(If a Windows service holds an open handle to `SRV-FILE-01`, remove stale `cmdkey /delete:<Target>` entries and sign out/in.)*
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Re-map Drive Using Persistent FQDN Path (`net use`):**
   ```cmd
   net use S: \\SRV-FILE-01.domain.local\Share /persistent:yes
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If connecting to a **legacy NAS blocking guest access on Windows 11 24H2**, configure authenticated user credentials on the NAS and enable **SMB3 + SMB Signing** on the NAS itself (never disable SMB signing globally unless strictly isolated and approved!).

## Verification & Post-Fix Checks
1. Run `net use` and confirm `S:` shows **`OK`** (no `Disconnected` / `Unavailable`), and `Get-SmbConnection` reports active SMB `3.x` dialect.
2. Have `jsmith@example.com` open a folder and save/delete a test document on `S:\` per share permissions.

## Cross-Subject Escalation & Pivot Links
- **UNC hostname resolution or firewall port 445 fails across split-tunnel VPN (0x80070035):** [net-001 — No Internet, APIPA 169.254.x.x, DNS, and VPN Split-Tunnel Triage](./net-001-dns-apipa-vpn-triage.md)
- **Cached conflicting SMB credentials (Error 1219) trigger AD account lockout (4740):** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)
- **GPO drive maps fail after logon (Event 1129) until AD Group Policy timing resolves:** [id-004 — Active Directory GPO Not Applying, SYSVOL Permissions, and DFSR Replication Errors](../01_Identity_AD_Entra/id-004-ad-gpo-not-applying-replication-and-dfsr.md)
- **Shared drive issue occurs in macOS Finder (smb://server/share) rather than Windows:** [mdm-007 — Beginner macOS Finder SMB Network Share, DNS Flush, and Office Mac Licensing](../07_macOS_Mobile_MDM/mdm-007-macos-finder-smb-share-and-office-licensing.md)

## Client Update Snippets (EN / FR)
- **EN:** We cleared the conflicting SMB session / network path issue on `PC-LAB-01` and reconnected your mapped network drive (`S:`) using the verified server FQDN. Could you open the drive in File Explorer and confirm your folders load normally?
- **FR:** Nous avons nettoyé la session SMB en conflit sur `PC-LAB-01` et reconnecté votre lecteur réseau (`S:`) avec le nom complet du serveur. Pouvez-vous ouvrir le lecteur dans l'Explorateur de fichiers et confirmer que vos dossiers sont accessibles ?
