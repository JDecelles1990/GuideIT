---
id: srv-016
domain: 08_Servers_Cloud_Infra
subject: Servers, Cloud & Infrastructure
subcategory: windows_server_sql
title: SQL Server Login Failed (18456), Transaction Log Full (9002) & Deadlocks
tier: L3
keywords_en:
  - sql server login failed 18456
  - sql transaction log is full 9002
  - sql database deadlock 1205
  - cannot connect sql server 1433
  - sql server blocking session
  - log reuse wait
keywords_fr:
  - echec connexion sql server 18456
  - journal transaction sql plein 9002
  - blocage deadlock base de donnees sql
  - erreur connexion sql port 1433
  - requete bloquee sql server
error_codes:
  - "18456"
  - "9002"
  - "1205"
tags:
  - sql_login_failed
  - sql_transaction_log_full
os:
  - windows
  - linux
environment:
  - on_prem_ad
  - cloud_infra
  - datacenter
tools:
  - SQL Server Management Studio (SSMS)
  - PowerShell (SqlServer / dbatools)
  - Windows Event Viewer
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-001
  - app-002
  - id-005
  - id-001
linked_scripts:
  - 07_Servers_Infra/Get-ServerAutoServices.ps1
  - 07_Servers_Infra/Get-FirewallAndListeningPorts.ps1
  - 01_System/Get-DiskSpaceReport.ps1
  - 02_Network/Get-ListeningPorts.ps1
  - 05_Security_Defender/Get-FirewallStatus.ps1
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Are **ALL users / services** failing to connect to the SQL database application (service stopped or disk/log full), or is **only one user (`jsmith@example.com`)** getting `Login failed` (`18456`)?
2. What is the **exact error message** (`Login failed for user`, `Cannot connect to SQL Server / network-related error`, `Transaction log for database is full (9002)`, or `Deadlock / Freezing`)?
3. Did anything change right before this started (SQL service account password change, Windows password reset, backup failure, server reboot, or Windows Updates)?
4. Can you still access other applications or shared folders on `<sql-host>` (checking if the whole server is down)?

### Initial Scope & Classification
- **Classify exact SQL error code:**
  - **`18456` (Login failed):** Always check **Event Viewer (`Application`) ON THE SQL SERVER HOST** or the server-side SQL **`ERRORLOG`** for the real **`State`** number! SQL deliberately hides the true State (showing generic **`State 1`**) to client apps to prevent password enumeration.
  - **`9002` (Transaction log for database is full):** Writes/inserts/deletes freeze (`LOG_BACKUP`, full disk volume, max log autogrowth cap, or runaway uncommitted transaction).
  - **`1205` (Transaction victim of deadlock) / Slow app:** Long-running uncommitted transaction blocking all other ERP/LOB sessions.
- **Verify backup jobs BEFORE touching Transaction Logs:** Ask whether Veeam / SQL Agent Transaction Log backups failed recently (`9002` is frequently caused by a broken log backup schedule on a `FULL` recovery database).

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Basic / GUI)
> Even when an SQL Server issue is escalated to L2/L3, L1 technicians can solve stopped-service / credential / disk-full causes fast — and gather exact `18456` Event Viewer evidence cleanly!

1. **Check SQL Server Services on the SQL Server Host (`services.msc` GUI):**
   - Connect to `<sql-host>` via RMM/RDP and open **`services.msc`**.
   - Check **`SQL Server (MSSQLSERVER)`** (or named instance **`SQL Server (SQLEXPRESS)` / `MSSQL$<Instance>`**), **`SQL Server Browser`** (needed so clients find named instances over UDP `1434`!), and **`SQL Server Agent`**: are they **Running**, **Stopped**, or **Paused**? (A stopped SQL Server or SQL Browser service stops ALL ERP logins!)
2. **Where to Check Error `18456` in Windows Event Viewer (IMPORTANT — Server Side Only!):**
   - **Yes — SQL Server Error `18456` IS logged in Windows Event Viewer**, **ON THE SQL SERVER ITSELF** (never on the user's workstation!).
   - Open **Event Viewer (`eventvwr.msc`) on `<sql-host>` -> `Windows Logs` -> `Application`** -> right-click **Filter Current Log...**:
     - **Event sources:** `MSSQLSERVER` (for default instance) or `MSSQL$<InstanceName>` (for named instance).
     - **Event IDs:** `18456, 9002, 17052`
   - Open the matching **`18456`** event: unlike the user's PC screen (which always says generic `State: 1`), **Event Viewer AND SQL `ERRORLOG`** (`C:\Program Files\Microsoft SQL Server\MSSQL*.<Instance>\MSSQL\Log\ERRORLOG`, or SSMS -> **Management -> SQL Server Logs**) display the **real `State`** number (e.g., `State: 8`) and plain-English **`Reason:`** (e.g., `Reason: Password did not match...`, `Reason: Could not find a login...`, `Reason: Server is configured for Integrated authentication only`)!
   - **What if Event Viewer has ZERO `18456` entries when users fail to connect?** That proves client packets **never reached the SQL authentication engine** (SQL Server service is stopped, firewall/port `1433` or `SQLBrowser` UDP `1434` is blocked, wrong instance name in client config, OR SQL **Login Auditing** is set to `None` / `Successful only` under SSMS -> Server Properties -> Security -> Login auditing)!
3. **Check Disk Space & AD Account Lockout:** Open File Explorer (`This PC`) on `<sql-host>` to ensure `.mdf`/`.ldf` volumes aren't at `0 MB` free (`[srv-001]`), and if the app uses **Windows Authentication**, check AD (`[id-001]`) to verify `jsmith@example.com` isn't locked or expired.

### L2 Technical Diagnostics
Verify SQL Server service status, TCP port `1433` connectivity, and Windows Application Event Log `18456` **State** numbers cleanly:

```powershell
# 1. Check SQL Server & Agent services plus TCP 1433 listener
Get-Service MSSQL*, SQLSERVERAGENT*, SQLBrowser* | Select-Object Name, DisplayName, Status, StartType | Format-Table -AutoSize
Test-NetConnection -ComputerName "sql01.domain.local" -Port 1433

# 2. Read Windows Application Event Log on <sql-host> for 18456 (real State code & Reason) and 9002 without modifying DB
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=18456,9002,17052} -MaxEvents 20 |
  Select-Object TimeCreated, ProviderName, Id, Message | Format-List

# 3. Also inspect the latest SQL Server ERRORLOG directly on disk (captures logins even if Event Log rotated)
Get-ChildItem "C:\Program Files\Microsoft SQL Server\MSSQL*\MSSQL\Log\ERRORLOG" -ErrorAction SilentlyContinue |
  ForEach-Object { Select-String -Path $_.FullName -Pattern "18456|Login failed|9002" | Select-Object -Last 10 }
```

Run read-only T-SQL DMVs in **SSMS** or `Invoke-Sqlcmd` to inspect database recovery models, why the transaction log won't reuse space (`log_reuse_wait_desc`), log percentages, and live blocking chains:

```sql
-- 1. Check DB state, Recovery Model, and why Transaction Log cannot truncate (Error 9002)
SELECT name, state_desc, recovery_model_desc, log_reuse_wait_desc
FROM sys.databases
ORDER BY name;

-- 2. Check current Transaction Log file usage %
DBCC SQLPERF(LOGSPACE);

-- 3. Inspect active blocking sessions without killing anything
SELECT
    r.session_id AS BlockedSPID,
    r.blocking_session_id AS BlockingSPID,
    s.login_name,
    s.host_name,
    s.program_name,
    DB_NAME(r.database_id) AS DatabaseName,
    r.wait_type,
    r.wait_time / 1000.0 AS WaitSeconds,
    t.text AS CurrentSQLText
FROM sys.dm_exec_requests r
JOIN sys.dm_exec_sessions s ON r.session_id = s.session_id
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) t
WHERE r.blocking_session_id <> 0 OR r.session_id IN (SELECT blocking_session_id FROM sys.dm_exec_requests WHERE blocking_session_id <> 0);
```

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Instance name (`MSSQLSERVER` vs `MSSQL$<Instance>`), service states from `services.msc`, free disk space on DB drives, AND the full **Application Event ID `18456` / `ERRORLOG` message** (showing `Reason:` and real `State:`).

## Deep-Dive Investigation (L3)
Interpret the exact SQL diagnostic output before making any change:

1. **Error `18456` State Reference (Read from `ERRORLOG`):**
   - **State `5`:** Invalid SQL login name (or orphaned user after DB restore — SID mismatch between `sys.server_principals` and `sys.database_principals`).
   - **State `8`:** Password mismatch for SQL Login.
   - **State `11` / `12`:** Login valid at server level, denied permission on requested database.
   - **State `38`:** Login cannot open its configured default database (offline, deleted, or missing permissions).
   - **State `58`:** SQL Server Authentication attempted while SQL instance is configured for **Windows Authentication mode only**.
2. **Error `9002` Root Causes (`log_reuse_wait_desc`):**
   - **`LOG_BACKUP`:** Database is in `FULL` recovery model, yet no Transaction Log backups are running (or last log backup job failed).
   - **`ACTIVE_TRANSACTION`:** An open uncommitted transaction (`DBCC OPENTRAN(<db>)`) prevents VLFs from recycling.
   - **`AVAILABILITY_REPLICA` / `REPLICATION`:** AlwaysOn AG secondary disconnected or replication stalled.
   - **Max Size / Full Volume:** `.ldf` reached its artificial `maxsize` cap in `sys.database_files`, or drive ran out of free space.
3. **Deadlocks (`1205`):** Inspect the built-in `system_health` Extended Events session (`Deadlock graph`) in SSMS to identify the exact two competing queries/indexes and share the XML graph with the LOB/ERP developer.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER switch a production database from `FULL` to `SIMPLE` recovery model or run `TRUNCATE_ONLY` without written approval — doing so **breaks the Transaction Log LSN chain** and invalidates point-in-time recovery! NEVER run `KILL <BlockingSPID>` blindly before identifying what ERP/payroll/ETL batch owns it, as rolling back a huge transaction can freeze the DB even longer! Restarting SQL Server disconnects all active users and rolls back open transactions — confirm impact and approval before restarting!

1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1/L2 Start Stopped SQL Service OR Approved Restart of Hung SQL Server Service):**
   - **If stopped (`services.msc`):** Start `SQL Server (MSSQLSERVER)` (or `MSSQL$<InstanceName>`), `SQL Server Agent` (so scheduled jobs & backups resume!), and `SQL Server Browser` (for named instances).
   - **If running yet hung / stuck logins / stale pool / after Mixed Mode auth toggle:** After confirming no critical un-saved batch is running and obtaining client approval to bounce the DB service cleanly (prefer `services.msc` or PowerShell):
     ```powershell
     # Run ONLY after verifying outage window / client confirmation (disconnects active users!)
     Restart-Service -Name "MSSQLSERVER" -Force   # Replace with MSSQL$<InstanceName> for named instances
     Start-Service -Name "SQLSERVERAGENT" -ErrorAction SilentlyContinue
     Start-Service -Name "SQLBrowser" -ErrorAction SilentlyContinue
     ```
     *(If restarting **SQL Server** under a changed AD service account password (`18456` service startup failure), update the logon password via **SQL Server Configuration Manager** rather than plain `services.msc` so SPNs & file ACLs stay valid!)*
2. **Resolve Error `9002` (`LOG_BACKUP`) Safely (L2/L3):**
   - Scope: Affected database `<DBName>` with verified disk space available for the backup target.
   - Prerequisite: Confirm primary backup tool (Veeam / SQL Maintenance Plan) schedule so backups do not conflict on LSN chains, or execute an approved on-demand **Transaction Log backup** to clear reusable space, then fix the failing backup job.
   - If the log drive is completely full and no log backup can run yet, temporarily add a secondary log file (`ALTER DATABASE ... ADD LOG FILE`) on another local healthy volume under L3 approval, run the log backup, then clean up cleanly.
3. **Resolve Orphaned SQL Login / `18456` State Error (L2/L3):**
   - For Mixed Mode (`State 58`), enable `SQL Server and Windows Authentication mode` in SSMS **Server Properties -> Security**, then perform an approved **Restart of `MSSQLSERVER` + `SQLSERVERAGENT`**.
   - For database-restored orphaned users (`State 5`), map existing user to server login (`ALTER USER [<user>] WITH LOGIN = [<login>]`).
   - For Windows Auth user account locked/expired (`[id-001]`), unlock AD account cleanly and test login.
4. **Resolve Critical Blocking (`BlockingSPID`) / Deadlocks (`1205`) (L3):**
   - Confirm with the app owner whether `<BlockingSPID>` is an abandoned workstation/report query vs active batch job before issuing `KILL <BlockingSPID>`. Provide `system_health` deadlock XML to app developers for index/query fixes.

## Verification & Post-Fix Checks
- Verify `DBCC SQLPERF(LOGSPACE)` shows Transaction Log usage dropped and `log_reuse_wait_desc` returns to `NOTHING`.
- Confirm scheduled Transaction Log backups succeed and alert thresholds on disk/log space remain healthy.
- Confirm the LOB application or ODBC client authenticates cleanly (zero new `18456` events) and active blocking clears.

## Cross-Subject Escalation & Pivot Links
- **NTFS drive hosting SQL .mdf/.ldf/backups ran out of free disk space (Error 9002):** [srv-001 — Windows Server Disk Space Exhaustion and VSS Shadow Copy Backup Failure](./srv-001-vss-backup-and-disk-triage.md)
- **Windows-integrated SQL login (18456) stems from an AD account lockout or expired password:** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)
- **Excel PowerQuery or LOB accounting app hangs on SQL blocking lock (1205) / 18456 auth:** [app-002 — Excel/Word Freezing on Open, COM Add-in Conflict, and PDF Previewer Failure](../09_Apps_LOB/app-002-office-addins-crash-and-pdf-preview-failure.md)
- **Windows-integrated SQL login fails across domain due to Kerberos/SPN/domain trust:** [id-005 — Windows Domain Trust Relationship Failed (Event ID 5722 / 3210 / 0xC000018B)](../01_Identity_AD_Entra/id-005-windows-domain-trust-relationship-failed.md)

## Useful Links & External Tools
- [Microsoft Learn SQL Server Troubleshooting](https://learn.microsoft.com/en-us/troubleshoot/sql/welcome-sql-server) — Official reference for SQL 18456 State codes, 9002 log full waits, and deadlock analysis.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we investigated the SQL Server `<login failure 18456 / transaction log full 9002 / blocking 1205>` incident on `<sql-host>`. After addressing `<root cause — e.g., backup log truncation / orphaned login mapping / confirmed idle blocker>`, database health and client connectivity are verified without interrupting backup integrity. Please test the application.
- **FR:** Bonjour `<user>`, nous avons diagnostiqué l'incident SQL Server (`<erreur 18456 / journal 9002 plein / blocage 1205>`) sur `<sql-host>`. Après correction (`<sauvegarde de journal / association compte / déblocage session validé>`), la base est de nouveau accessible tout en préservant la chaîne de sauvegarde. Merci de valider l'application.
