---
id: srv-015
domain: 08_Servers_Cloud_Infra
subject: Servers, Cloud & Infrastructure
subcategory: cloud_azure_gcp_docker
title: Docker Container CrashLoopBackOff, Port Conflicts (EADDRINUSE) & Overlay2 Disk Full
tier: L2
keywords_en:
  - docker container keeps restarting
  - docker crashloopbackoff
  - docker no space left on device
  - overlay2 disk full
  - port already in use docker
  - container oom killed 137
  - image pull backoff
keywords_fr:
  - conteneur docker redemarre en boucle
  - disque plein docker overlay2
  - erreur port deja utilise conteneur
  - conteneur tue memoire oom 137
  - echec telechargement image docker
error_codes:
  - CrashLoopBackOff
  - EADDRINUSE
  - ImagePullBackOff
tags:
  - docker_container_crash
  - docker_overlay_disk
os:
  - linux
  - windows
  - cross_platform
environment:
  - datacenter
  - cloud_infra
  - local_endpoint
tools:
  - Docker CLI
  - Linux systemd / journalctl
  - ss / lsof
risk_level: high
requires_admin: true
last_verified: 2026-11-22
related_ids:
  - srv-006
  - srv-004
  - srv-007
  - app-004
---

## Fast Triage (Under 2 Minutes)
### Questions to Ask the User (Classify the Issue)
1. Is **one specific container app** down/restarting (`Restarting (1)` / `CrashLoopBackOff`), OR have **ALL containers on the Linux server stopped** (classic sign of `/var/lib/docker` hitting 100% disk -> `[srv-006]`)?
2. Did someone **just deploy a new image tag / edit `compose.yaml`**, or did an automated OS update run?
3. What is the **exact container name** and whether it holds a stateful database (`PostgreSQL` / `MySQL` — **CRITICAL:** never prune Docker volumes blindly!)?

### Initial Scope & Classification
- Check host disk space (`df -h`), container `ExitCode` (`1` = app crash; `137` = OOMKilled; `EADDRINUSE` = port taken; `ImagePullBackOff` = registry/network fail), and stderr logs cleanly BEFORE cleaning anything!

## Read-Only Diagnostics (L1-L2)
### L1 First-Line Checks (Start Here — Safe Read-Only Status & Disk Check)
1. **Run Non-Destructive Status & Disk Glance First (`docker ps -a` + `df -h`):** Check whether ALL containers died because disk `/` or `/var/lib/docker` is 100% full (`[srv-006]`), vs one container looping `Restarting` — screenshot `docker ps -a` and `docker logs --tail 50 <container-name>` for L2/dev review!
2. **Never Run `docker system prune --volumes` at L1:** Confirm whether PostgreSQL/MySQL/Redis stateful containers exist before touching any image/cache cleanup!

### L2 Technical Diagnostics
Inspect container status, restart counters, exit codes, OOM flags, recent stderr logs, and host disk/inode utilization without altering running containers:

```bash
# 1. List all containers including exited/restarting ones
docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

# 2. Inspect exact ExitCode, OOMKilled state, and Engine error string
docker inspect <container-name> --format "RestartCount={{.RestartCount}} Status={{.State.Status}} ExitCode={{.State.ExitCode}} OOMKilled={{.State.OOMKilled}} Error={{.State.Error}}"

# 3. View last 150 lines of container logs
docker logs --tail 150 <container-name>

# 4. Check Docker disk breakdown and host filesystem + inode usage
docker system df
df -h /var/lib/docker
df -i /var/lib/docker
```

If container startup fails with `bind: address already in use` / `EADDRINUSE` or image pull errors:

```bash
# Find which host process or container already holds the target TCP/UDP port (e.g. 8080)
ss -tulpn | grep :8080

# Inspect Docker daemon logs (network, overlay2, registry/proxy TLS failures)
journalctl -u docker -n 100 --no-pager
```

## Deep-Dive Investigation (L3)
Analyze the top four production container failure patterns:

1. **Unrotated Container JSON Logs Filling `/var/lib/docker`:**
   - Default Docker `json-file` logging has **no size limit**; verbose apps write 50+ GB `*-json.log` files inside `/var/lib/docker/containers/<id>/`.
   - Locate largest logs cleanly (read-only): `du -h --max-depth=2 /var/lib/docker/containers/ | sort -hr | head -n 15`.
2. **Kernel OOM Kill (`ExitCode 137` + `OOMKilled=true`):**
   - Verify container memory limit (`docker inspect <name> --format "{{.HostConfig.Memory}}"`) and check host kernel OOM logs (`dmesg -T | grep -i oom` or `journalctl -k | grep -i oom`).
3. **`ImagePullBackOff` / Registry Pull Failures:**
   - Distinguish bad tag/missing private registry credentials (`unauthorized: authentication required`), Docker Hub rate limits, DNS failure inside host, or corporate SSL inspection proxy blocking registry HTTPS pulls (check `/etc/systemd/system/docker.service.d/` proxy config).
4. **Volume Permission / Config Drift (`ExitCode 1` / `126` / `139`):**
   - Non-root container UID mismatches against bind-mounted host folders, missing `.env` secrets, or corrupted database lock files after unclean host reboot.

## Remediation (Confirm Before Running)
> **[REMEDIATION — CONFIRM BEFORE RUNNING]** NEVER run `docker system prune -a --volumes` or delete `/var/lib/docker/volumes` blindly — pruning unused volumes permanently wipes database/application data belonging to stopped containers! Never kill another service on an `EADDRINUSE` port without confirming what owns that port.

1. **Safe Disk Recovery for Full `/var/lib/docker` (`No space left on device`):**
   - Scope: Exited build cache and dangling images only (explicitly **WITHOUT** `--volumes`!).
   - Prerequisite: Confirm no needed rollback images or stopped stateful containers rely on untagged images.
   ```bash
   # Preview what will be removed before running cleanup
   docker image ls -f "dangling=true"
   # Safe cleanup: removes unused build cache and dangling images WITHOUT touching volumes
   docker builder prune -f
   docker image prune -f
   ```
   - For oversized active container log files (`*-json.log`), avoid `rm` (which leaves deleted file handles open until restart!); truncate safely only after exporting needed diagnostic tail lines, then configure `/etc/docker/daemon.json` log rotation (`max-size: "50m"`, `max-file: "3"`).
2. **Fix `EADDRINUSE` Port Collision:**
   - Coordinate with app owner either to stop the conflicting legacy daemon/container shown by `ss -tulpn`, or remap the container host port in `compose.yaml` (`"127.0.0.1:8081:8080"`).
3. **Fix `ExitCode 137` (`OOMKilled`) / `ImagePullBackOff`:**
   - Adjust container memory limits in `compose.yaml` / Kubernetes manifests cleanly if legitimate app footprint grew (or fix memory leak with dev team), refresh registry login (`docker login <registry>`), and redeploy with `docker compose up -d`.

## Verification & Post-Fix Checks
- Verify `docker ps` reports `Up` and `(healthy)` (not `Restarting`) for at least 5–10 minutes with `RestartCount` stable.
- Confirm `df -h /var/lib/docker` and `df -i /var/lib/docker` maintain >= 20% headroom, and verify log rotation policy is active for new containers.
- Test application HTTP/TCP health endpoint and confirm persistent data volumes mounted cleanly.

## Cross-Subject Escalation & Pivot Links
- **/var/lib/docker overlay2 or unrotated JSON logs fill host Linux disk (ENOSPC):** [srv-006 — Linux Disk Full (ENOSPC), Inode Exhaustion, Deleted Open Files, and Read-Only FS](./srv-006-linux-disk-full-inodes-lsof-and-readonly-fs.md)
- **docker.service daemon fails or systemd unit wraps crashing container runtime:** [srv-004 — Linux systemd Service Crash, Exit Codes, and journalctl Diagnostics](./srv-004-linux-systemd-service-crash-and-journalctl.md)
- **Host nftables/ufw firewall or DNS bridge blocks registry pulls (ImagePullBackOff):** [srv-007 — Linux Network Interfaces, LACP Bonding, DNS, and Firewall (nftables/ufw/firewalld)](./srv-007-linux-network-nic-bonding-and-firewall.md)
- **Corporate SSL inspection proxy CA triggers registry x509 certificate error:** [app-004 — Developer Git/NPM/PIP SSL Proxy Certificate Errors & PowerShell ExecutionPolicy](../09_Apps_LOB/app-004-dev-git-ssl-proxy-cert-and-powershell-policy.md)

## Useful Links & External Tools
- [Docker Hub Status](https://www.dockerstatus.com/) — Verify Docker Hub registry availability and pull service incidents.

## Client Update Snippets (EN / FR)
- **EN:** Hi `<user>`, we investigated the container outage (`<CrashLoopBackOff / EADDRINUSE / Disk Full>`) on `<host>`. We preserved all persistent data volumes, resolved `<log/disk bloat / port collision / memory limit / pull auth>`, and verified the container (`<name>`) is running and healthy. Please test your application endpoint.
- **FR:** Bonjour `<user>`, nous avons analysé la panne du conteneur (`<CrashLoopBackOff / EADDRINUSE / Disque plein>`) sur `<host>`. Après avoir préservé tous les volumes de données, nous avons corrigé `<saturation disque/journaux / conflit de port / limite mémoire / authentification registre>` et vérifié l'état stable (`Up / healthy`). Merci de valider l'application.
