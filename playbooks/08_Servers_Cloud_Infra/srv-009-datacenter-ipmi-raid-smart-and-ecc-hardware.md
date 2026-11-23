---
id: srv-009
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: datacenter_hardware_boot
title: Data Center IPMI/iDRAC/iLO, RAID Degraded, SMART Disk, and ECC/MCE Hardware Triage
tier: L3
keywords_en:
  - ipmi raid degraded
  - idrac ilo hardware fault
  - ecc memory error mce
  - smart disk failing datacenter
  - nvme smart error linux
keywords_fr:
  - erreur materielle serveur ipmi
  - disque raid degrade
  - erreur memoire ecc serveur
  - panne disque smart datacenter
  - alerte idrac ilo materiel
error_codes:
  - MCE
  - ECC_ERROR
  - RAID_DEGRADED
  - SMART_FAIL
tags:
  - datacenter_ipmi_hardware
  - datacenter_raid_smart
os:
  - linux
  - cross_platform
environment:
  - datacenter
  - cloud_infra
tools:
  - ipmitool
  - smartctl
  - nvme-cli
  - storcli
  - mdadm
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-010
  - srv-006
  - srv-011
  - srv-005
---

## Fast Triage (Under 2 Minutes)
- **Check Out-of-Band BMC (Dell iDRAC / HPE iLO / Supermicro IPMI) BEFORE walking to the rack:** Record the exact Service Tag/Serial (do not log raw serials into shared tickets outside client PSA), amber LED location (Front/Rear chassis UID blink), System Event Log (SEL) fault, and RAID Virtual Disk state (**Optimal** vs **Degraded** vs **Offline**).
- **Critical Data Center Rule:** Before pulling ANY hot-swap drive from a rack server:
  1. **Verify RAID level** (`RAID 1/5/6/10` — **NEVER** pull a drive from `RAID 0` or a double-faulted `RAID 5`!).
  2. **Blink the exact Bay Locator LED** (`storcli` / iDRAC / iLO) and **triple-check Bay # + WWN/Serial** so you never yank a healthy member drive!

## Read-Only Diagnostics (L1-L2)
1. **Query BMC System Event Log & Hardware Sensors via `ipmitool` (read-only):**
   ```bash
   sudo ipmitool chassis status
   sudo ipmitool sel list | tail -n 30
   sudo ipmitool sdr elist | grep -iE 'fail|warn|crit|degrad|ecc|pwr|temp' || true
   ```
2. **Inspect Software RAID (`mdadm`) or Hardware RAID Controller (`storcli` / `perccli`, read-only):**
   ```bash
   cat /proc/mdstat
   sudo mdadm --detail /dev/md0 2>/dev/null || true
   sudo storcli /c0 show 2>/dev/null || sudo perccli /c0 show 2>/dev/null || true
   ```
3. **Inspect SATA/SAS SMART Health & NVMe Wear/Media Errors (read-only):**
   ```bash
   sudo smartctl -H -A /dev/sda 2>/dev/null || true
   sudo nvme smart-log /dev/nvme0n1 2>/dev/null || true
   ```
   *(Key SMART danger indicators: `Reallocated_Sector_Ct > 0`, `Current_Pending_Sector > 0`, `Offline_Uncorrectable > 0`, NVMe `media_errors > 0`, or `critical_warning != 0`.)*
4. **Inspect ECC Memory Errors & Machine Check Exceptions (`MCE` / `ECC_ERROR`, read-only):**
   ```bash
   sudo dmesg -T | grep -iE 'mce|edac|ecc|hardware error|corrected|uncorrected' | tail -n 30
   sudo edac-util -v 2>/dev/null || true
   ```

## Deep-Dive Investigation (L3)
1. **Correctable (CE) vs. Uncorrectable (UE) ECC RAM Errors:** Occasional single-bit CE counts are logged and fixed by hardware, whereas **rapidly climbing CE counts on one specific DIMM slot** (`CPU1_DIMM_A2`) or ANY **Uncorrectable Error (`UE`)** requires scheduling a maintenance window to reseat/replace that exact DIMM.
2. **RAID BBU / CacheVault Degraded (`Write-Back` -> `Write-Through`):** A failed RAID controller battery/supercapacitor drops array caching to `Write-Through`, crippling database/VM I/O (`D_STATE` spikes in `[srv-005]`) even when all disks are healthy!
3. **Backplane / SAS Cable Reseat vs. Dead Drive:** Multiple drives dropping simultaneously on the same enclosure/backplane indicates a loose Mini-SAS HD cable, failing expander backplane, or HBA overheat rather than 4 dead disks at once.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Locate & Hot-Swap a Confirmed Failed RAID Drive (`RAID_DEGRADED`):**
   - Confirm backups are current and array redundancy can tolerate 1 replacement.
   - Blink the failed drive's physical bay LED (`sudo storcli /c0/e<enc>/s<slot> start locate` or via iDRAC/iLO), visually confirm the blinking amber/blue bay in the rack, pull the failed carrier slowly (wait 30s for spin-down), and seat the matching **exact capacity / interface (SAS vs SATA, 512n vs 4Kn)** replacement drive.
   - Verify automatic rebuild starts (or assign as hotspare / mark Foreign Config import ONLY after confirming drive is blank/intended target!).
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** **Replace Faulty ECC DIMM / HBA / System Board:** Schedule maintenance outage -> gracefully shut down OS (`sudo systemctl poweroff`) -> drain residual flea power (unplug both A/B PSUs + hold power button 15s) -> wear ESD wrist strap -> swap exact faulted DIMM slot (`A2`/`B2`) -> clear BMC SEL fault counter only after documenting incident ID.

## Verification & Post-Fix Checks
1. Confirm `cat /proc/mdstat` or `storcli /c0 show` shows RAID array **`Rebuild` -> `Optimal`** (100% synced) and `smartctl -H` / `nvme smart-log` reports **`PASSED`** / `0` media errors.
2. Confirm `ipmitool sel list` and `edac-util -v` accumulate zero new hardware/ECC faults and chassis front LED returns steady blue/green.

## Cross-Subject Escalation & Pivot Links
- **Chassis thermal alarm or PSU redundancy alert traces to rack A/B PDU power loss:** [srv-010 — Data Center Rack Power (A/B PSU), Thermal Trips, and SFP+/Fiber Optical Diagnostics](./srv-010-datacenter-rack-power-thermal-and-sfp-optics.md)
- **Failed physical RAID member or controller media error triggers Linux read-only FS:** [srv-006 — Linux Disk Full (ENOSPC), Inode Exhaustion, Deleted Open Files, and Read-Only FS](./srv-006-linux-disk-full-inodes-lsof-and-readonly-fs.md)
- **Missing RAID/HBA driver or degraded boot drive drops server to GRUB Rescue:** [srv-011 — Linux Boot Failure, Broken /etc/fstab Emergency Mode, GRUB Rescue, and initramfs](./srv-011-linux-boot-failure-grub-and-fstab-emergency.md)
- **Degraded RAID write-back cache (dead BBU) causes severe Linux I/O wait latency:** [srv-005 — Linux High CPU, Memory Pressure, OOM Killer, and I/O Wait Triage](./srv-005-linux-high-cpu-oom-killer-and-io-wait.md)

## Client Update Snippets (EN / FR)
- **EN:** We inspected the server BMC/IPMI hardware event logs, isolated the failing storage/memory component, completed the verified hardware replacement / RAID rebuild check, and confirmed the host reports **Optimal** health.
- **FR:** Nous avons consulté les journaux matériels BMC/IPMI du serveur, isolé le composant disque/mémoire défaillant, effectué le remplacement / la reconstruction RAID sécuritaire et confirmé le retour à l'état **Optimal**.
