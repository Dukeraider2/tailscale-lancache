# v2 development: first milestone

Status: source implementation for staged testing. No v2 production release or live migration has occurred. The Tailscale `/32` transport, Mullvad coexistence approach and shared 512 GB storage budget remain the base.

## Service states

| Service ID | Initial state | Coverage and limits |
| --- | --- | --- |
| `steam` | Default baseline | Existing Steam discovery configuration; actual content HIT verification is still required. |
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

- Implemented in this increment: explicit service catalog, pinned client hostname snapshot with attribution, guarded server profile generation, Windows service-plan import and cleanup, regression tests and Windows CI checks.
- Next: staged Epic HTTP/HTTPS/download validation and actual HIT evidence, then EA and Microsoft profiles one at a time; lock server-side domain/image versions to the same reviewed snapshot.
- Reliability work: health-based DNS bypass/recovery with state persistence, transition tests, metrics and in-place upgrades. Do not redirect DNS to a dead service during recovery.
- Research: evaluate GOG, Amazon Games, Nexus Mods and LoversLab delivery behavior separately. Implement supported integrations only after evidence establishes a workable path; authenticated HTTPS may require a different local-download-library approach rather than transparent caching.

No v2 launcher profile has passed these acceptance checks yet. This milestone starts development; it does not declare broad publisher compatibility.
