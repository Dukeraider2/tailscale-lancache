# Tailscale LANCache

**v2 development branch:** the initial multi-service profile implementation is available for staged testing. Steam remains the default. See [v2 development and compatibility](docs/v2-development.md) before enabling experimental profiles. The published v1.0.0 release remains the baseline for the existing deployment.

Steam LANCache on a Docker-based TrueNAS system, reached through Tailscale from a Windows PC with Mullvad connected or disconnected. This is an installable v1 source package extracted from a working deployment. All network addresses, tailnet names and storage paths are supplied at installation time. No authentication keys, device state, personal logs or binaries are included.

## How it works

Steam discovers a private RFC1918 cache address. The cache advertises that single address as a Tailscale `/32` route. A Windows DNS proxy listens only on localhost and sends selected DNS queries to the cache on TCP 8053. Owned NRPT rules cover Steam discovery and exact MagicDNS device names. Ordinary DNS continues to use the PC's existing resolver.

Tailscale carries the private cache route while normal internet traffic uses Mullvad when connected. During v2 staging preparation, the Windows Tailscale background service recovered its control connection when its Mullvad exclusions were removed; the baseline then passed with Mullvad connected and disconnected. Older deployments used exclusions. Test the background service's health as well as peer connectivity before choosing a configuration. Results depend on VPN versions and policies. See [Tailscale's other-VPN guidance](https://tailscale.com/docs/reference/faq/other-vpns) and [LANCache troubleshooting](https://lancache.net/docs/common-issues/).

## Requirements

- Docker-based TrueNAS supporting custom Compose apps, or a Linux Docker Compose host with ipvlan and `/dev/net/tun`.
- A reserved, unused RFC1918 IPv4 address on the server LAN, outside the DHCP allocation range.
- A dedicated dataset with **512 GB hard quota** for the default **450 GiB** content cache. Logs, indexes and Tailscale state share the remaining space. Snapshots also consume space; exclude this disposable cache from snapshot policies where appropriate.
- Tailscale and MagicDNS, permission to approve a subnet route, and tailnet access to the cache on TCP 80 and 8053.
- Windows x64, Windows PowerShell 5.1+, an Administrator session, and no existing local port-53 listener. Domain-managed NRPT policies may prevent this setup.
- Python 3.10+ on the machine used to generate the server document; no Python packages are required. Python is not needed on the Windows client for installation.

## Install server

1. Create a dedicated dataset using the TrueNAS UI, set its hard quota to 512 GB, and create `cache`, `logs` and `tailscale` child directories. Grant the containers suitable write access. Tailscale state is sensitive; restrict access to administrators. The generator does not create datasets or enforce quotas.
2. Generate the deployment, replacing every example value with your own configuration. The example addresses below are generic and are not a live deployment:

```sh
python server/generate.py --cache-ip 192.168.50.10 --subnet 192.168.50.0/24 --gateway 192.168.50.1 --interface eth0 --dataset /mnt/POOL/lancache --tailnet-suffix example-tailnet.ts.net
```

3. Paste `generated/compose.yaml` into TrueNAS's custom-app Compose editor, or on a standard Docker host run `docker compose -f generated/compose.yaml up -d`. The generated JSON document is valid YAML 1.2. Use the real interface name; TrueNAS VMs commonly have a different name from physical hosts.
4. View the Tailscale container logs and open its login URL yourself. Authenticate to your tailnet, then approve **only the cache `/32` advertised route** in the Tailscale admin console. No auth key is required in the source or deployment. If login times out, restart that container and use its new login URL. Persist its state directory across restarts.
5. On each Windows client, enable Tailscale route acceptance and DNS. Ensure its MagicDNS suffix matches the generator input. Confirm the cache `/32` route is selected on the Tailscale adapter.

The ipvlan service exposes DNS 53, DNS transport 8053 and cache HTTP on its LAN address. Restrict access using LAN firewalls and tailnet grants. Do not port-forward these services to the internet. Tailscale uses kernel networking with `NET_ADMIN` and netfilter disabled; host/LAN restrictions are your responsibility. This deployment does not advertise an exit node or a whole LAN subnet.

The dnsproxy image is pinned to v0.86.0. LANCache uses its upstream `latest` tags and Tailscale uses `stable`; those are mutable tags. Resolve them to tested image digests if you require reproducible production deployments. Review image changes before upgrading.

## Configure Mullvad

Enable Mullvad LAN sharing and keep its normal DNS setting. Start with Tailscale running through the normal VPN tunnel, without exclusions for `tailscaled.exe` or `tailscale.exe`. Do not exclude `dnsproxy.exe` or configure the PC's whole DNS service to use the cache. Check that Tailscale reports `Running` with no health warnings, then test cache access, MagicDNS and normal internet traffic in both VPN states.

If that configuration cannot carry Tailscale traffic, split-tunnel exclusions for the installed Tailscale service and CLI are an alternative to test. Keep them only if coordination-server connectivity and all baseline checks pass. A successful command-line control probe or a cached peer connection alone does not prove that the Windows background service can synchronize its network map. Removing the exclusions resolved that distinction during v2 staging preparation.

The installer deliberately leaves Mullvad settings and Tailscale enrollment to the operator. It does not disable either VPN or alter security settings.

## Install Windows client

Extract the complete source package to a folder. Open Windows PowerShell as Administrator and run:

```powershell
.\windows\Install.ps1 -CacheIP '192.168.50.10' -TailnetSuffix 'example-tailnet.ts.net' -LanSubnet '192.168.50.0/24' -WhatIf
.\windows\Install.ps1 -CacheIP '192.168.50.10' -TailnetSuffix 'example-tailnet.ts.net' -LanSubnet '192.168.50.0/24'
```

`-WhatIf` validates the cache address and prints the proposed action without changing the system. The actual install checks the active Tailscale `/32` route and TCP 8053, downloads the official [AdGuard dnsproxy v0.86.0 Windows x64 archive](https://github.com/AdguardTeam/dnsproxy/releases/tag/v0.86.0), and verifies its pinned SHA-256 before extraction. It installs into `%ProgramData%\TailscaleLANCache`, protects executable and script permissions, saves original suffix and metric preferences, and registers two SYSTEM tasks. Maintenance runs at startup and every minute.

`-LanSubnet` is optional. When supplied, maintenance lowers Tailscale's route priority on that directly attached LAN to avoid overlapping subnet routes; away from that LAN it raises the priority. The cache's more specific `/32` remains selected. Avoid this option if other routes require a different adapter metric.

Installation failures after the original-state backup trigger uninstall rollback. Reinstallation is refused while an existing runtime directory is present: uninstall first. This package uses separate task names from earlier experimental deployments. Remove those deployments before installing this one; do not install over an existing local DNS proxy.

## Verify

Restart idle Steam after installing. Run the following once with Mullvad connected and once disconnected; the test never changes VPN state:

```powershell
.\windows\Test.ps1 -CacheIP '192.168.50.10' -MagicDNSName 'steam-lancache.example-tailnet.ts.net'
```

The test checks Steam discovery, ordinary DNS, optional MagicDNS and an HTTP 204 cache heartbeat. To prove content reuse, download a small Steam game, remove its local installation, download it again, and check the server cache logs for HIT responses. Heartbeat checks alone do not prove caching or throughput. Test again after a reboot and from a different network. The extracted deployment passed on/off VPN connectivity tests; this generic installer has been syntax-checked and tested without changing the source machine's working installation. A fresh-machine install and reboot remain necessary acceptance checks.

## Uninstall and recover

Run from an Administrator PowerShell:

```powershell
.\windows\Uninstall.ps1 -WhatIf
.\windows\Uninstall.ps1
```

This removes only this product's tasks and NRPT rules, restores the saved suffix list and adapter preferences, and removes its runtime directory. If you changed those preferences after installation, review `original-state.json` first: restoring it uses the installation-time values. Mullvad exclusions, Tailscale membership, server deployment and cached data remain operator-managed. If the server is down, uninstalling restores ordinary Steam DNS so downloads can go directly to the internet. There is no automatic DNS failover in v1; Steam-specific queries can fail while the cache or Tailscale is unavailable.

For a server restart or image upgrade, restart the entire Compose app because services share the cache container's network namespace. To remove the server, stop/delete the app in TrueNAS (or `docker compose down` on a standard host), revoke its Tailscale node and route, and decide separately whether to delete cache data. Never publish the persisted Tailscale state directory.

## Privacy and scope

Generated deployment files, runtime configuration, authentication state, logs, downloaded executables and archives are excluded by `.gitignore`. Keep generated files private; they contain your network topology. The distributed example configuration contains only generic values. Third-party components retain their own licenses and are downloaded separately.

v1 supports Steam discovery and the coexistence configuration above. The v2 branch adds opt-in experimental profile generation for Epic, EA/Origin, Microsoft Xbox content and Microsoft updates. Those profiles have not passed download/cache-HIT acceptance tests. GOG, Amazon Games, Nexus Mods and LoversLab remain research-only and cannot be enabled. HTTPS, authentication, signed URLs and publisher behavior need separate evaluation; this project does not intercept TLS or promise those services can be cached.

Run source checks with `python -m unittest discover -s tests -v`, `powershell -NoProfile -File tests/Check-Syntax.ps1` and `powershell -NoProfile -File tests/Check-ServicePlan.ps1`. No production settings are changed by these checks.
