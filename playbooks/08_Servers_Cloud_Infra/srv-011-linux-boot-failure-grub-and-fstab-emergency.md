---
id: srv-011
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: datacenter_hardware_boot
title: Linux Boot Failure, Broken /etc/fstab Emergency Mode, GRUB Rescue, and initramfs
tier: L3
keywords_en:
  - grub rescue emergency mode
  - linux won't boot fstab
  - dracut initqueue timeout
  - give root password for maintenance
  - linux kernel panic boot
keywords_fr:
  - mode urgence linux demarrage
  - erreur fstab grub rescue
  - serveur linux bloque au demarrage
  - mot de passe root maintenance linux
  - echec demarrage noyau grub linux
error_codes:
  - GRUB_RESCUE
  - EMERGENCY_MODE
  - DRACUT_TIMEOUT
tags:
  - linux_grub_boot
  - linux_fstab_emergency
os:
  - linux
environment:
  - datacenter
  - cloud_infra
tools:
  - IPMI Serial Console
  - GRUB
  - journalctl
  - lsblk
  - blkid
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-006
  - srv-009
  - srv-013
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is this a **virtual machine (VMware / Hyper-V / Proxmox / Azure `[srv-013]`)** or a **physical rack server (`iDRAC / iLO / IPMI`)**?
2. Did someone **just patch/reboot the server**, **attach/resize a storage disk or NFS share**, or **edit `/etc/fstab`** before it stopped booting?
3. What exact text appears on the remote console screen (`You are in emergency mode`, `dracut-initqueue timeout`, `grub rescue>`, or `Reboot and Select proper Boot device`)?
4. Do we have a **recent VM snapshot / verified backup** available before making disk/boot changes?

### Initial Scope & Classification
- Connect via **IPMI / iDRAC / iLO Virtual Console** (or Hypervisor / Cloud Serial Console) and read the exact boot halt state:
  - **`You are in emergency mode` / `Give root password for maintenance` (`EMERGENCY_MODE`):** Usually a bad UUID, typo, or unreachable SAN/NFS/secondary disk inside **`/etc/fstab`** (or failed root/data `fsck`)!
  - **`dracut-initqueue timeout — starting timeout scripts` (`DRACUT_TIMEOUT`):** Initramfs cannot find the root LVM/RAID/NVMe device (missing storage driver in new kernel initramfs or changed root UUID).
  - **`grub rescue>` (`GRUB_RESCUE`):** Damaged GRUB stage/config, wrong UEFI boot order, or moved `/boot` partition.
- **Fastest 30-second Recovery Check:** At the **GRUB boot menu**, try selecting the **previous working kernel** entry first to see if a recent kernel update broke initramfs!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Console Screenshot & Pre-Checks)
1. **Open Hypervisor / iDRAC / iLO Remote Console & Capture Screenshot (Zero Risk!):** Take a crystal-clear screenshot of the exact halt lines (especially any `Failed to mount ...` or `Dependency failed for ...` lines right above `emergency mode`)!
2. **Verify No Stray ISO / Virtual Media or Wrong Boot Drive:** Check VM settings or Virtual Media to verify an old installer ISO or unplugged USB drive isn't interrupting boot order (`No boot device`), and confirm the hypervisor datastore/SAN storage hosting the secondary disks is Online (`[srv-009]`).
3. **Check VM Snapshot / Backup Readiness:** Before L2/L3 enters root maintenance mode, verify whether a pre-reboot VM snapshot exists (or take a **cold VM snapshot/checkpoint** if safe!).

### L2 Technical Diagnostics
1. **Inside Emergency Mode Shell (enter root password), inspect failed mount units, block UUIDs, and `/etc/fstab` (read-only):**
   ```bash
   journalctl -xb -p err --no-pager | head -n 50
   systemctl --failed --no-pager
   lsblk -f
   blkid
   cat /etc/fstab
   ```
   *(Compare every `UUID=00000000-0000-0000-0000-000000000000` or `/dev/sdX` in `/etc/fstab` against `blkid` output!)*
2. **In `grub rescue>` Prompt (read-only discovery of partitions):**
   ```text
   ls
   ls (hd0,gpt2)/boot/grub2
   ```
   *(Inspect which partition contains `/boot/grub` or `/boot/grub2` and `vmlinuz`.)*

### Escalation Handoff Checklist (Before Sending to L2 / L3)
- Clear console screenshot showing exact halt message (`EMERGENCY_MODE` / `DRACUT_TIMEOUT` / `grub rescue>`), any recent disk/OS changes, and confirmation of backup/snapshot status.

## Deep-Dive Investigation (L3)
1. **Non-Critical Data/NFS Disks Blocking Whole Server Boot:** Any secondary drive, iSCSI LUN, or NFS share in `/etc/fstab` without **`nofail`** (and **`_netdev`** for network mounts) halts the entire Linux server in `EMERGENCY_MODE` if that external disk/NAS is temporarily offline!
2. **Missing Root LVM/RAID Driver in `initramfs` (`DRACUT_TIMEOUT`):** Occurs when cloning VMs across hypervisors (`virtio_scsi` vs `nvme` vs `mpt3sas`) or interrupting a kernel package update before `dracut` / `update-initramfs` finished building `/boot/initramfs-*.img`.
3. **Corrupted Root Filesystem Requiring Offline `fsck`:** If `journalctl -xb` reports `UNEXPECTED INCONSISTENCY; RUN fsck MANUALLY` on `/dev/mapper/...`, verify hardware health (`[srv-009]`) before running `fsck` from an unmounted rescue shell / Live ISO.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L1 Safe Console Checks: Unmount Stray ISO / Test Previous Kernel)** Remove any accidentally mounted virtual ISO/USB in iDRAC/VMware/Proxmox settings; if rebooting cleanly with client approval, select the **previous working kernel** at the GRUB menu to verify whether a brand-new kernel update failed boot.
2. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L2/L3 Fix Broken `/etc/fstab` Safely in Emergency Mode)**
   - If `/` is mounted read-only, remount `/` read-write temporarily and back up `/etc/fstab` FIRST:
     ```bash
     mount -o remount,rw /
     cp /etc/fstab /etc/fstab.bak.$(date +%F_%H%M)
     ```
   - Comment out or correct the failing non-root UUID/mount line (or append `,nofail,x-systemd.device-timeout=10s` — plus `_netdev` for NFS/CIFS — so a missing secondary volume never bricks server boot!).
   - **MANDATORY TEST BEFORE REBOOTING:** Always run `mount -a` (and `systemctl daemon-reload`) — if `mount -a` exits `0` cleanly, reboot safely (`systemctl reboot`).
3. **[REMEDIATION — CONFIRM BEFORE RUNNING] (L3 Rebuild Corrupted `initramfs` / `GRUB` Config)** From booted previous kernel or chroot rescue environment:
   - **RHEL / Rocky / Alma:**
     ```bash
     sudo dracut -f --regenerate-all
     sudo grub2-mkconfig -o /boot/grub2/grub.cfg
     ```
     *(On UEFI RHEL 9+, verify `/boot/efi/EFI/<distro>/grub.cfg` vs `/boot/grub2/grub.cfg` per distro standard before overwriting!)*
   - **Ubuntu / Debian:**
     ```bash
     sudo update-initramfs -u -k all
     sudo update-grub
     ```

## Verification & Post-Fix Checks
1. Reboot the Linux host cleanly while watching the IPMI console to confirm it reaches multi-user login prompt without entering `EMERGENCY_MODE` or `grub rescue>`.
2. Run `df -hT`, `systemctl --failed`, and `uname -r` to verify all filesystems mounted and services started cleanly.

## Cross-Subject Escalation & Pivot Links
- **Full /boot kernel volume or stale UUID /etc/fstab entry traps Linux in emergency mode:** [srv-006 — Linux Disk Full (ENOSPC), Inode Exhaustion, Deleted Open Files, and Read-Only FS](./srv-006-linux-disk-full-inodes-lsof-and-readonly-fs.md)
- **Underlying OS boot disk or RAID controller virtual drive failed in hardware:** [srv-009 — Data Center IPMI/iDRAC/iLO, RAID Degraded, SMART Disk, and ECC/MCE Hardware Triage](./srv-009-datacenter-ipmi-raid-smart-and-ecc-hardware.md)
- **Unbootable Linux VM sits in Azure — recover cleanly via Serial Console or Repair VM:** [srv-013 — Azure VM Boot Failures, RDP/SSH Unreachable, NSG & Serial Console Triage](./srv-013-azure-vm-boot-rdp-ssh-and-serial-console.md)

## Client Update Snippets (EN / FR)
- **EN:** Using the out-of-band server console, we diagnosed the Linux boot failure (`/etc/fstab` mount mismatch / initramfs / GRUB), applied a backed-up fix, verified `mount -a`, and confirmed the server rebooted cleanly into production.
- **FR:** Via la console hors-bande du serveur, nous avons diagnostiqué l'échec de démarrage Linux (`/etc/fstab` / initramfs / GRUB), appliqué un correctif sauvegardé, validé `mount -a` et confirmé le redémarrage complet du serveur.
