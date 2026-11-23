---
id: srv-013
domain: 08_Servers_Cloud_Infra
subject: Servers, Cloud & Infrastructure
subcategory: cloud_azure_gcp_docker
title: Azure VM Boot Failures, RDP/SSH Unreachable, NSG & Serial Console Triage
tier: L3
keywords_en:
  - azure vm unreachable
  - azure vm won't boot
  - azure rdp failed
  - azure ssh timeout
  - azure serial console
  - boot diagnostics screenshot
  - azure nsg blocking port
  - azure allocation failed
keywords_fr:
  - vm azure demarre pas
  - connexion rdp ssh azure echouee
  - console serie azure vm
  - diagnostics demarrage azure
  - regle nsg bloque azure
  - erreur allocation vm azure
error_codes:
  - AllocationFailed
  - VMExtensionProvisioningError
  - OSProvisioningTimedOut
  - NSG_DENY
tags:
  - azure_vm_triage
  - azure_vm_boot_rdp
os:
  - windows
  - linux
  - cross_platform
environment:
  - azure
  - cloud_infra
tools:
  - Microsoft Azure Portal
  - Azure CLI (az)
  - PowerShell (Az.Compute / Az.Network)
  - Azure Serial Console & Boot Diagnostics
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-014
  - srv-003
  - srv-008
  - net-005
  - srv-001
---

## Fast Triage (Under 2 Minutes)
- **Check Azure Service Health & Region Status first:** Before troubleshooting guest OS internals, confirm the Azure region is healthy and inspect **VM -> Resource Health** for platform host reboots or maintenance events.
- **Check VM PowerState & ProvisioningState:** Determine if the VM shows `VM running`, `VM deallocated`, `AllocationFailed` (regional capacity exhaustion on VM SKU/zone), or `Failed` (`OSProvisioningTimedOut` / `VMExtensionProvisioningError`).
- **Scope outage (One VM vs. All VMs in Subnet):** If all VMs in a subnet lost RDP/SSH simultaneously, suspect **Subnet NSG**, **User-Defined Route (UDR `0.0.0.0/0` to an unhealthy NVA/Firewall)**, or **Site-to-Site VPN / ExpressRoute**.
- **Check Boot Diagnostics screenshot immediately:** A screenshot showing the Windows login screen or Linux `login:` prompt proves the guest OS booted cleanly — focus immediately on **NSG**, **OS Firewall**, or **Routing/Bastion**, not OS recovery!

## Read-Only Diagnostics (L1-L2)
Use Azure CLI (`az`) read-only commands to check VM power state, provisioning messages, Boot Diagnostics serial log, extensions, and effective NIC security rules:

```bash
# 1. Check VM instance power state, provisioning state, and Azure Resource Health
az vm get-instance-view --resource-group <rg-name> --name <vm-name> --output table

# 2. Fetch Boot Diagnostics serial console output (no reboot required)
az vm boot-diagnostics get-boot-log --resource-group <rg-name> --name <vm-name>

# 3. Inspect VM Extensions (e.g. CustomScriptExtension, AMA, Defender)
az vm extension list --resource-group <rg-name> --vm-name <vm-name> --output table
```

Inspect **Effective Security Rules** and **Effective Routes** on the VM's Network Interface (`NIC`) — remember BOTH Subnet NSG AND NIC NSG must allow traffic independently:

```bash
# Find NIC name attached to VM
az vm nic list --resource-group <rg-name> --vm-name <vm-name> --output table

# View combined Subnet + NIC Effective NSG rules and Effective UDR Routes
az network nic list-effective-nsg --resource-group <rg-name> --name <nic-name> --output table
az network nic show-effective-route-table --resource-group <rg-name> --name <nic-name> --output table
```

Equivalent PowerShell (`Az.Compute`) status check:

```powershell
Get-AzVM -ResourceGroupName "<rg-name>" -Name "<vm-name>" -Status |
  Select-Object Name, ResourceGroupName -ExpandProperty Statuses | Format-Table Code, DisplayStatus, Message
```

## Deep-Dive Investigation (L3)
Analyze the failure layer based on Boot Diagnostics and Effective NSG/Routes:

1. **Layer 1 — Control Plane / Host (`AllocationFailed`, `OSProvisioningTimedOut`):**
   - `AllocationFailed` occurs when the requested VM size/zone lacks capacity in the current cluster during Start/Resize.
   - `OSProvisioningTimedOut` on newly deployed Linux/Windows images means `waagent` or sysprep failed to report ready within the timeout (often custom image missing cloud-init/waagent or blocked metadata access to `169.254.169.254`).
2. **Layer 2 — Network (`NSG_DENY` / UDR Asymmetric Routing / Guest Firewall):**
   - Verify port `3389` (RDP) or `22` (SSH) isn't blocked by a lower-priority Deny rule on either the **Subnet NSG** or **NIC NSG** (`Priority` number closer to `100` wins).
   - Check `Effective Routes` for `User` UDRs routing traffic to a stopped Azure Firewall / FortiGate NVA.
   - Use **Azure Network Watcher -> IP Flow Verify** and **Connection Troubleshoot** (`az network watcher test-ip-flow`) to test exact packet allow/deny from your source IP without guessing.
3. **Layer 3 — Guest OS Stuck at Boot (BSOD, BitLocker/ADE, Kernel Panic, Bad `/etc/fstab`):**
   - Open **Azure Portal -> VM -> Help -> Serial Console**:
     - **Windows:** Wait for `SAC>` prompt, run `cmd`, then `ch -si 1` to authenticate as local admin and inspect Event Logs, `bcdedit`, or `netsh advfirewall`.
     - **Linux:** Inspect emergency shell / GRUB timeout (`fstab` UUID error, full `/var` disk, `sshd` syntax error with `sshd -t`, or `ufw`/`firewalld` blocking SSH).
4. **Layer 4 — Non-Destructive Run Command (`waagent` / Guest Agent Healthy):**
   - Run read-only diagnostics via `az vm run-command invoke` (works even when RDP/SSH is blocked by OS firewall, as long as VM Agent is `Ready`):
     ```bash
     # Windows read-only RDP & firewall check via VM Agent
     az vm run-command invoke --resource-group <rg-name> --name <vm-name> --command-id RunPowerShellScript --scripts "Get-Service TermService; Get-NetFirewallRule -DisplayGroup 'Remote Desktop' | Select DisplayName,Enabled,Action"

     # Linux read-only SSH & disk check via VM Agent
     az vm run-command invoke --resource-group <rg-name> --name <vm-name> --command-id RunShellScript --scripts "systemctl status ssh sshd --no-pager; df -h"
     ```

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER open TCP `3389` (RDP) or `22` (SSH) to `0.0.0.0/0` (`Any`) on a Public IP NSG. Prefer **Azure Bastion**, **Corporate VPN private IP**, or **Microsoft Defender for Cloud Just-In-Time (JIT) VM Access**. NEVER redeploy or resize an Azure VM before verifying no production data resides on the **ephemeral temporary disk (`D:` / `/mnt`)**, because redeployment wipes the temporary disk!

1. **Resolve OS Firewall / Dead RDP/SSH Service Without Downtime:**
   - Scope: Single VM guest OS via **Azure Serial Console** or **VM Reset password / Reset configuration only** (`VMAccessAgent`).
   - Prerequisite: `VMAccess` extension healthy or Serial Console interactive credentials available; backup/snapshot taken before registry or `fstab` edits.
   - Enable **Remote Desktop** / restart `sshd` or reset local admin configuration via Portal -> **Help -> Reset password -> Reset configuration only** (`sshd_config` / Windows RDP settings).
2. **Resolve NSG Block Securely (`NSG_DENY`):**
   - Scope: Target NSG rule allowing ONLY specific MSP jumpbox / corporate static IP (`198.51.100.10/32`) or **AzureBastionSubnet**, never `Internet`/`Any`.
   - Prerequisite: Network change approval and confirm whether Subnet NSG and NIC NSG both need matching Allow rules.
3. **Resolve `AllocationFailed` (Capacity Error on Deallocated VM):**
   - Prerequisite: Confirm application compatibility with target SKU and maintenance window.
   - **[REMEDIATION — CONFIRM BEFORE RUNNING]** Stop (Deallocate) the VM completely (`az vm deallocate`), then start again (or temporarily resize within the same disk/vCPU family), which frees the old pinned cluster placement and schedules on healthy capacity.
4. **Severe OS Boot Failure (OS Disk Repair VM Pattern):**
   - Take an **OS Disk Snapshot** first, then use `az vm repair create` to attach a copy of the OS disk as a data disk onto a rescue VM to fix `/etc/fstab`, corrupt registry hive, or Windows update loops cleanly before swapping the repaired OS disk back.

## Verification & Post-Fix Checks
- Verify `az vm get-instance-view` shows `PowerState/running` and `ProvisioningState/succeeded`, and Boot Diagnostics screenshot shows a clean OS login prompt.
- Confirm connection succeeds strictly over **Azure Bastion**, **Site-to-Site VPN**, or **JIT approved source IP** — verify no `0.0.0.0/0` RDP/SSH rules remain in Effective NSGs.
- If a snapshot or repair VM was created during recovery, verify disk/application integrity and schedule cleanup of temporary repair resources after customer sign-off.

## Cross-Subject Escalation & Pivot Links
- **Missing Azure RBAC rights prevent viewing VM Boot Diagnostics or modifying NIC NSGs:** [srv-014 — Azure RBAC 403 Errors, Storage Permission Mismatch & Key Vault Firewall Blocks](./srv-014-azure-rbac-403-storage-and-keyvault-firewall.md)
- **Azure Windows VM shows login screen on Boot Diagnostics yet RDP rejects CredSSP/NLA:** [srv-003 — Remote Desktop (RDP) Refused, CredSSP Encryption Oracle, and NLA Failure](./srv-003-rdp-credssp-and-nla-connection-failed.md)
- **Azure Linux VM boots cleanly yet SSH rejects key or PAM auth:** [srv-008 — Linux SSH Permission Denied, Key Auth, Host Key Mismatch, and PAM Lockout](./srv-008-linux-ssh-permission-denied-and-pam-lockout.md)
- **Private Azure VNet VM is unreachable because Site-to-Site IPsec VPN tunnel dropped:** [net-005 — Site-to-Site IPsec VPN Tunnel Down (IKE Phase 1/2 Mismatch & DPD Timeouts)](../04_Network_VPN_VoIP/net-005-site-to-site-ipsec-vpn-tunnel-down.md)
- **Windows Azure VM C: drive full prevents OS boot or extension readiness:** [srv-001 — Windows Server Disk Space Exhaustion and VSS Shadow Copy Backup Failure](./srv-001-vss-backup-and-disk-triage.md)

## Useful Links & External Tools
- [Microsoft Azure Portal](https://portal.azure.com/) — Access VM Boot Diagnostics screenshots, Serial Console, Resource Health, and Network Watcher IP Flow Verify.
- [Azure Service Status](https://azure.status.microsoft/) — Check active Azure region compute, storage, or networking incidents.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we investigated the unreachable Azure VM (`<vm-name>`) via Boot Diagnostics, Effective NSG rules, and Serial Console/VM Agent checks. The root cause (`<NSG rule / Guest firewall / Host allocation / Boot issue>`) has been resolved cleanly with zero temp-disk data loss, and RDP/SSH connectivity is verified via `<Bastion / VPN>`. Please test your session.
- **FR:** Bonjour `<user>`, nous avons diagnostiqué la machine virtuelle Azure (`<vm-name>`) via les diagnostics de démarrage, les règles NSG effectives et la console série. La cause (`<règle NSG / pare-feu invité / allocation Azure / démarrage OS>`) a été corrigée sans perte de données et l'accès `<RDP/SSH>` via `<Bastion/VPN>` est rétabli. Merci de confirmer votre connexion.
