---
id: srv-005
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: linux_os_networking
title: Linux High CPU, Memory Pressure, OOM Killer, and I/O Wait Triage
tier: L3
keywords_en:
  - linux oom killer
  - linux high cpu io wait
  - out of memory killed process
  - linux server slow load average
  - uninterruptible sleep d state
keywords_fr:
  - charge cpu elevee linux
  - saturation memoire oom linux
  - processus tue manque memoire linux
  - serveur linux tres lent
  - attente disque iowait linux
error_codes:
  - OOM_KILLED
  - SIGKILL
  - D_STATE
tags:
  - linux_oom_killer
  - linux_high_cpu_io
os:
  - linux
environment:
  - datacenter
  - cloud_infra
tools:
  - top
  - free
  - vmstat
  - iostat
  - dmesg
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-004
  - srv-006
  - srv-009
---

## Fast Triage (Under 2 Minutes)
- Run `uptime` and `free -h`: compare **1/5/15-min Load Average** against total vCPU/core count (`nproc`), and check **Available** RAM (`available` column, NOT `free` — Linux caches aggressively!).
- Determine whether slowness is **User CPU (`%us`)**, **Disk I/O Wait (`%wa` + `D_STATE` processes)**, **Steal Time (`%st` > 5% on noisy cloud/hypervisor hosts)**, or **Memory/OOM thrashing (`OOM_KILLED`)**.

## Read-Only Diagnostics (L1-L2)
1. **Capture CPU, Memory, Swap, and Top Consumers (read-only):**
   ```bash
   nproc
   uptime
   free -h
   swapon --show
   ps aux --sort=-%cpu | head -n 12
   ps aux --sort=-%mem | head -n 12
   ```
2. **Check Kernel OOM Killer & Hardware Stall Logs (read-only):**
   ```bash
   sudo dmesg -T | grep -iE 'oom|killed process|out of memory|blocked for more than' | tail -n 25
   ```
3. **Separate CPU Bottleneck vs. Swap Thrashing (`si`/`so`) vs. Storage Latency (`%wa` / `await`):**
   ```bash
   vmstat 1 5
   iostat -xz 1 3 2>/dev/null || true
   ps -eo pid,ppid,stat,comm,wchan:30 | awk '$3 ~ /D/'
   ```
   *(If processes sit in **`D` (`D_STATE`)** and `iostat` `await` > 50–100 ms or `%util` ~100%, check storage/RAID/NFS health immediately -> `[srv-009]` / `[srv-006]`!)*

## Deep-Dive Investigation (L3)
1. **Per-Cgroup / Container OOM (`MemoryMax` Hit While Host Has Free RAM):** Inspect `/sys/fs/cgroup/` (`systemd-cgtop -n 1`) or `docker stats --no-stream` / `journalctl -k | grep -i memory` — a systemd unit or container can hit its cgroup `MemoryMax` even when host `free -h` looks healthy!
2. **Slab / Kernel Memory Leak vs. Page Cache:** Inspect `/proc/meminfo` (`Slab`, `SUnreclaim`, `AnonPages`, `Dirty`) and `slabtop -o` if RSS totals don't account for consumed RAM.
3. **Hypervisor CPU Steal (`%st` in `top` / `vmstat`):** On VMware/KVM/cloud VMs, sustained `st > 5–10%` means physical host CPU oversubscription or noisy neighbors requiring vMotion/host migration.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Stop or gracefully restart a confirmed runaway memory-leaking worker process (never `kill -9` a database like PostgreSQL/MySQL unless frozen and unrecoverable — prefer graceful `systemctl restart <service>` or `kill -TERM <pid>`).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Tune application memory limits (`Xmx`, worker pool count, `MemoryMax` in systemd drop-in) or add emergency swapfile / expand RAM on the hypervisor/cloud instance.
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** If **unresponsive NFS mount** (`soft` vs `hard`) causes stuck `D_STATE` processes, restore storage connectivity first (`[srv-007]` / `[srv-009]`); only use `umount -lf` as a last resort when storage is permanently gone.

## Verification & Post-Fix Checks
1. Confirm `uptime` load average trends down below `nproc`, `vmstat` `si/so` = `0`, and `%wa` < `5%`.
2. Confirm `dmesg -T` logs no new `Out of memory` events and target application services respond within SLA.

## Cross-Subject Escalation & Pivot Links
- **OOM-killed process triggers cascading systemd service restarts:** [srv-004 — Linux systemd Service Crash, Exit Codes, and journalctl Diagnostics](./srv-004-linux-systemd-service-crash-and-journalctl.md)
- **Extreme iowait coincides with filesystem errors, full disk, or read-only remount:** [srv-006 — Linux Disk Full (ENOSPC), Inode Exhaustion, Deleted Open Files, and Read-Only FS](./srv-006-linux-disk-full-inodes-lsof-and-readonly-fs.md)
- **Sustained hardware iowait traces back to degraded RAID or failed PERC/HBA battery cache:** [srv-009 — Data Center IPMI/iDRAC/iLO, RAID Degraded, SMART Disk, and ECC/MCE Hardware Triage](./srv-009-datacenter-ipmi-raid-smart-and-ecc-hardware.md)

## Client Update Snippets (EN / FR)
- **EN:** We isolated the root cause of the Linux server resource bottleneck (CPU / memory OOM / disk I/O wait), stabilized the affected workload, and confirmed normal load and memory availability.
- **FR:** Nous avons identifié l'origine de la saturation sur le serveur Linux (CPU / OOM mémoire / attente disque I/O), stabilisé le service concerné et confirmé le retour à des métriques normales.
