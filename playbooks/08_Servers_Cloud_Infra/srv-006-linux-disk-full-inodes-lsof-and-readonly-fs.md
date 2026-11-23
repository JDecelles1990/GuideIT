---
id: srv-006
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: linux_os_networking
title: Linux Disk Full (ENOSPC), Inode Exhaustion, Deleted Open Files, and Read-Only FS
tier: L2
keywords_en:
  - linux disk full inodes
  - linux read only file system
  - lsof deleted open files
  - no space left on device linux
  - ext4 xfs filesystem error
keywords_fr:
  - disque plein inodes linux
  - systeme de fichiers lecture seule linux
  - fichiers supprimes encore ouverts lsof
  - plus d espace disque linux
  - erreur systeme fichiers ext4
error_codes:
  - ENOSPC
  - EROFS
  - EXT4_ERROR
tags:
  - linux_disk_inodes
  - linux_readonly_fs
os:
  - linux
environment:
  - datacenter
  - cloud_infra
tools:
  - df
  - du
  - lsof
  - dmesg
  - lsblk
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-015
  - srv-005
  - srv-009
  - srv-011
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Did monitoring flag **90–100% disk usage on `/` or `/var` (`ENOSPC`)**, OR did an app/upload fail with **`Read-only file system (EROFS)`**?
2. Is this host running **Docker (`[srv-015]`)**, a **web/app server writing big logs**, or a **database**?
3. Has any storage/SAN outage or hypervisor host snapshot issue occurred recently?

### Initial Scope & Classification
- Distinguish **two classic Linux surprises** before deleting anything:
  1. **`df -h` shows free GB, yet apps fail with `No space left on device (ENOSPC)`:** Check **`df -i`** — 100% **inode exhaustion**!
  2. **`du -sh` total is MUCH smaller than `df -h` Used space:** Running daemon still holds an open handle to a **deleted** log (`lsof +L1`)!
- If **`Read-only file system (EROFS)`**, DO NOT force-remount `rw` blindly — inspect `dmesg` and hardware health (`[srv-009]`) first!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Safe Read-Only Capacity Snapshot)
1. **Inspect Disk % and Monitoring Alert Scope:** Run `df -hT` and `df -ihT` (read-only!) to verify WHICH mount (`/`, `/var`, `/var/lib/docker`) hit 100% blocks or 100% inodes, and screenshot the output!
2. **Never `rm` Active Database or App Files at L1:** Confirm with L2/dev owner before deleting or truncating any large `.log` or backup file, and verify backups completed (`[srv-009]` if `EROFS` hardware warnings exist!).

### L2 Technical Diagnostics
1. **Check Block Capacity, Inode Usage, Mount Options (`ro` vs `rw`), and Block Devices (read-only):**
   ```bash
   df -hT
   df -ihT
   mount | grep -E '\(ro[ ,]' || echo "No read-only mounts detected"
   lsblk -f
   ```
2. **Find Unlinked-But-Open Deleted Files (`lsof +L1`) and Top Directories (read-only):**
   ```bash
   sudo lsof +L1 | head -n 25
   sudo du -xhd 1 /var /var/log /tmp 2>/dev/null | sort -hr | head -n 15
   ```
3. **Check Kernel Storage & Filesystem Errors (`EROFS` / `EXT4-fs error` / `XFS` I/O errors):**
   ```bash
   sudo dmesg -T | grep -iE 'ext4-fs|xfs|remounting filesystem read-only|i/o error|blk_update_request' | tail -n 25
   ```

## Deep-Dive Investigation (L3)
1. **Systemd Journal / Docker / Container Overlay Bloat:** Check `journalctl --disk-usage` and `/var/lib/docker` or `/var/lib/containerd` if `/var` filled unexpectedly.
2. **Mount Point Masking Hidden Data:** If `/mnt/backup` was unmounted while a backup job wrote locally into `/mnt/backup`, remounting the external drive hides gigabytes underneath `/mnt/backup` on the root filesystem!
3. **Reserved Root Blocks (`5%` on ext4):** Non-root service accounts hit `ENOSPC` at `95%` (`100%` reported in `Use%`) while `root` still sees free space; inspect `tune2fs -l /dev/sdX | grep -i 'reserved'`.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Free Deleted Open File Space Cleanly:** Restart ONLY the specific daemon shown in `sudo lsof +L1` (never delete active database data files!), or truncate an active log safely (`truncate -s 0 /var/log/<oversized>.log`) instead of `rm`.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Vacuum Oversized Systemd Journals / Package Cache Safely:**
   ```bash
   sudo journalctl --vacuum-size=500M
   ```
   *(For inode exhaustion in a confirmed temp/spool directory, inspect sample filenames first, then clean in batches with `find <dir> -type f -mtime +7 -delete`.)*
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **If Filesystem Dropped to Read-Only (`EROFS`) Due to Corruption:**
   - First verify physical disk/RAID health (`[srv-009]`) — NEVER run `fsck` on a failing RAID array before checking hardware!
   - **NEVER run `fsck` or `xfs_repair` on a mounted read-write filesystem!** Unmount the non-root partition (`umount /data`) or boot into rescue/single-user mode for `/`, then run `sudo fsck -y /dev/<device>` (ext4) or `sudo xfs_repair /dev/<device>` (XFS).

## Verification & Post-Fix Checks
1. Confirm `df -hT` and `df -ihT` show `< 85%` utilization across all mounts and `mount` shows `(rw,...)` cleanly.
2. Confirm `dmesg -T` logs zero new I/O or filesystem errors and affected services write normally.

## Cross-Subject Escalation & Pivot Links
- **/var/lib/docker overlay2 images or unrotated container JSON logs exhausted disk:** [srv-015 — Docker Container CrashLoopBackOff, Port Conflicts (EADDRINUSE) & Overlay2 Disk Full](./srv-015-docker-container-crashloop-and-overlay-disk.md)
- **Disk full or XFS/ext4 corruption triggers read-only remount and severe iowait:** [srv-005 — Linux High CPU, Memory Pressure, OOM Killer, and I/O Wait Triage](./srv-005-linux-high-cpu-oom-killer-and-io-wait.md)
- **Physical disk or RAID controller I/O errors force Linux kernel read-only filesystem:** [srv-009 — Data Center IPMI/iDRAC/iLO, RAID Degraded, SMART Disk, and ECC/MCE Hardware Triage](./srv-009-datacenter-ipmi-raid-smart-and-ecc-hardware.md)
- **Full /boot partition or corrupt root UUID prevents Linux boot past emergency shell:** [srv-011 — Linux Boot Failure, Broken /etc/fstab Emergency Mode, GRUB Rescue, and initramfs](./srv-011-linux-boot-failure-grub-and-fstab-emergency.md)

## Client Update Snippets (EN / FR)
- **EN:** We identified the cause of the Linux storage / filesystem fault (`ENOSPC` / open deleted logs / inode usage / read-only remount), safely reclaimed capacity, and confirmed normal read/write operation.
- **FR:** Nous avons identifié l'origine du blocage disque Linux (`ENOSPC` / fichiers ouverts supprimés / inodes / montage en lecture seule), libéré l'espace de façon sécuritaire et validé le retour en lecture/écriture normale.
