---
id: srv-008
domain: 08_Servers_Cloud_Infra
subject: "Servers, Cloud & Infrastructure"
subcategory: linux_os_networking
title: Linux SSH Permission Denied, Key Auth, Host Key Mismatch, and PAM Lockout
tier: L2
keywords_en:
  - linux ssh permission denied
  - ssh publickey denied
  - ssh host key verification failed
  - pam faillock user locked linux
  - sshd config broken
keywords_fr:
  - connexion ssh refusee linux
  - cle ssh refusee linux
  - erreur empreinte hote ssh
  - compte bloque faillock linux
  - ssh permission denied pubkey
error_codes:
  - SSH_PUBLICKEY_DENIED
  - HOST_KEY_MISMATCH
tags:
  - linux_ssh_denied
  - linux_pam_selinux
os:
  - linux
environment:
  - datacenter
  - cloud_infra
tools:
  - ssh
  - sshd
  - journalctl
  - faillock
  - restorecon
risk_level: medium
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-007
  - srv-004
  - srv-013
  - id-001
---

## Fast Triage (Under 2 Minutes)
- Distinguish the exact SSH failure mode:
  - **`Connection refused` / `timed out`:** `sshd` down (`[srv-004]`) or firewall blocking TCP `22` (`[srv-007]`).
  - **`Permission denied (publickey)` (`SSH_PUBLICKEY_DENIED`):** Wrong username, missing/wrong key in `~/.ssh/authorized_keys`, **over-permissive `~/.ssh` permissions** (most common!), or SELinux context mismatch.
  - **`WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED` (`HOST_KEY_MISMATCH`):** Server rebuilt/re-IP'd — OR potential MITM; verify host key fingerprint out-of-band via IPMI/console before removing old `known_hosts`!
- Confirm whether Out-of-Band **IPMI / iDRAC / Serial Console** (`[srv-009]`) is accessible BEFORE restarting `sshd` remotely!

## Read-Only Diagnostics (L1-L2)
1. **Run verbose client debug from workstation (read-only):**
   ```bash
   ssh -vvv -o BatchMode=yes jsmith@10.0.10.25
   ```
2. **On target Linux server (via existing admin session or IPMI console), inspect SSH logs, syntax, effective `sshd` rules, and directory permissions (read-only):**
   ```bash
   sudo journalctl -u ssh -u sshd -n 60 --no-pager
   sudo sshd -t
   sudo sshd -T | grep -iE 'passwordauthentication|pubkeyauthentication|permitrootlogin|allowusers|allowgroups|maxauthtries'
   ls -ld /home/jsmith /home/jsmith/.ssh /home/jsmith/.ssh/authorized_keys 2>/dev/null || true
   ```
   *(Strict OpenSSH requirement: `/home/jsmith` must NOT be group/world-writable `g+w`/`o+w`, `.ssh` MUST be `700`, `authorized_keys` MUST be `600`, and both must be owned by `jsmith`!)*
3. **Check PAM account lockout (`faillock`) and SELinux labels (read-only):**
   ```bash
   sudo faillock --user jsmith 2>/dev/null || sudo pam_tally2 --user=jsmith 2>/dev/null || true
   ls -Z /home/jsmith/.ssh 2>/dev/null || true
   ```

## Deep-Dive Investigation (L3)
1. **SELinux `ssh_home_t` Mismatch (RHEL/Rocky/Alma):** Copying keys manually or relocating `/home` breaks `ssh_home_t` context so `sshd` silently ignores `authorized_keys` (`ausearch -m avc` reveals the block!).
2. **`PubkeyAcceptedAlgorithms` Legacy RSA Key Rejection:** Modern OpenSSH (`>= 8.8`, Ubuntu 22.04+/RHEL 9+) disables legacy `ssh-rsa` (`SHA-1`) signatures by default; migrate clients to **`ed25519`** (`ssh-keygen -t ed25519`) rather than weakening server crypto globally.
3. **`AllowUsers` / `AllowGroups` or Expired Account (`chage -l jsmith`):** Check `/etc/shadow` lock (`!`/`*`) and account expiration via `sudo chage -l jsmith`.

## Remediation (Confirm Before Running)
1. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Fix strict OpenSSH home/`.ssh` ownership, permissions, and SELinux context cleanly:
   ```bash
   sudo chmod 755 /home/jsmith
   sudo chmod 700 /home/jsmith/.ssh
   sudo chmod 600 /home/jsmith/.ssh/authorized_keys
   sudo chown -R jsmith:jsmith /home/jsmith/.ssh
   sudo restorecon -Rv /home/jsmith/.ssh 2>/dev/null || true
   ```
2. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Reset PAM `faillock` counter after verifying failed attempts were legitimate typos (not brute-force attack!):
   ```bash
   sudo faillock --user jsmith --reset
   ```
3. **[REMEDIATION — CONFIRM BEFORE RUNNING]** Always validate `sudo sshd -t` BEFORE running `sudo systemctl reload sshd` (never kill active SSH sessions while testing!).
4. **[REMEDIATION — CONFIRM BEFORE RUNNING]** For `HOST_KEY_MISMATCH` **ONLY after verifying the new `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` fingerprint matches the rebuilt host via IPMI console**, remove the stale `known_hosts` entry on the client:
   ```bash
   ssh-keygen -R 10.0.10.25
   ```

## Verification & Post-Fix Checks
1. Keep one admin shell open while testing a brand-new `ssh jsmith@10.0.10.25` session in a second terminal.
2. Confirm `journalctl -u ssh -u sshd` logs `Accepted publickey` cleanly with zero SELinux/PAM warnings.

## Cross-Subject Escalation & Pivot Links
- **Port 22 packets drop at local firewall (ufw/nftables) or unconfigured NIC:** [srv-007 — Linux Network Interfaces, LACP Bonding, DNS, and Firewall (nftables/ufw/firewalld)](./srv-007-linux-network-nic-bonding-and-firewall.md)
- **sshd.service fails syntax validation (sshd -t) or failed reload:** [srv-004 — Linux systemd Service Crash, Exit Codes, and journalctl Diagnostics](./srv-004-linux-systemd-service-crash-and-journalctl.md)
- **Unreachable Linux Azure VM requires Serial Console or VMAccess reset without SSH:** [srv-013 — Azure VM Boot Failures, RDP/SSH Unreachable, NSG & Serial Console Triage](./srv-013-azure-vm-boot-rdp-ssh-and-serial-console.md)
- **AD-joined SSSD Linux host rejects valid SSH login due to AD lockout (4740):** [id-001 — Account Lockout Investigation](../01_Identity_AD_Entra/id-001-account-lockout.md)

## Client Update Snippets (EN / FR)
- **EN:** We inspected the SSH daemon logs, fixed the `.ssh` file permissions / SELinux context / PAM lock on the Linux server, and verified clean SSH login in a fresh session.
- **FR:** Nous avons analysé les journaux SSH, corrigé les permissions `.ssh` / le contexte SELinux / le verrouillage PAM sur le serveur Linux et validé la connexion SSH dans une nouvelle session.
