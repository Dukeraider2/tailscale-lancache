# v2 development: first milestone

Status: source implementation for staged testing. No v2 production release or live migration has occurred. The Tailscale `/32` transport, Mullvad coexistence approach and shared 512 GB storage budget remain the base.

## Service states

| Service ID | Initial state | Coverage and limits |
| --- | --- | --- |
| `steam` | Default baseline | Content HITs verified for a 140 reinstall with Mullvad connected; see the [test evidence](validation/steam-140.md). Other acceptance cases remain. |
| `epic` | Experimental opt-in | Upstream Epic CDN list; launchers and individual games require testing. |
| `ea` | Experimental opt-in | Upstream Origin CDN list; this is not proof of current EA App compatibility. |
| `microsoft-xbox` | Experimental opt-in | Upstream Xbox Live content list; not a guarantee for all Xbox/Game Pass/Store titles. |
| `microsoft-updates` | Separate experimental opt-in | Upstream Windows Update/Office delivery list; not implied by Xbox selection. |
| `gog` | Research only | No validated profile. Direct downloads remain in use. |
| `amazon` | Research only | No validated Amazon Games profile. Direct downloads remain in use. |
| `nexusmods` | Research only | Upstream lists a delivery hostname, but HTTP cacheability and authenticated-download behavior need testing. |
| `loverslab` | Research only | No validated profile; authenticated download and HTTPS behavior need testing. |

The upstream [service registry](https://github.com/uklans/cache-domains/blob/f7d6206f4769d6bf0274b5ad79e6bebda7753b17/cache_domains.json) and [domain files](https://github.com/uklans/cache-domains/tree/f7d6206f4769d6bf0274b5ad79e6bebda7753b17) provide hostname evidence, not results from this deployment. Selected host lists are recorded in `server/domains.lock.json` with the upstream commit and MIT license in `third_party/`. No automatic domain-list update occurs in the generator.

LANCache [per-service DNS settings](https://lancache.net/docs/containers/dns/) let the generator enable selected services without enabling generic caching for everything. Monolithic's [SNI forwarding](https://lancache.net/docs/containers/sniproxy/) passes HTTPS through without decrypting or caching it. The staging server must allow client TCP 443 through Tailscale and the LAN firewall, in addition to TCP 80 and DNS transport 8053. Do not install a separate SNI container on the shared port 443: Monolithic provides that listener.

## Try the generated configuration

List the catalog without contacting any service or changing settings:

```sh
python server/profiles.py --list
```

Generate matching server and client configurations for Steam plus Epic on a staging dataset/address:

```sh
python server/generate.py --cache-ip 192.168.50.10 --subnet 192.168.50.0/24 --gateway 192.168.50.1 --interface eth0 --dataset /mnt/POOL/lancache --tailnet-suffix example-tailnet.ts.net --services steam,epic --allow-experimental
```

This writes `generated/compose.yaml` and `generated/client-plan.json`. Omitting `--services` retains Steam-only behavior. Non-Steam supported profiles require `--allow-experimental`; research-only profiles fail generation even with that flag. Multiple services share the same content cache and dataset budget. Adding services does not allocate additional storage.

On a staging Windows client, preview the matching plan from an Administrator PowerShell:

```powershell
.\windows\Install.ps1 -CacheIP '192.168.50.10' -TailnetSuffix 'example-tailnet.ts.net' -ServicePlan '.\generated\client-plan.json' -AllowExperimental -WhatIf
```

Read the preview and generated namespaces before running without `-WhatIf`. The installer requires the plan's cache address to match, validates its format, and separately requires `-AllowExperimental`. Plans are local configuration files, not signed or trusted downloads: use the file you generated and reviewed. Supply the correct tailnet suffix as in v1. Existing v1 installations must be uninstalled before installing a new plan; there is no in-place upgrade yet. Keep your original configuration available for rollback.

The client adds extra service namespaces under a separate ownership marker. Uninstall removes those rules alongside owned Steam and MagicDNS rules. It does not change launcher credentials or enable TLS interception. Account, storefront and login domains are not added as whole-provider suffixes.

Upstream wildcard domains become NRPT suffix rules. Windows suffix rules also match the apex; the server DNS still decides whether that hostname matches its upstream cache list. For example `.windowsupdate.com` is an explicit, separately opted-in exception to the general rule against broad two-label suffixes. `.microsoft.com` and `.epicgames.com` are rejected by plan validation. Domain lists bundled inside mutable server images may differ from the client snapshot. Check DNS parity on the staged server; image/domain pinning is still pending.

## Acceptance before enabling a profile on the live client

### Isolated server staging

The generator also supports a user-defined Docker bridge and a distinct Tailscale hostname. This avoids consuming a second LAN/DHCP address and keeps the live Steam container network separate. First inspect the NAS Docker networks and all advertised tailnet routes; the example bridge below must not overlap either. No host ports are published. Reach the private bridge address through the staging node's approved Tailscale `/32` route.

```sh
python server/generate.py --cache-ip 172.28.80.10 --subnet 172.28.80.0/24 --gateway 172.28.80.1 --network-driver bridge --hostname epic-lancache-stage --dataset /mnt/POOL/lancache/stage-epic --tailnet-suffix example-tailnet.ts.net --cache-gib 4 --quota-gb 16 --services steam,epic --allow-experimental
```

Create a separate child dataset with a 16 GB hard quota and verify sufficient free space under the parent cache quota. The 4 GiB content cache leaves the default 10 GiB free-space allowance within that child quota. A child dataset inside a 512 GB capped parent does not increase the parent limit. Inspect actual usage before starting it; do not reduce the live cache's size or delete content to make room automatically. Authenticate the staging Tailscale node and approve only its route.

Before changing any client DNS, test the staged route, cache heartbeat, HTTP and TLS forwarding with explicit per-request address overrides:

```powershell
.\windows\Test-StagedEndpoint.ps1 -ServicePlan '.\generated\client-plan.json' -Hostname 'download.epicgames.com'
```

This read-only probe requires the approved Tailscale `/32` route and validates the origin HTTPS certificate without certificate exceptions. It uses HEAD requests, does not change DNS or VPN state, and does not download game content. An origin HTTP error such as 403 can still establish transport reachability; the report includes status and curl exit codes and explicitly leaves `CacheHitProven` false. Run it in both VPN states. Content hostnames in a profile are not a guarantee that every hostname currently serves HTTP or TLS successfully; investigate failures before redirecting the launcher.

The v2 installer is not an in-place migration mechanism and refuses to overwrite an existing runtime. Keep the current Steam DNS rules pointing at the live cache during initial probes. A separate, reversible Epic-only client DNS trial still needs implementation and validation before testing the launcher alongside an existing v1 client.

### Local TrueNAS installer fallback

If browser control is unavailable, `server/stage_truenas.py` can run on the TrueNAS host using its existing local `midclt`, Docker, `ip` and Python tools. It uses the documented [custom app API](https://api.truenas.com/v25.10/api_methods_app.create.html); it does not create an API key, enable SSH or require a password in code.

First inspect the plan without applying changes, using your real parent dataset and tailnet suffix:

```sh
sudo python3 server/stage_truenas.py --parent-dataset POOL/lancache --tailnet-suffix example-tailnet.ts.net
```

The installer checks that the parent exists at its expected mountpoint, has a hard quota and at least 16 GB available, and that the proposed bridge subnet does not overlap existing Docker networks or host IPv4 routes. Select a different subnet with `--cache-ip`, `--subnet` and `--gateway` if needed; also check it against routes advertised elsewhere in the tailnet. It refuses to reuse any existing `stage-epic` child, staging app or staging path.

After reviewing the plan, rerun with `--apply`. That mode pulls the official cache image, pins the pulled digest and determines its worker UID/GID. It then creates only a 16 GB `stage-epic` child dataset, private state/deployment directories and the separate `epic-lancache-stage` custom app. Cache and log directories use the image's worker ownership. The parent quota and existing apps remain unchanged. A failed new deployment is left for inspection; the script does not destroy datasets or delete an app automatically.

Authenticate the new Tailscale node from its container logs and approve only the cache `/32` route before probing it from Windows. The generated private deployment and client plan are stored under the staging dataset's `deployment` directory; keep them outside Git. The installer has offline tests, including refusal and default no-write behavior; a live TrueNAS run is still part of staging acceptance, especially on nightly builds whose API may differ.

### Per-service acceptance checklist

For each service, record the launcher/version and check all of the following with Mullvad connected and disconnected:

1. Steam, MagicDNS, ordinary DNS and cache heartbeat still pass the v1 connectivity test.
2. Selected content hostnames resolve to the cache; non-selected service and account domains resolve normally.
3. HTTPS connections pass through with valid origin certificates and no certificate exceptions.
4. Launcher login, catalog access and downloads work, including range/resume requests where supported.
5. A repeated identical download produces actual cache HIT log evidence. Record total downloaded bytes and HIT bytes; HTTP 204 heartbeat results do not establish a cache HIT.
6. Restart the PC and server app, then repeat while on the home LAN and a remote network. Exercise Tailscale/Mullvad transitions and a server outage.
7. Uninstall restores the prior DNS preferences and metric settings. Verify original Steam-only operation after rollback.

Reports may include account identifiers, signed URLs or IP addresses. Store them outside Git and redact before sharing. Do not capture launcher passwords, cookies or authentication tokens. v2 retains v1's manual recovery from a cache outage; automatic failover has not been implemented.

## Milestones

The [service requirements and route-verification plan](v2-service-requirements.md) covers Steam, Epic, EA, Microsoft PC games and updates, GOG, Amazon, Nexus Mods, LoversLab, and the new Mod DB and itch.io research targets. It separates router/IP evidence from cacheability and defines a delivery method and acceptance requirements for each service.

The [Epic Launcher Preview 0.120.0 staging report](validation/epic-preview-0.120.md) records successful Tailscale/Mullvad endpoint checks and a real 20XX download trial. The tested client sends game traffic through HTTPS passthrough, with no demonstrated cache HIT. Epic remains experimental; do not promote its domain profile based on successful transport checks.

Staging-preparation finding: the Windows Tailscale background service reported a control-server connection failure while its CLI control-protocol probe succeeded. Restarting the service alone did not repair it. Removing the Tailscale service and CLI from Mullvad exclusions restored `Running` with an empty health list; Steam discovery, MagicDNS, HTTP 204 cache heartbeat and ordinary HTTPS passed with Mullvad disconnected and connected. This establishes a healthier baseline for the staged tests, not an Epic cache result. Verify the installed VPN versions and retain rollback settings when testing another machine.

- Implemented in this increment: explicit service catalog, pinned client hostname snapshot with attribution, guarded server profile generation, Windows service-plan import and cleanup, regression tests and Windows CI checks.
- Next: staged Epic HTTP/HTTPS/download validation and actual HIT evidence, then EA and Microsoft profiles one at a time; lock server-side domain/image versions to the same reviewed snapshot.
- Reliability work: health-based DNS bypass/recovery with state persistence, transition tests, metrics and in-place upgrades. Do not redirect DNS to a dead service during recovery.
- Research: evaluate GOG, Amazon Games, Nexus Mods and LoversLab delivery behavior separately. Implement supported integrations only after evidence establishes a workable path; authenticated HTTPS may require a different local-download-library approach rather than transparent caching.

No v2 launcher profile has passed these acceptance checks yet. This milestone starts development; it does not declare broad publisher compatibility.

