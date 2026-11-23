---
id: srv-004
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: linux_os_networking
title: Linux systemd Service Crash, Exit Codes, and journalctl Diagnostics
tier: L2
keywords_en:
  - systemd failed journalctl
  - linux service won't start
  - systemctl failed unit
  - exit code 203 exec
  - linux daemon crashing
keywords_fr:
  - service linux en echec
  - erreur systemd journalctl
  - demon linux ne demarre pas
  - erreur systemctl failed
  - code sortie systemd 203
error_codes:
  - "203/EXEC"
  - "127"
  - "137"
  - "139"
tags:
  - linux_systemd_failed
  - linux_journalctl
os:
  - linux
environment:
  - datacenter
  - cloud_infra
  - local_endpoint
tools:
  - systemctl
  - journalctl
  - ss
  - ausearch
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-005
  - srv-006
  - srv-007
  - srv-015
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is **one specific web app / database / daemon (`nginx`, `postgresql`, `docker`) down**, OR is the entire Linux host offline/unresponsive (`[srv-005]`)?
2. Roughly **when** did the service stop responding, and did someone run `apt/dnf` updates, edit a config file, or run out of disk space (`[srv-006]`) right before?
3. Did a monitoring alert show a specific service name (`<service_name>.service`)?

### Initial Scope & Classification
- Check disk space (`df -h`), failed units (`systemctl --failed`), and exit codes (`203/EXEC`, `137` OOM, `139` SIGSEGV) cleanly before restarting anything blindly.

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Safe Status & Disk Glance)
1. **Check RMM / Console & Basic Health First (`No Config Edits!`):** Run **`systemctl --failed`**, **`systemctl status <service_name> --no-pager`**, and **`df -h`** (a 100% full `/var` disk stops Linux services instantly -> `[srv-006]`!) and capture the last ~20 log lines shown in `systemctl status`!
2. **Verify Recent File Edits / Restarts:** Ask the team whether anyone modified `/etc/...` config or deployed code within the last hour.

### L2 Technical Diagnostics
1. **Inspect failed units, unit status, and full journal logs (read-only):**
   ```bash
   systemctl --failed
   systemctl status <service_name> --no-pager -l
   journalctl -xeu <service_name> -n 100 --no-pager
   ```
2. **Decode Common `systemd` Exit Status Codes:**
   - **`203/EXEC`:** Binary path missing, missing executable permission (`chmod +x`), bad `#!` shebang, or `noexec` mount / SELinux blocking execution.
   - **`1` / `2`:** Configuration file syntax error or bad CLI flag (check service native config test like `nginx -t`, `sshd -t`, `apachectl configtest`).
   - **`127`:** Command/shared library not found.
   - **`137` (`SIGKILL`):** Often killed by Linux **OOM Killer** (`[srv-005]`) or `TimeoutStopSec` kill.
   - **`139` (`SIGSEGV`):** Segmentation fault (corrupted library/binary or hardware/RAM issue).
3. **Check unit file location, overrides, listening port conflicts, and SELinux denials (read-only):**
   ```bash
   systemctl cat <service_name> --no-pager
   systemd-analyze verify /etc/systemd/system/<service_name>.service 2>&1 || true
   ss -tulpn
   sudo ausearch -m avc -ts recent 2>/dev/null || true
   ```

## Deep-Dive Investigation (L3)
1. **Environment / Drop-in Override Conflict:** Check `/etc/systemd/system/<service>.service.d/*.conf` and `EnvironmentFile=` paths; missing `EnvironmentFile` (without leading `-`) aborts startup immediately.
2. **SELinux / AppArmor Denial:** On RHEL/Rocky/AlmaLinux, `203/EXEC` or `Permission denied` despite `0755` permissions usually points to wrong SELinux file context (`ls -Z /path/to/binary`) or custom port labeling (`semanage port -l`). On Ubuntu/Debian, check `aa-status` and `/var/log/syslog` for AppArmor `DENIED`.
3. **Resource Limits (`LimitNOFILE` / `MemoryMax`):** Inspect `systemctl show <service_name> -p MemoryCurrent,TasksCurrent,LimitNOFILE` for descriptor or cgroup exhaustion.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Validate service configuration syntax first (e.g., `nginx -t` / `sshd -t`), fix broken paths/permissions/port bindings, and reload `systemd` if unit files were modified:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart <service_name>
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If SELinux labeled a relocated binary or web root incorrectly on RHEL/Rocky (avoid `setenforce 0` in production!), restore proper contexts:
   ```bash
   sudo restorecon -Rv /path/to/service/dir
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Reset failed state counter if unit hit `start-limit-hit`:
   ```bash
   sudo systemctl reset-failed <service_name>
   sudo systemctl start <service_name>
   ```

## Verification & Post-Fix Checks
1. Confirm `systemctl is-active <service_name>` returns `active` and `systemctl --failed` shows `0 loaded units listed`.
2. Verify expected listening socket in `ss -tulpn` and check `journalctl -u <service_name> --since "2 minutes ago"` is error-free.

## Cross-Subject Escalation & Pivot Links
- **Systemd service dies silently (SIGKILL) due to Linux OOM Killer or I/O starvation:** [srv-005 — Linux High CPU, Memory Pressure, OOM Killer, and I/O Wait Triage](./srv-005-linux-high-cpu-oom-killer-and-io-wait.md)
- **Unit fails on start (ENOSPC) because /var/log or root disk/inodes reached 100%:** [srv-006 — Linux Disk Full (ENOSPC), Inode Exhaustion, Deleted Open Files, and Read-Only FS](./srv-006-linux-disk-full-inodes-lsof-and-readonly-fs.md)
- **Service fails binding interface/port or resolving DNS due to NIC or nftables rules:** [srv-007 — Linux Network Interfaces, LACP Bonding, DNS, and Firewall (nftables/ufw/firewalld)](./srv-007-linux-network-nic-bonding-and-firewall.md)
- **Failing systemd unit is docker.service or a containerized workload in CrashLoopBackOff:** [srv-015 — Docker Container CrashLoopBackOff, Port Conflicts (EADDRINUSE) & Overlay2 Disk Full](./srv-015-docker-container-crashloop-and-overlay-disk.md)

## Client Update Snippets (EN / FR)
- **EN:** We investigated the failed Linux systemd service via `journalctl`, resolved the underlying configuration / permission error, and confirmed the service is active and healthy.
- **FR:** Nous avons analysé l'échec du service systemd Linux via `journalctl`, corrigé l'erreur de configuration / permission et confirmé que le service est de nouveau actif et stable.
